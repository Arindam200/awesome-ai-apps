package game

import (
	"sort"
)

type HandRank struct {
	Category int
	Ranks    []int
}

func (h HandRank) BetterThan(o HandRank) bool {
	if h.Category != o.Category {
		return h.Category > o.Category
	}
	for i := 0; i < len(h.Ranks) && i < len(o.Ranks); i++ {
		if h.Ranks[i] != o.Ranks[i] {
			return h.Ranks[i] > o.Ranks[i]
		}
	}
	return false
}

func Evaluate7(cards []Card) HandRank {
	best := HandRank{Category: -1}
	idx := []int{0, 1, 2, 3, 4}
	for a := 0; a < 7; a++ {
		for b := a + 1; b < 7; b++ {
			for c := b + 1; c < 7; c++ {
				for d := c + 1; d < 7; d++ {
					for e := d + 1; e < 7; e++ {
						idx[0], idx[1], idx[2], idx[3], idx[4] = a, b, c, d, e
						h := eval5(cards[idx[0]], cards[idx[1]], cards[idx[2]], cards[idx[3]], cards[idx[4]])
						if h.BetterThan(best) {
							best = h
						}
					}
				}
			}
		}
	}
	return best
}

// Category ranking: 8 Straight Flush, 7 Four, 6 Full House, 5 Flush, 4 Straight, 3 Trips, 2 Two Pair, 1 Pair, 0 High Card
func eval5(c1, c2, c3, c4, c5 Card) HandRank {
	cards := []Card{c1, c2, c3, c4, c5}
	counts := map[int]int{}
	suits := map[Suit]int{}
	ranks := make([]int, 0, 5)
	for _, c := range cards {
		r := int(c.Rank)
		counts[r]++
		suits[c.Suit]++
		ranks = append(ranks, r)
	}
	sort.Sort(sort.Reverse(sort.IntSlice(ranks)))
	isFlush := false
	for _, v := range suits {
		if v == 5 {
			isFlush = true
			break
		}
	}
	isStraight, highStraight := straightHigh(ranks)
	if isFlush && isStraight {
		return HandRank{Category: 8, Ranks: []int{highStraight}}
	}

	// sort counts
	type rc struct {
		rank  int
		count int
	}
	pairs := make([]rc, 0, len(counts))
	for r, c := range counts {
		pairs = append(pairs, rc{rank: r, count: c})
	}
	sort.Slice(pairs, func(i, j int) bool {
		if pairs[i].count != pairs[j].count {
			return pairs[i].count > pairs[j].count
		}
		return pairs[i].rank > pairs[j].rank
	})

	if pairs[0].count == 4 {
		kicker := highestExcluding(ranks, pairs[0].rank)
		return HandRank{Category: 7, Ranks: []int{pairs[0].rank, kicker}}
	}
	if pairs[0].count == 3 && pairs[1].count == 2 {
		return HandRank{Category: 6, Ranks: []int{pairs[0].rank, pairs[1].rank}}
	}
	if isFlush {
		return HandRank{Category: 5, Ranks: ranks}
	}
	if isStraight {
		return HandRank{Category: 4, Ranks: []int{highStraight}}
	}
	if pairs[0].count == 3 {
		kickers := topKickers(ranks, []int{pairs[0].rank}, 2)
		return HandRank{Category: 3, Ranks: append([]int{pairs[0].rank}, kickers...)}
	}
	if pairs[0].count == 2 && pairs[1].count == 2 {
		highPair := pairs[0].rank
		lowPair := pairs[1].rank
		kicker := highestExcluding(ranks, highPair, lowPair)
		return HandRank{Category: 2, Ranks: []int{highPair, lowPair, kicker}}
	}
	if pairs[0].count == 2 {
		kickers := topKickers(ranks, []int{pairs[0].rank}, 3)
		return HandRank{Category: 1, Ranks: append([]int{pairs[0].rank}, kickers...)}
	}
	return HandRank{Category: 0, Ranks: ranks}
}

func straightHigh(ranks []int) (bool, int) {
	unique := uniqueRanks(ranks)
	sort.Sort(sort.Reverse(sort.IntSlice(unique)))
	if len(unique) < 5 {
		return false, 0
	}
	for i := 0; i <= len(unique)-5; i++ {
		if unique[i]-unique[i+4] == 4 {
			return true, unique[i]
		}
	}
	// Wheel A-5
	if contains(unique, 14) && contains(unique, 5) && contains(unique, 4) && contains(unique, 3) && contains(unique, 2) {
		return true, 5
	}
	return false, 0
}

func uniqueRanks(ranks []int) []int {
	m := map[int]bool{}
	out := make([]int, 0, len(ranks))
	for _, r := range ranks {
		if !m[r] {
			m[r] = true
			out = append(out, r)
		}
	}
	return out
}

func contains(arr []int, v int) bool {
	for _, x := range arr {
		if x == v {
			return true
		}
	}
	return false
}

func highestExcluding(ranks []int, exclude ...int) int {
	for _, r := range ranks {
		ok := true
		for _, e := range exclude {
			if r == e {
				ok = false
			}
		}
		if ok {
			return r
		}
	}
	return 0
}

func topKickers(ranks []int, exclude []int, n int) []int {
	out := []int{}
	for _, r := range ranks {
		skip := false
		for _, e := range exclude {
			if r == e {
				skip = true
				break
			}
		}
		if skip {
			continue
		}
		out = append(out, r)
		if len(out) == n {
			break
		}
	}
	return out
}
