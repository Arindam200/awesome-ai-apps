"""Stable sample ticket and patch used by both demo surfaces."""
from __future__ import annotations

import difflib

DEMO_OBJECTIVE = (
    "Fix the failing pytest suite. Users report bugs in cart.py: a discount "
    "compounds when applied twice, removing a missing item crashes, and the "
    "total ignores quantities. Fix ONLY cart.py — never edit a test."
)

DEMO_BUGGY_CART = '''"""A small shopping cart module."""


class ShoppingCart:
    def __init__(self):
        self.items = {}
        self.discount_percent = 0.0

    def add_item(self, name, price, quantity=1):
        if name in self.items:
            self.items[name]["quantity"] += quantity
        else:
            self.items[name] = {"price": price, "quantity": quantity}

    def remove_item(self, name):
        del self.items[name]

    def apply_discount(self, percent):
        self.discount_percent += percent

    def total(self):
        subtotal = sum(item["price"] for item in self.items.values())
        return round(subtotal * (1 - self.discount_percent / 100), 2)
'''

DEMO_FIXED_CART = '''"""A small shopping cart module."""


class ShoppingCart:
    def __init__(self):
        self.items = {}
        self.discount_percent = 0.0

    def add_item(self, name, price, quantity=1):
        if name in self.items:
            self.items[name]["quantity"] += quantity
        else:
            self.items[name] = {"price": price, "quantity": quantity}

    def remove_item(self, name):
        self.items.pop(name, None)

    def apply_discount(self, percent):
        self.discount_percent = percent

    def total(self):
        subtotal = sum(
            item["price"] * item["quantity"] for item in self.items.values()
        )
        return round(subtotal * (1 - self.discount_percent / 100), 2)
'''

DEMO_DIFF = "".join(
    difflib.unified_diff(
        DEMO_BUGGY_CART.splitlines(keepends=True),
        DEMO_FIXED_CART.splitlines(keepends=True),
        fromfile="a/cart.py",
        tofile="b/cart.py",
    )
)
