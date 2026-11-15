"""Headless-Chrome self-test for a generated explainer.

Usage: python qa.py <page.html> <screenshot.png>
Prints one JSON line: {"errors": [...]}. Runs in its own process so Playwright's
event loop never collides with Streamlit's.
"""

import json
import sys

from playwright.sync_api import sync_playwright


def main() -> None:
    page_path, shot_path = sys.argv[1], sys.argv[2]
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860})
        page.on("pageerror", lambda e: errors.append(f"Uncaught JS error: {e}"))
        page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.goto(f"file://{page_path}", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(800)
        page.screenshot(path=shot_path)
        # Scroll through so IntersectionObserver-driven widgets initialise too.
        height = page.evaluate("document.body.scrollHeight")
        for y in range(0, int(height), 700):
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(120)
        # Poke every range input once to catch handler errors.
        page.evaluate("""() => document.querySelectorAll('input[type=range]').forEach(el => {
            el.value = (Number(el.min || 0) + Number(el.max || 100)) / 2;
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        })""")
        page.wait_for_timeout(500)
        browser.close()
    # De-duplicate while keeping order.
    print(json.dumps({"errors": list(dict.fromkeys(errors))[:25]}))


if __name__ == "__main__":
    main()
