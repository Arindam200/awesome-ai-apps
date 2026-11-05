"""Read -> plan -> build (in parallel) -> self-test -> patch.

1. Plan: Kimi reads the full paper (text + figure pages) and designs a lesson:
   sections, one interactive widget per idea, key results, glossary, quiz.
2. Build: one Kimi call writes the page shell while one call per section writes
   that section's prose and widget, all at the same time, against a shared
   contract. We stitch them into a single self-contained HTML file.
3. Self-test: optional headless Chrome run collects JS errors; Kimi patches them.
4. Refine: the user asks for changes; Kimi answers with SEARCH/REPLACE patches.
"""

from __future__ import annotations

import base64
import html as htmllib
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from openai import OpenAI

from kimi import stream_chat
from paper import Paper

QA_SCRIPT = Path(__file__).parent / "qa.py"

AUDIENCES = {
    "Curious beginner": "a smart high-schooler or non-specialist. Build intuition first, minimal math, everyday analogies.",
    "Software engineer": "a working software engineer with basic linear algebra and probability. Show the math, but make every symbol tangible.",
    "Researcher": "an ML researcher. Be precise and dense, keep the full math, focus on what is new versus prior work.",
}

PLAN_SYSTEM = """You are a world-class science communicator who designs interactive explainers in the spirit of Distill.pub, Bartosz Ciechanowski and 3Blue1Brown. You read the entire paper, including its figures, and design a lesson where every core idea is something the reader can play with.

Return one JSON object with exactly these keys:
{
  "title": "catchy explainer title (not the paper title)",
  "hook": "one sentence that makes a curious reader want to keep going",
  "paper": {"title": "...", "authors": "...", "year": "...", "link": "..."},
  "big_idea": "the paper's core contribution in two sentences",
  "sections": [
    {
      "id": "s1",
      "heading": "...",
      "goal": "what the reader will understand after this section",
      "explanation": "4-6 sentences, plain language, grounded in the paper",
      "interactive": {
        "kind": "e.g. slider-driven canvas animation, draggable diagram, step-through simulation, 3D scene, live chart, tiny model you can train in the browser",
        "title": "...",
        "controls": ["each slider/button/drag handle and what it changes"],
        "behavior": "what the reader sees change as they play",
        "why_it_teaches": "the insight the reader should feel"
      },
      "math": "optional key equation in LaTeX, or empty string",
      "grounding": "the paper section, figure or table this comes from"
    }
  ],
  "key_results": [{"claim": "...", "number": "the exact number as printed in the paper", "source": "Table/Figure/Section"}],
  "limitations": ["..."],
  "glossary": [{"term": "...", "definition": "one sentence"}],
  "quiz": [{"question": "...", "options": ["a", "b", "c", "d"], "answer": 0, "explanation": "..."}]
}

Rules: 4-6 sections that build on each other, one interactive per section, each interactive genuinely different and genuinely teaching (not decoration). 3 quiz questions. Only use numbers that appear in the paper. Output only the JSON."""

BUILD_SYSTEM = """You are an elite creative front-end engineer and visual designer. You build polished, self-contained interactive explainers (one HTML file) that people share on social media.

Hard requirements:
- All CSS and JS inline. The only allowed external resources are:
  - KaTeX 0.16.11 from https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/ (katex.min.css, katex.min.js, contrib/auto-render.min.js) for math
  - Optionally three.js via <script type="importmap"> pointing to https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js
  - Optionally d3 from https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js
  - Fonts from fonts.googleapis.com
  Draw every visual yourself with SVG or canvas. No external images.
- Every interactive works fully, with real labelled controls. It must look alive on first paint (sensible initial state, gentle idle animation where it helps) and react instantly to input.
- Faithful to the paper: only use numbers that appear in the provided paper text, and cite where ideas come from (e.g. "§3.2", "Table 2").
- Design: editorial and beautiful. Readable text column (~720px) with widgets allowed wider, generous whitespace, a clear type scale, one restrained accent color, smooth but quick transitions. Light and dark via prefers-color-scheme. Responsive down to 375px wide. Accessible contrast, keyboard-usable controls.
- Robustness: wrap each widget's setup in try/catch so one failure can't break the page; pause animations when offscreen; no alert(), no localStorage, no console errors."""

