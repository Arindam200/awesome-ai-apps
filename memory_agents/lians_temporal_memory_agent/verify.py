"""Executable verification for the Lians temporal-memory example."""

from main import _contents, run_demo


def main() -> None:
    results = run_demo()
    current = _contents(results["current"])
    historical = _contents(results["historical"])

    assert any("Monday" in content for content in current)
    assert all("Friday" not in content for content in current)
    assert any("Friday" in content for content in historical)
    assert all("Monday" not in content for content in historical)
    assert results["current"]["receipt_sha256"]
    assert results["historical"]["receipt_sha256"]
    print("PASS: current and point-in-time memory stayed separated")


if __name__ == "__main__":
    main()
