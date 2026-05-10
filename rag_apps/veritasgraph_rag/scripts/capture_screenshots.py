"""Capture Gradio UI screenshots for the PR."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "assets"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              device_scale_factor=2)
    page = ctx.new_page()

    # 1. Empty UI
    page.goto("http://localhost:7860", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    page.screenshot(path=str(OUT / "01_ui_empty.png"), full_page=True)
    print("captured 01_ui_empty.png")

    # 2. Filled question (don't actually run — keeps it deterministic + fast)
    page.fill("textarea", "Who is part of the Paranormal Military Squad and what is Operation: Dulce?")
    time.sleep(1)
    page.screenshot(path=str(OUT / "02_ui_question.png"), full_page=True)
    print("captured 02_ui_question.png")

    browser.close()