# Shared contract so the shell and the sections can be written in parallel.
KIT_CONTRACT = """SHARED CONTRACT (the shell implements it, sections use it)

CSS custom properties on :root, redefined for dark mode:
--bg --fg --muted --surface --border --accent --accent-2 --good --bad --tip-bg --tip-fg --radius --font-body --font-mono

Component classes:
.lesson         wrapper of one lesson section (consistent vertical rhythm, scroll-margin for the sticky bar)
.prose          the readable text column (~720px, centered)
.widget         card around an interactive; may be wider than .prose (up to ~1040px, centered)
.widget-title   small heading inside .widget
.widget-stage   full-width area holding the canvas or svg
.controls       wrapping flex row of controls under the stage
.control        one labelled control: <label class="control"><span>Name</span><input type="range"><output></output></label>
.btn, .btn.primary   buttons
.readout        monospace live numbers
.caption        small muted text under a widget
.callout        highlighted aside inside .prose
.term           glossary term in prose, written as <span class="term" data-def="one-sentence definition">term</span>
.eq             display-math block

window.ExplainerKit (already provided, loaded in <head> before any section):
ExplainerKit.onVisible(el, start, stop)   call start/stop as el enters/leaves the viewport
ExplainerKit.loop(el, frame)              requestAnimationFrame loop that only runs while el is visible; frame(timeMs, dtSeconds)
ExplainerKit.fitCanvas(canvas, height?)   sizes a canvas for devicePixelRatio, returns {ctx, width, height} in CSS pixels
ExplainerKit.color(name, fallback?)       reads a CSS custom property, e.g. ExplainerKit.color('--accent')
Glossary tooltips for .term[data-def] are handled by the kit."""

SHELL_PROMPT = """Write the page SHELL of the explainer. Other engineers are writing the lesson sections at the same time and will drop them into your placeholders, so don't write the sections yourself.

{contract}

The shell must contain:
- <head>: meta charset + viewport, <title>, fonts, KaTeX (css, js and auto-render, rendering $...$ and $$...$$ once on DOMContentLoaded), and a <style> block that implements every custom property and class in the contract beautifully (light and dark), plus your own layout styles.
- Do NOT define window.ExplainerKit or tooltip code; the kit is injected for you.
- A hero (an explainer title, the hook, the paper title, authors and a link to {link}), a sticky slim reading-progress bar, and a compact table of contents linking to each section id.
- Then, in order, each of these placeholder comments on its own line, exactly as written: {placeholders}
- After the placeholders: a "Key results" block (numbers and sources from the plan), "Limitations", a working 3-question quiz with instant feedback, and a footer saying "Generated by Kimi on Nebius Token Factory from the paper. Check the original paper for authoritative details."

Audience: {audience}

LESSON PLAN:
{plan}

{meta}

Keep the shell under ~450 lines; spend the effort on typography and layout, not on extra features.

Output only the complete HTML document in one ```html block."""

SECTION_PROMPT = """You are writing ONE section of an interactive explainer. The page shell (design system, hero, quiz) is being written by someone else at the same time against this contract:

{contract}

Write section "{sid}":
```json
{section}
```

Output exactly one element: <section id="{sid}" class="lesson"> ... </section>. Inside it:
- an <h2>, then the prose in <div class="prose"> (wrap glossary terms as .term spans; use $$...$$ inside <div class="eq"> if the plan has an equation)
- the interactive in <div class="widget"> using the contract classes, drawn with SVG or canvas, with real labelled controls and a live .readout
- optional <style> whose selectors are ALL scoped under #{sid}
- one <script> containing an IIFE wrapped in try/catch that finds its elements via document.getElementById("{sid}") and animates only through ExplainerKit.loop or ExplainerKit.onVisible. Use ids/classes prefixed with "{sid}-" to avoid collisions with other sections.

Make this widget the best version of itself: it should teach the insight in the plan through play.
Budget: keep the whole section under ~350 lines. Prefer one rich, well-made widget over many controls.
Ground every claim in the paper and cite it (e.g. "§3.2"). Only use numbers that appear in the paper.

Audience: {audience}

Full lesson plan for context (write only section {sid}):
{plan}

{paper}

Output only the section in one ```html block."""

