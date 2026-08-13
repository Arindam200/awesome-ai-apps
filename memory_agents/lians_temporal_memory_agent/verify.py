"""Executable verification for the Lians temporal-memory example."""

import hashlib
import json
from typing import Any

from main import _contents, run_demo


def _verify_receipt(result: dict[str, Any], label: str) -> None:
    receipt = result.get("receipt")
    expected = result.get("receipt_sha256")
    if not isinstance(receipt, dict) or not isinstance(expected, str):
        raise TypeError(f"{label} recall did not return a complete receipt")

    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"), default=str)
    actual = hashlib.sha256(encoded.encode()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"{label} recall receipt hash does not match its payload")


def main() -> None:
    results = run_demo()
    current = _contents(results["current"])
    historical = _contents(results["historical"])

    if not any("Monday" in content for content in current):
        raise RuntimeError("current recall did not return the Monday estimate")
    if any("Friday" in content for content in current):
        raise RuntimeError("current recall leaked the superseded Friday estimate")
    if not any("Friday" in content for content in historical):
        raise RuntimeError("historical recall did not return the Friday estimate")
    if any("Monday" in content for content in historical):
        raise RuntimeError("historical recall leaked the later Monday estimate")

    _verify_receipt(results["current"], "current")
    _verify_receipt(results["historical"], "historical")
    print("PASS: current and point-in-time memory stayed separated")


if __name__ == "__main__":
    main()
