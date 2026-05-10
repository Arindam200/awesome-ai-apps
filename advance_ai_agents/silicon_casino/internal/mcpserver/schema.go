package mcpserver

const (
	defaultPageLimit      = 50
	maxPageLimit          = 500
	maxLeaderboardLimit   = 100
	defaultLeaderboardWin = "30d"
	defaultLeaderboardRm  = "all"
	defaultLeaderboardSrt = "score"
)

func clampPagination(limit, offset, maxLimit int) (int, int) {
	if limit <= 0 {
		limit = defaultPageLimit
	}
	if limit > maxLimit {
		limit = maxLimit
	}
	if offset < 0 {
		offset = 0
	}
	return limit, offset
}

func normalizeJoinMode(v string) string {
	if v == "" {
		return "random"
	}
	return v
}

func normalizeLeaderboardWindow(v string) string {
	if v == "" {
		return defaultLeaderboardWin
	}
	return v
}

func normalizeLeaderboardRoom(v string) string {
	if v == "" {
		return defaultLeaderboardRm
	}
	return v
}

func normalizeLeaderboardSort(v string) string {
	if v == "" {
		return defaultLeaderboardSrt
	}
	return v
}

func isAllowedLeaderboardWindow(v string) bool {
	return v == "7d" || v == "30d" || v == "all"
}

func isAllowedLeaderboardRoom(v string) bool {
	return v == "all" || v == "low" || v == "mid" || v == "high"
}

func isAllowedLeaderboardSort(v string) bool {
	return v == "score" || v == "net_cc_from_play" || v == "hands_played" || v == "win_rate"
}
