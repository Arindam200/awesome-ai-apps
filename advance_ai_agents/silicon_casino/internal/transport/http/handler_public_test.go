package httptransport

import "testing"

func TestLeaderboardParamAllowlists(t *testing.T) {
	windowTests := []struct {
		v    string
		want bool
	}{
		{"7d", true},
		{"30d", true},
		{"all", true},
		{"", false},
		{"weekly", false},
	}
	for _, tt := range windowTests {
		if got := isAllowedLeaderboardWindow(tt.v); got != tt.want {
			t.Fatalf("window %q = %v, want %v", tt.v, got, tt.want)
		}
	}

	roomTests := []struct {
		v    string
		want bool
	}{
		{"all", true},
		{"low", true},
		{"mid", true},
		{"high", true},
		{"vip", false},
	}
	for _, tt := range roomTests {
		if got := isAllowedLeaderboardRoom(tt.v); got != tt.want {
			t.Fatalf("room %q = %v, want %v", tt.v, got, tt.want)
		}
	}

	sortTests := []struct {
		v    string
		want bool
	}{
		{"score", true},
		{"net_cc_from_play", true},
		{"hands_played", true},
		{"win_rate", true},
		{"bb_per_100", false},
	}
	for _, tt := range sortTests {
		if got := isAllowedLeaderboardSort(tt.v); got != tt.want {
			t.Fatalf("sort %q = %v, want %v", tt.v, got, tt.want)
		}
	}
}