SECTION_PAPER_CHARS = 160_000  # each parallel section call gets up to ~40k tokens of paper

KIT_JS = """<script>
/* ExplainerKit: tiny shared helpers injected by paper_to_interactive_explainer */
window.ExplainerKit = (function () {
  var kit = {};
  kit.onVisible = function (el, start, stop) {
    if (!el) return;
    if (!('IntersectionObserver' in window)) { if (start) start(); return; }
    var on = false;
    new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !on) { on = true; if (start) start(); }
        else if (!e.isIntersecting && on) { on = false; if (stop) stop(); }
      });
    }, { threshold: 0.05 }).observe(el);
  };
  kit.loop = function (el, frame) {
    var id = null, last = 0;
    function tick(t) {
      var dt = last ? Math.min((t - last) / 1000, 0.1) : 0; last = t;
      try { frame(t, dt); } catch (err) { console.warn('ExplainerKit.loop', err); }
      id = requestAnimationFrame(tick);
    }
    kit.onVisible(el, function () { if (id === null) { last = 0; id = requestAnimationFrame(tick); } },
                      function () { if (id !== null) { cancelAnimationFrame(id); id = null; } });
  };
  kit.color = function (name, fallback) {
    var n = name.indexOf('--') === 0 ? name : '--' + name;
    var v = getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    return v || fallback || '#888';
  };
  kit.fitCanvas = function (canvas, height) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = canvas.clientWidth || (canvas.parentElement && canvas.parentElement.clientWidth) || 640;
    var h = height || canvas.clientHeight || Math.round(w * 0.56);
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    canvas.style.width = '100%'; canvas.style.height = h + 'px';
    var ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, width: w, height: h };
  };
  function initTerms() {
    var tip = document.createElement('div');
    tip.className = 'kit-tip'; tip.setAttribute('role', 'tooltip'); document.body.appendChild(tip);
    function show(t) {
      tip.textContent = t.getAttribute('data-def');
      var r = t.getBoundingClientRect();
      tip.style.left = Math.max(8, Math.min(window.innerWidth - 308, r.left)) + 'px';
      tip.style.top = (r.bottom + window.scrollY + 8) + 'px';
      tip.classList.add('on');
    }
    function hide() { tip.classList.remove('on'); }
    document.addEventListener('mouseover', function (e) { var t = e.target.closest && e.target.closest('.term[data-def]'); if (t) show(t); else hide(); });
    document.addEventListener('focusin', function (e) { var t = e.target.closest && e.target.closest('.term[data-def]'); if (t) show(t); });
    document.addEventListener('click', function (e) { var t = e.target.closest && e.target.closest('.term[data-def]'); if (t) show(t); else hide(); });
    document.querySelectorAll('.term[data-def]').forEach(function (t) { if (!t.hasAttribute('tabindex')) t.setAttribute('tabindex', '0'); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initTerms); else initTerms();
  // Sections are written in parallel and don't agree on math delimiters, so render them all
  // once every script (including KaTeX from the shell) has loaded.
  window.addEventListener('load', function () {
    if (typeof window.renderMathInElement !== 'function') return;
    try {
      window.renderMathInElement(document.body, {
        delimiters: [
          { left: '$$', right: '$$', display: true }, { left: '\\\\[', right: '\\\\]', display: true },
          { left: '\\\\(', right: '\\\\)', display: false }, { left: '$', right: '$', display: false }
        ],
        ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option', 'input', 'canvas', 'svg'],
        throwOnError: false
      });
    } catch (err) { console.warn('ExplainerKit math', err); }
  });
  return kit;
})();
</script>
<style>
.kit-tip{position:absolute;z-index:1000;max-width:300px;padding:8px 11px;border-radius:8px;font-size:14px;line-height:1.45;
  background:var(--tip-bg,#151515);color:var(--tip-fg,#fff);box-shadow:0 8px 28px rgba(0,0,0,.22);opacity:0;pointer-events:none;
  transform:translateY(-2px);transition:opacity .12s,transform .12s}
.kit-tip.on{opacity:1;transform:none}
.term[data-def]{cursor:help}
</style>
"""

