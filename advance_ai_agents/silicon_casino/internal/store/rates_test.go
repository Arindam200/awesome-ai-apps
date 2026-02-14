package store

import "testing"

func TestComputeCCFromBudgetUSD(t *testing.T) {
	got := ComputeCCFromBudgetUSD(10, 1000, 1)
	if got != 10000 {
		t.Fatalf("expected 10000, got %d", got)
	}
}

func TestComputeCCFromTokens(t *testing.T) {
	got := ComputeCCFromTokens(2000, 0.001, 1000, 1)
	if got != 2 {
		t.Fatalf("expected 2, got %d", got)
	}
}
