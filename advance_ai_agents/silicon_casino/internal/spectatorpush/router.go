package spectatorpush

import "strings"

type Router struct{}

func (r Router) MatchTargets(targets []PushTarget, ev NormalizedEvent) []PushTarget {
	if len(targets) == 0 {
		return nil
	}
	out := make([]PushTarget, 0, len(targets))
	for _, target := range targets {
		if !target.Enabled {
			continue
		}
		if !scopeMatches(target, ev) {
			continue
		}
		if !eventAllowed(target.EventAllowlist, ev.EventType) {
			continue
		}
		out = append(out, target)
	}
	return out
}

func scopeMatches(target PushTarget, ev NormalizedEvent) bool {
	switch target.ScopeType {
	case "all":
		return true
	case "room":
		return target.ScopeValue != "" && target.ScopeValue == ev.RoomID
	case "table":
		return target.ScopeValue != "" && target.ScopeValue == ev.TableID
	default:
		return false
	}
}

func eventAllowed(allowlist []string, evType string) bool {
	if len(allowlist) == 0 {
		return true
	}
	evType = strings.ToLower(strings.TrimSpace(evType))
	for _, v := range allowlist {
		if v == "" {
			continue
		}
		if strings.ToLower(strings.TrimSpace(v)) == evType {
			return true
		}
	}
	return false
}
