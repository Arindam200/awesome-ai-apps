import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cart import ShoppingCart


def test_add_single_item_total():
    cart = ShoppingCart()
    cart.add_item("apple", 2.50)
    assert cart.total() == 2.50


def test_remove_existing_item():
    cart = ShoppingCart()
    cart.add_item("apple", 2.50)
    cart.remove_item("apple")
    assert cart.total() == 0.0


def test_total_respects_quantity():
    cart = ShoppingCart()
    cart.add_item("apple", 2.50, quantity=3)
    assert cart.total() == 7.50


def test_remove_missing_item_is_noop():
    cart = ShoppingCart()
    cart.add_item("apple", 2.50)
    cart.remove_item("banana")  # must not raise
    assert cart.total() == 2.50


def test_discount_applied_once():
    cart = ShoppingCart()
    cart.add_item("book", 10.00)
    cart.apply_discount(10)
    cart.apply_discount(10)  # re-applying must not compound
    assert cart.total() == 9.00
