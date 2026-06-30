package game

import "testing"

func TestComputePotEqual(t *testing.T) {
	p := ComputePot(100, 100)
	if p.Main != 200 || p.HasSide {
		t.Fatalf("expected main 200 no side, got %+v", p)
	}
}

func TestComputePotSide(t *testing.T) {
	p := ComputePot(100, 250)
	if p.Main != 200 || !p.HasSide || p.Side != 150 {
		t.Fatalf("expected main 200 side 150, got %+v", p)
	}
}
