package game

type Pot struct {
	Main    int64
	Side    int64
	HasSide bool
}

// Compute pot for heads-up based on total contributions per player.
func ComputePot(contribA, contribB int64) Pot {
	if contribA == contribB {
		return Pot{Main: contribA + contribB}
	}
	if contribA < contribB {
		main := contribA * 2
		side := contribB - contribA
		return Pot{Main: main, Side: side, HasSide: true}
	}
	main := contribB * 2
	side := contribA - contribB
	return Pot{Main: main, Side: side, HasSide: true}
}
