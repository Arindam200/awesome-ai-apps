"""Paper -> Interactive Explainer: Kimi K3.1 Pro on Nebius reads a whole paper and builds a playable explainer."""

from __future__ import annotations

import re
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")

from explainer_agent import AUDIENCES, ExplainerAgent, Version, qa_available  # noqa: E402
from kimi import PREFERRED_MODEL, available_kimi_models, get_client, label  # noqa: E402
from paper import Paper, fetch_arxiv, load_pdf, parse_arxiv_id  # noqa: E402

OUTPUT_DIR = APP_DIR / "outputs"
EXAMPLES = {
    "Attention Is All You Need": "1706.03762",
    "Denoising Diffusion (DDPM)": "2006.11239",
    "LoRA": "2106.09685",
    "Chain-of-Thought": "2201.11903",
}

st.set_page_config(page_title="Paper → Interactive Explainer", page_icon="📄", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; max-width: 1400px;}
    .hero h1 {font-size: 2.3rem; margin-bottom: .1rem; letter-spacing: -.02em;}
    .hero p {color: #8b938c; margin-top: 0; font-size: 1.02rem;}
    .card {border: 1px solid rgba(127,127,127,.25); border-radius: 12px; padding: .8rem 1rem; height: 100%;}
    .card h4 {margin: 0 0 .3rem 0; font-size: 1rem;}
    .card .kind {font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: #b7f34a;}
    .card p {font-size: .88rem; color: #8b938c; margin: .3rem 0 0 0;}
    .ticker {font-family: ui-monospace, Menlo, monospace; font-size: .74rem; color:#8b938c; white-space: pre-wrap;
             max-height: 11rem; overflow: hidden; border-left: 2px solid #b7f34a; padding-left: .7rem;}
    .tiles {display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: .6rem; margin: .4rem 0 1rem;}
    .tile {border: 1px solid rgba(127,127,127,.25); border-radius: 10px; padding: .6rem .75rem; display: flex; flex-direction: column; gap: .15rem;}
    .tile b {font-size: .85rem; font-weight: 600;}
    .tile i {font-style: normal; font-size: .75rem; color: #8b938c; font-variant-numeric: tabular-nums;}
    .tile.writing {border-color: #b7f34a;}
    .tile.done {border-color: #57b26a;}
    .tile.failed {border-color: #d9a13b;}
    </style>
    <div class="hero">
      <h1>📄 Paper → Interactive Explainer</h1>
      <p>Drop in a paper. Kimi K3.1 Pro reads all of it, figures included, designs a lesson, and builds a Distill-style explainer you can actually play with.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

ss = st.session_state
ss.setdefault("paper", None)
ss.setdefault("plan", None)
ss.setdefault("versions", [])
ss.setdefault("tokens", 0)
ss.setdefault("source", "")


@st.cache_resource(show_spinner=False)
def client_and_models():
    client = get_client()
    return client, available_kimi_models(client)


with st.sidebar:
    st.subheader("Model")
    try:
        client, models = client_and_models()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    model = st.selectbox("Kimi model on Nebius", models, format_func=label)
    if model != PREFERRED_MODEL and PREFERRED_MODEL not in models:
        st.caption(f"{label(PREFERRED_MODEL)} isn't enabled for this API key yet, so the app is using {label(model)}.")
    effort = st.select_slider("Reasoning effort", ["low", "high", "max"], value="high")
    audience = st.selectbox("Audience", list(AUDIENCES), index=1)
    can_qa = qa_available()
    use_browser = st.toggle("Self-test in headless Chrome", value=can_qa, disabled=not can_qa,
                            help="Loads the page, collects JS errors and lets Kimi patch them." if can_qa
                            else "Install the qa extra to enable: uv sync --extra qa && uv run playwright install chromium")
    st.divider()
    st.caption(f"Tokens used this session: {ss.tokens:,}")

# ---------------------------------------------------------------- input
c1, c2 = st.columns([1.3, 1], gap="large")
with c1:
    src = st.text_input("arXiv link or ID", value=ss.source, placeholder="https://arxiv.org/abs/1706.03762")
    ex_cols = st.columns(len(EXAMPLES))
    for col, (name, aid) in zip(ex_cols, EXAMPLES.items()):
        if col.button(name, width="stretch"):
            ss.source = aid
            st.rerun()
with c2:
    pdf = st.file_uploader("…or upload a PDF", type=["pdf"])

go = st.button("✨ Build the explainer", type="primary", disabled=not (src or pdf))

status_slot = st.empty()
ticker_slot = st.empty()
plan_slot = st.container()


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def show_plan(plan: dict, target=None) -> None:
    with target or plan_slot:
        st.markdown(f"### {plan.get('title', 'Lesson plan')}")
        st.caption(plan.get("hook", ""))
        sections = plan.get("sections", [])
        cols = st.columns(min(len(sections), 3) or 1)
        for i, sec in enumerate(sections):
            inter = sec.get("interactive", {})
            with cols[i % len(cols)]:
                st.markdown(
                    f'<div class="card"><div class="kind">{esc(inter.get("kind", ""))[:60]}</div>'
                    f'<h4>{i + 1}. {esc(sec.get("heading", ""))}</h4>'
                    f'<p><b>{esc(inter.get("title", ""))}</b> · {esc(inter.get("why_it_teaches", ""))}</p></div>',
                    unsafe_allow_html=True,
                )
                st.write("")


def run_agent(fn):
    buf = {"reasoning": "", "content": ""}
    with status_slot.status("Starting…", expanded=True) as status:

        def emit(event, *args):
            if event == "stage":
                status.update(label=args[0])
                buf["reasoning"], buf["content"] = "", ""
            elif event == "delta":
                kind, text = args
                buf[kind] += text
                now = time.monotonic()
                if now - buf.get("t", 0) < 0.25:  # throttle UI updates
                    return
                buf["t"] = now
                if buf["content"]:
                    head, shown = f"writing · {len(buf['content']):,} chars", buf["content"][-900:]
                else:
                    head, shown = "thinking", buf["reasoning"][-700:]
                ticker_slot.markdown(f'<div class="ticker">{head}\n…{esc(shown)}</div>', unsafe_allow_html=True)
            elif event == "sections":
                tiles = []
                for key, p in args[0].items():
                    icon = {"queued": "⏳", "thinking": "🧠", "writing": "✍️", "retrying": "🔁", "done": "✅", "failed": "⚠️"}[p["phase"]]
                    if p["chars"]:
                        detail = f"writing · {p['chars']:,} chars"
                    elif p.get("think"):
                        detail = f"thinking · {p['think']:,} chars"
                    else:
                        detail = p["phase"]
                    tiles.append(f'<div class="tile {p["phase"]}"><span>{icon}</span><b>{esc(p["label"])[:48]}</b><i>{detail}</i></div>')
                ticker_slot.markdown(f'<div class="tiles">{"".join(tiles)}</div>', unsafe_allow_html=True)
            elif event == "qa":
                errs = args[0]
                status.write("🧪 Self-test passed: no errors" if not errs else f"🧪 Self-test found {len(errs)} problem(s)")
                for e in errs[:5]:
                    status.caption(e[:200])
            elif event == "note":
                status.write(f"🔧 {args[0]}")
            elif event == "screenshot":
                pass
            elif event == "usage" and args[0]:
                ss.tokens += args[0].get("total_tokens", 0)

        agent = ExplainerAgent(client, model, effort, emit)
        try:
            out = fn(agent, status)
            status.update(label="Done", state="complete", expanded=False)
        except Exception as exc:
            status.update(label=f"Failed: {exc}", state="error")
            out = None
    ticker_slot.empty()
    return out


def save(html: str, paper: Paper, n: int) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", paper.title.lower()).strip("-")[:60] or "explainer"
    path = OUTPUT_DIR / f"{slug}-v{n}.html"
    path.write_text(html)
    return path


if go:
    def pipeline(agent: ExplainerAgent, status):
        status.update(label="Fetching the paper")
        if pdf is not None:
            paper = load_pdf(pdf.getvalue(), title=Path(pdf.name).stem.replace("_", " "))
        else:
            aid = parse_arxiv_id(src)
            if not aid:
                raise ValueError("That doesn't look like an arXiv link or ID")
            paper = fetch_arxiv(aid)
        status.write(f"📄 **{paper.title}** · {paper.page_count} pages · {len(paper.figures)} figure pages · ~{len(paper.text) // 4:,} tokens of text")
        ss.paper, ss.plan, ss.versions = paper, None, []

        plan = agent.plan(paper, audience)
        ss.plan = plan
        status.write(f"🗺️ Lesson plan: {len(plan.get('sections', []))} sections, each with its own interactive")
        show_plan(plan)

        html = agent.build(paper, plan, audience)
        status.write(f"🏗️ Built the page: {len(html):,} characters")
        html, errors = agent.self_test(html, plan, use_browser)
        return Version(1, "first build", html, errors if use_browser else None)

    v = run_agent(pipeline)
    if v:
        ss.versions = [v]
        st.rerun()

# ---------------------------------------------------------------- result
if ss.plan and not go:
    show_plan(ss.plan, st.expander("🗺️ Lesson plan Kimi designed", expanded=not ss.versions))

if ss.versions:
    paper: Paper = ss.paper
    labels = [f"v{v.n} · {v.label}" for v in ss.versions]
    pick = st.radio("Version", labels, index=len(labels) - 1, horizontal=True, label_visibility="collapsed")
    cur: Version = ss.versions[labels.index(pick)]

    path = save(cur.html, paper, cur.n)
    m1, m2, m3, m4 = st.columns([1, 1, 1, 1.3])
    m1.metric("Sections", cur.html.lower().count("<section"))
    m2.metric("Page size", f"{len(cur.html) / 1024:.0f} KB")
    m3.metric("Self-test", "not run" if cur.qa_errors is None else ("0 errors" if not cur.qa_errors else f"{len(cur.qa_errors)} issues"))
    with m4:
        st.download_button("⬇ Download explainer.html", cur.html, path.name, mime="text/html", type="primary", width="stretch")
        st.caption(f"Saved to `{path.relative_to(APP_DIR)}`")

    components.html(cur.html, height=900, scrolling=True)

    st.subheader("💬 Refine it")
    with st.form("refine", clear_on_submit=True):
        req = st.text_input("What should change?", placeholder="Let me type my own sentence into the attention widget",
                            label_visibility="collapsed")
        submitted = st.form_submit_button("Apply")
    if submitted and req.strip():
        def refine(agent: ExplainerAgent, status):
            html, summary = agent.patch(cur.html, f"The reader asked for this change: \"{req.strip()}\"",
                                        "Kimi is editing the page")
            status.write(f"🔧 {summary}")
            html, errors = agent.self_test(html, ss.plan, use_browser, max_fixes=1)
            return Version(len(ss.versions) + 1, req.strip()[:40], html, errors if use_browser else None)

        v = run_agent(refine)
        if v:
            ss.versions.append(v)
        st.rerun()

    with st.expander("View source"):
        st.code(cur.html, language="html")
