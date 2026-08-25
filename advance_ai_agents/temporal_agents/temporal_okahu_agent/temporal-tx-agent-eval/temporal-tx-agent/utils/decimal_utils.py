"""Utility functions for Decimal handling with Couchbase."""

from decimal import Decimal
from typing import Union

def to_decimal(value: Union[str, int, float, Decimal]) -> Decimal:
    """Convert value to Decimal."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    return Decimal(str(value))

def decimal_to_float(value: Union[Decimal, float, int, str]) -> float:
    """Convert Decimal to float."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(Decimal(value))
    return float(value)

def from_decimal(value: Union[Decimal, float, int, str, None]) -> Union[float, None]:
    """Convert Decimal to float, handling None."""
    if value is None:
        return None
    return decimal_to_float(value)

def from_decimal128(value) -> float:
    """Convert Decimal128 (MongoDB/Couchbase) to float."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(Decimal(value))
        except:
            return 0.0
    # Try to convert if it has a value attribute (like Decimal128)
    try:
        return float(value)
    except:
        return 0.0

