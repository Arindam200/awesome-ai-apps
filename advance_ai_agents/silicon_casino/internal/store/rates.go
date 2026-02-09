package store

import "math"

func ComputeCCFromBudgetUSD(budgetUSD, ccPerUSD, weight float64) int64 {
	if budgetUSD <= 0 || ccPerUSD <= 0 || weight <= 0 {
		return 0
	}
	cc := budgetUSD * ccPerUSD * weight
	return int64(math.Round(cc))
}

func ComputeCCFromTokens(totalTokens int, pricePer1KTokensUSD, ccPerUSD, weight float64) int64 {
	if totalTokens <= 0 || pricePer1KTokensUSD <= 0 || ccPerUSD <= 0 || weight <= 0 {
		return 0
	}
	usd := (float64(totalTokens) / 1000.0) * pricePer1KTokensUSD
	cc := usd * ccPerUSD * weight
	return int64(math.Round(cc))
}
