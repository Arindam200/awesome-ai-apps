from calculator import add


def test_adds_two_integers() -> None:
    """Addition combines two positive integers."""
    assert add(2, 3) == 5


def test_adds_negative_integer() -> None:
    """Addition supports a negative right operand."""
    assert add(7, -2) == 5