PATCH_INSTRUCTIONS = """Return your fix as one or more edit blocks in exactly this format:

<<<<<<< SEARCH
exact lines copied from the current file
=======
replacement lines
>>>>>>> REPLACE

Each SEARCH must match the current file exactly (including indentation) and appear only once. Keep edits minimal and don't touch unrelated code. If the change is too large for edits, instead return the complete new file in one ```html block."""


@dataclass
class Version:
    n: int
    label: str
    html: str
    qa_errors: list[str] | None = None  # None = not tested


Emit = Callable[..., None]


def _image_part(jpeg: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}}


def _paper_block(paper: Paper) -> str:
    return (f"PAPER: {paper.title}\nAUTHORS: {', '.join(paper.authors) or 'see text'}\nLINK: {paper.source_url or 'n/a'}\n"
            f"ABSTRACT: {paper.abstract or 'see text'}\n\nFULL TEXT ({paper.page_count} pages):\n{paper.text}")


def parse_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("Kimi's plan wasn't valid JSON")
    return json.loads(text[start : end + 1])


def extract_html(text: str) -> str:
    fence = re.search(r"```html\s*\n(.*?)(?:```|$)", text, re.S | re.I)
    html = fence.group(1) if fence else text
    start = html.lower().find("<!doctype")
    if start < 0:
        start = html.lower().find("<html")
    return html[max(start, 0):].strip()


def extract_section(text: str, sid: str) -> str:
    fence = re.search(r"```html\s*\n(.*?)(?:```|$)", text, re.S | re.I)
    body = (fence.group(1) if fence else text).strip()
    start = body.find("<section")
    end = body.rfind("</section>")
    if start >= 0 and end > start:
        # Keep trailing <script>/<style> that some answers put after the section.
        tail = body[end + len("</section>"):]
        extras = "".join(re.findall(r"<(?:script|style)\b.*?</(?:script|style)>", tail, re.S))
        return body[start : end + len("</section>")] + extras
    return f'<section id="{sid}" class="lesson">\n{body}\n</section>'


def fallback_section(sec: dict) -> str:
    sid, esc = sec["id"], htmllib.escape
    return (f'<section id="{sid}" class="lesson"><h2>{esc(sec.get("heading", ""))}</h2>'
            f'<div class="prose"><p>{esc(sec.get("explanation", ""))}</p></div></section>')


def assemble(shell: str, bodies: dict[str, str]) -> str:
    html, leftovers = shell, []
    for sid, body in bodies.items():
        pattern = re.compile(rf"<!--\s*SECTION:\s*{re.escape(sid)}\s*-->")
        if pattern.search(html):
            html = pattern.sub(lambda _m, b=body: b, html, count=1)
        else:
            leftovers.append(body)
    if leftovers:
        joined = "\n".join(leftovers)
        for anchor in ("</main>", "<footer", "</body>"):
            i = html.find(anchor)
            if i >= 0:
                html = html[:i] + joined + "\n" + html[i:]
                break
        else:
            html += joined
    i = html.lower().find("</head>")
    return html[:i] + KIT_JS + html[i:] if i >= 0 else KIT_JS + html


