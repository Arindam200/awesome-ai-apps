package spectatorpush

import (
	"fmt"
	"strconv"
	"strings"
	"time"
)

const (
	colorAction   = 0x3BA55D
	colorSnapshot = 0x5865F2
	colorWarn     = 0xFEE75C
	colorRecover  = 0x57F287
	colorCritical = 0xED4245

	thoughtPreviewLimit = 160
	shortIDLimit        = 10
	defaultFooter       = "silicon-casino spectator push"
)

func FormatMessage(ev NormalizedEvent) (FormattedMessage, bool) {
	roomShort := shortID(fallback(ev.RoomID, "unknown"), shortIDLimit)
	tableShort := shortID(fallback(ev.TableID, "unknown"), shortIDLimit)
	fields := make([]MessageField, 0, 10)
	base := FormattedMessage{
		Timestamp: eventTimestamp(ev.ServerTS),
		Footer:    defaultFooter,
	}

	switch ev.EventType {
	case "action_log":
		base.Title = fmt.Sprintf("Action · R:%s · T:%s", roomShort, tableShort)
		base.Content = fmt.Sprintf("seat %s %s", seatText(ev.ActorSeat), fallback(ev.Action, "action"))
		base.Description = fmt.Sprintf("Seat %s %s", seatText(ev.ActorSeat), fallback(ev.Action, "action"))
		base.Color = colorAction
		fields = append(fields,
			MessageField{Name: "Seat", Value: seatText(ev.ActorSeat), Inline: true},
			MessageField{Name: "Action", Value: fallback(ev.Action, "-"), Inline: true},
			MessageField{Name: "Amount", Value: amountText(ev.Amount), Inline: true},
			MessageField{Name: "Hand", Value: fallback(ev.HandID, "-"), Inline: true},
			MessageField{Name: "Street", Value: fallback(ev.Street, "-"), Inline: true},
			MessageField{Name: "Status", Value: fallback(ev.TableStatus, "-"), Inline: true},
		)
		if ev.Amount != nil {
			base.Description = fmt.Sprintf("%s (%dcc)", base.Description, *ev.Amount)
		}
		if ev.ThoughtLog != "" {
			fields = append(fields, MessageField{Name: "Thought", Value: formatThoughtPreview(ev.ThoughtLog), Inline: false})
		}
	case "table_snapshot":
		base.Title = fmt.Sprintf("Snapshot · R:%s · T:%s", roomShort, tableShort)
		base.Content = fmt.Sprintf("street=%s status=%s", fallback(ev.Street, "-"), fallback(ev.TableStatus, "active"))
		base.Description = fmt.Sprintf("Street=%s, Status=%s", fallback(ev.Street, "-"), fallback(ev.TableStatus, "active"))
		base.Color = colorSnapshot
		fields = append(fields,
			MessageField{Name: "Hand", Value: fallback(ev.HandID, "-"), Inline: true},
			MessageField{Name: "Street", Value: fallback(ev.Street, "-"), Inline: true},
			MessageField{Name: "Status", Value: fallback(ev.TableStatus, "active"), Inline: true},
		)
	case "reconnect_grace_started":
		base.Title = fmt.Sprintf("Reconnect Grace · R:%s · T:%s", roomShort, tableShort)
		base.Content = "table enters reconnect grace"
		base.Description = "Table enters reconnect grace window."
		base.Color = colorWarn
		fields = append(fields, MessageField{Name: "Status", Value: fallback(ev.TableStatus, "closing"), Inline: true})
		if ev.CloseReason != "" {
			fields = append(fields, MessageField{Name: "Reason", Value: ev.CloseReason, Inline: true})
		}
	case "opponent_reconnected":
		base.Title = fmt.Sprintf("Recovered · R:%s · T:%s", roomShort, tableShort)
		base.Content = "table recovered and continues"
		base.Description = "Opponent reconnected; table continues."
		base.Color = colorRecover
		fields = append(fields,
			MessageField{Name: "Hand", Value: fallback(ev.HandID, "-"), Inline: true},
			MessageField{Name: "Street", Value: fallback(ev.Street, "-"), Inline: true},
			MessageField{Name: "Status", Value: fallback(ev.TableStatus, "active"), Inline: true},
		)
	case "opponent_forfeited":
		base.Title = fmt.Sprintf("Forfeit · R:%s · T:%s", roomShort, tableShort)
		base.Content = "table settled by forfeit"
		base.Description = "Table settled by opponent forfeit."
		base.Color = colorCritical
		fields = append(fields, MessageField{Name: "Status", Value: fallback(ev.TableStatus, "closed"), Inline: true})
		if ev.CloseReason != "" {
			fields = append(fields, MessageField{Name: "Reason", Value: ev.CloseReason, Inline: true})
		}
	case "table_closed":
		base.Title = fmt.Sprintf("Table Closed · R:%s · T:%s", roomShort, tableShort)
		base.Content = "table closed"
		base.Description = "Table closed."
		base.Color = colorCritical
		fields = append(fields, MessageField{Name: "Status", Value: fallback(ev.TableStatus, "closed"), Inline: true})
		if ev.CloseReason != "" {
			fields = append(fields, MessageField{Name: "Reason", Value: ev.CloseReason, Inline: true})
		}
	default:
		return FormattedMessage{}, false
	}

	base.Fields = fields
	return base, true
}

func seatText(seat *int) string {
	if seat == nil {
		return "-"
	}
	return strconv.Itoa(*seat)
}

func trimText(v string, max int) string {
	if max <= 0 || len(v) <= max {
		return v
	}
	if max <= 3 {
		return v[:max]
	}
	return v[:max-3] + "..."
}

func amountText(amount *int64) string {
	if amount == nil {
		return "-"
	}
	return strconv.FormatInt(*amount, 10)
}

func formatThoughtPreview(v string) string {
	return trimText(strings.TrimSpace(v), thoughtPreviewLimit)
}

func shortID(v string, max int) string {
	if max <= 0 || len(v) <= max {
		return v
	}
	return v[:max]
}

func eventTimestamp(ms int64) string {
	if ms <= 0 {
		return ""
	}
	return time.UnixMilli(ms).UTC().Format(time.RFC3339)
}

func fallback(v, d string) string {
	if strings.TrimSpace(v) == "" {
		return d
	}
	return v
}
