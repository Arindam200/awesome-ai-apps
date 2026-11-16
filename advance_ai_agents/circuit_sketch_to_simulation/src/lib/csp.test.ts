import { chromium } from "playwright-core";
import { describe, expect, it } from "vitest";
import { lockDown } from "./csp";
import { findChrome } from "./sandbox";

// Chrome ignores a CSP <meta> that ends up outside <head>. Check the real parser applies it for
// the page shapes models produce: normal, cut off, with stray text first, and fragments.
const chrome = findChrome();
const pages = {
  normal: "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>x</title></head><body><p>ok</p></body></html>",
  "cut off": "<!DOCTYPE html><html><head><title>x</title><style>body{color:red}</style></head><body><div>half",
  "stray fence first": "```html\n<!DOCTYPE html>\n<html>\n<head>\n<title>x</title>",
  "no head": "<html><body><p>x</p></body></html>",
  fragment: "<svg width='10' height='10'></svg>",
};

describe.skipIf(!chrome)("CSP in a real browser", () => {
  it("applies the policy to every page shape", async () => {
    const browser = await chromium.launch({ executablePath: chrome, headless: true });
    try {
      for (const [name, html] of Object.entries(pages)) {
        const page = await browser.newPage();
        const ignored: string[] = [];
        page.on("console", (m) => /policy has been ignored/i.test(m.text()) && ignored.push(m.text()));
        await page.setContent(lockDown(html));
        // An inline script that tries a fetch: the CSP must block it.
        const blocked = await page.evaluate(() => fetch("https://example.com/").then(() => false, () => true));
        const inHead = await page.evaluate(() => !!document.head.querySelector('meta[http-equiv="Content-Security-Policy"]'));
        expect({ name, ignored, blocked, inHead }).toEqual({ name, ignored: [], blocked: true, inHead: true });
        await page.close();
      }
    } finally {
      await browser.close();
    }
  }, 60_000);
});