def apply_patches(html: str, reply: str) -> tuple[str, int, list[str]]:
    """Apply SEARCH/REPLACE blocks. Returns (new_html, applied, failed_searches)."""
    blocks = re.findall(r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE", reply, re.S)
    applied, failed = 0, []
    for search, replace in blocks:
        if html.count(search) == 1:
            html = html.replace(search, replace)
            applied += 1
            continue
        # Fall back to a whitespace-insensitive line match.
        lines = html.split("\n")
        target = [ln.strip() for ln in search.split("\n")]
        hit = None
        for i in range(len(lines) - len(target) + 1):
            if [ln.strip() for ln in lines[i : i + len(target)]] == target:
                if hit is not None:
                    hit = -1
                    break
                hit = i
        if hit is not None and hit >= 0:
            lines[hit : hit + len(target)] = replace.split("\n")
            html = "\n".join(lines)
            applied += 1
        else:
            failed.append(search[:200])
    return html, applied, failed


def static_check(html: str, plan: dict | None) -> list[str]:
    issues = []
    low = html.lower()
    if "</html>" not in low:
        issues.append("The document is truncated: it has no closing </html> tag.")
    if low.count("<script") != low.count("</script>"):
        issues.append("Unbalanced <script> tags.")
    if plan:
        want = len(plan.get("sections", []))
        got = low.count("<section")
        if want and got < want:
            issues.append(f"The plan has {want} sections but the page only has {got} <section> elements.")
    return issues


def qa_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def browser_check(html: str) -> tuple[list[str], bytes | None]:
    """Load the page in headless Chromium (separate process) and collect JS errors."""
    with tempfile.TemporaryDirectory(prefix="explainer_qa_") as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(html)
        shot = Path(tmp) / "shot.png"
        try:
            proc = subprocess.run([sys.executable, str(QA_SCRIPT), str(page), str(shot)],
                                  capture_output=True, text=True, timeout=120)
            data = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception as exc:
            return [f"(self-test could not run: {exc})"], None
        return data.get("errors", []), shot.read_bytes() if shot.exists() else None


class ExplainerAgent:
    def __init__(self, client: OpenAI, model: str, effort: str, emit: Emit, build_effort: str = "low"):
        # The lesson plan does the heavy thinking; the parallel writers mostly write code,
        # so they default to low reasoning effort, which is several times faster.
        self.client, self.model, self.effort, self.emit = client, model, effort, emit
        self.build_effort = build_effort

    def _ask(self, messages: list[dict], stage: str, max_tokens: int = 32000):
        self.emit("stage", stage)
        res = stream_chat(self.client, self.model, messages, reasoning_effort=self.effort, max_tokens=max_tokens,
                          on_delta=lambda kind, text: self.emit("delta", kind, text))
        self.emit("usage", res.usage)
        return res

    def plan(self, paper: Paper, audience: str) -> dict:
        content = [_image_part(img) for _, img in paper.figures]
        content.append({"type": "text", "text": (
            f"The figure images above are renders of pages {', '.join(str(p) for p, _ in paper.figures) or 'none'}.\n"
            f"Audience: {AUDIENCES[audience]}\n\n{_paper_block(paper)}")})
        messages = [{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": content}]
        res = self._ask(messages, f"Kimi is reading all {paper.page_count} pages and {len(paper.figures)} figure pages")
        return parse_json(res.content)

    def _call(self, messages: list[dict], max_tokens: int, on_delta=None) -> tuple[str, dict]:
        """Non-UI call (safe from worker threads). Continues if the output cap is hit."""
        res = stream_chat(self.client, self.model, messages, reasoning_effort=self.build_effort,
                          max_tokens=max_tokens, on_delta=on_delta)
        text, usage = res.content, dict(res.usage or {})
        for _ in range(2):
            if res.finish_reason != "length":
                break
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": "You were cut off. Continue exactly where you stopped. Output only the remaining HTML, no repetition, no code fence."},
            ]
            res = stream_chat(self.client, self.model, messages, reasoning_effort=self.build_effort,
                              max_tokens=max_tokens, on_delta=on_delta)
            text += res.content
            usage["total_tokens"] = usage.get("total_tokens", 0) + (res.usage or {}).get("total_tokens", 0)
        return text, usage

    def build(self, paper: Paper, plan: dict, audience: str) -> str:
        """Write the shell and every section at the same time, then assemble them.

        All calls share a fixed contract (CSS class names + an ExplainerKit JS
        helper we inject ourselves), so they can run in parallel and still fit.
        """
        sections = plan.get("sections", [])
        ids = [s.get("id") or f"s{i + 1}" for i, s in enumerate(sections)]
        for sec, sid in zip(sections, ids):
            sec["id"] = sid
        plan_json = json.dumps(plan, indent=1)
        paper_text = _paper_block(paper)
        if len(paper_text) > SECTION_PAPER_CHARS:
            paper_text = paper_text[:SECTION_PAPER_CHARS] + "\n[...truncated]"

        shell_msgs = [{"role": "system", "content": BUILD_SYSTEM}, {"role": "user", "content": SHELL_PROMPT.format(
            contract=KIT_CONTRACT, placeholders=" ".join(f"<!--SECTION:{i}-->" for i in ids),
            audience=AUDIENCES[audience], plan=plan_json, link=paper.source_url or "none",
            meta=f"PAPER: {paper.title}\nAUTHORS: {', '.join(paper.authors)}\nABSTRACT: {paper.abstract}")}]
        jobs = {"shell": shell_msgs}
        for sec in sections:
            jobs[sec["id"]] = [{"role": "system", "content": BUILD_SYSTEM}, {"role": "user", "content": SECTION_PROMPT.format(
                contract=KIT_CONTRACT, sid=sec["id"], section=json.dumps(sec, indent=1), plan=plan_json,
                audience=AUDIENCES[audience], paper=paper_text)}]

        progress = {k: {"label": "Page shell" if k == "shell" else next(s["heading"] for s in sections if s["id"] == k),
                        "phase": "queued", "chars": 0, "think": 0} for k in jobs}

        def run(key: str, msgs: list[dict]) -> tuple[str, dict]:
            def on_delta(kind, text):
                p = progress[key]
                if kind == "content":
                    p["phase"] = "writing"
                    p["chars"] += len(text)
                else:
                    p["think"] += len(text)
            progress[key]["phase"] = "thinking"
            try:
                text, usage = self._call(msgs, max_tokens=20000, on_delta=on_delta)
            except Exception:
                progress[key]["phase"] = "retrying"
                text, usage = self._call(msgs, max_tokens=20000, on_delta=on_delta)
            progress[key]["phase"] = "done"
            return text, usage

        self.emit("stage", f"Kimi is building the page: shell + {len(sections)} sections in parallel")
        results: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {pool.submit(run, k, m): k for k, m in jobs.items()}
            while any(not f.done() for f in futures):
                self.emit("sections", {k: dict(v) for k, v in progress.items()})
                time.sleep(0.5)
            for f, key in futures.items():
                try:
                    text, usage = f.result()
                    results[key] = text
                    self.emit("usage", usage)
                except Exception as exc:
                    progress[key]["phase"] = "failed"
                    self.emit("note", f"{progress[key]['label']} failed ({exc}); using a plain-text fallback")
        self.emit("sections", {k: dict(v) for k, v in progress.items()})

        if "shell" not in results:
            raise RuntimeError("Kimi couldn't write the page shell. Try again.")
        bodies = {}
        for sec in sections:
            sid = sec["id"]
            bodies[sid] = extract_section(results[sid], sid) if sid in results else fallback_section(sec)
        return assemble(extract_html(results["shell"]), bodies)

    def patch(self, html: str, problem: str, stage: str) -> tuple[str, str]:
        """Ask for SEARCH/REPLACE edits (or a full rewrite) and apply them."""
        messages = [
            {"role": "system", "content": BUILD_SYSTEM},
            {"role": "user", "content": f"Current file:\n```html\n{html}\n```\n\n{problem}\n\n{PATCH_INSTRUCTIONS}"},
        ]
        reply = self._ask(messages, stage, max_tokens=64000).content
        if "<<<<<<< SEARCH" not in reply and "```html" in reply:
            return extract_html(reply), "rewrote the page"
        new_html, applied, failed = apply_patches(html, reply)
        if failed and not applied:
            raise RuntimeError(f"Kimi's {len(failed)} edit(s) didn't match the file. Try rephrasing the request.")
        return new_html, f"applied {applied} edit(s)" + (f", {len(failed)} didn't match" if failed else "")

    def self_test(self, html: str, plan: dict, use_browser: bool, max_fixes: int = 2) -> tuple[str, list[str] | None]:
        errors: list[str] | None = None
        for attempt in range(max_fixes + 1):
            errors = static_check(html, plan)
            if use_browser:
                self.emit("stage", "Self-test: loading the page in headless Chrome")
                browser_errors, shot = browser_check(html)
                errors += browser_errors
                if shot:
                    self.emit("screenshot", shot)
            self.emit("qa", errors)
            if not errors or attempt == max_fixes:
                break
            problem = "The page has these problems:\n" + "\n".join(f"- {e}" for e in errors[:15]) + "\nFix the root causes."
            html, summary = self.patch(html, problem, f"Kimi is fixing {len(errors)} problem(s) (pass {attempt + 1})")
            self.emit("note", summary)
        return html, errors
