"""Napkin -> 3D Print: sketch a part, Kimi K3.1 Pro on Nebius models it, you print it."""

from __future__ import annotations

import io
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from PIL import Image

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")

from cad_agent import Iteration, NapkinAgent, execute  # noqa: E402
from kimi import PREFERRED_MODEL, available_kimi_models, get_client, image_part, label  # noqa: E402
from viewer import viewer_html  # noqa: E402

SAMPLES = {
    "Phone stand": ("samples/phone_stand.png", "Desk stand for a phone, about 75 mm wide. Leave a slot at the front for a charging cable."),
    "Wall hook": ("samples/wall_hook.png", "Wall hook for a backpack, mounted with two screws."),
    "Pen cup": ("samples/pen_cup.png", "Hexagonal pen holder with a small tray on one side."),
}
FILAMENTS = {"Orange PLA": "#f28c33", "Lime PLA": "#b7f34a", "Snow PLA": "#e9ece8", "Graphite PLA": "#4a4f4c", "Ocean PETG": "#2f8fd8"}
PLA_DENSITY_G_CM3 = 1.24

st.set_page_config(page_title="Napkin → 3D Print", page_icon="✏️", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; max-width: 1400px;}
    .hero h1 {font-size: 2.3rem; margin-bottom: .1rem; letter-spacing: -.02em;}
    .hero p {color: #8b938c; margin-top: 0; font-size: 1.02rem;}
    .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem;
           border:1px solid rgba(127,127,127,.35); margin-right:6px;}
    .pill.ok {border-color:#57b26a; color:#57b26a;}
    .pill.warn {border-color:#d9a13b; color:#d9a13b;}
    .thinking {font-family: ui-monospace, Menlo, monospace; font-size: .78rem; color:#8b938c;
               white-space: pre-wrap; max-height: 9.5rem; overflow: hidden; border-left: 2px solid #b7f34a;
               padding-left: .7rem;}
    </style>
    <div class="hero">
      <h1>✏️ Napkin → 3D Print</h1>
      <p>Sketch a part on paper. Kimi K3.1 Pro reads it, writes parametric CadQuery, checks its own render against your drawing, and hands you a printable STL.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

ss = st.session_state
ss.setdefault("history", [])
ss.setdefault("current", None)  # the Iteration shown in the viewer
ss.setdefault("sketch_bytes", None)
ss.setdefault("tokens", 0)


@st.cache_resource(show_spinner=False)
def client_and_models():
    client = get_client()
    return client, available_kimi_models(client)


# ---------------------------------------------------------------- sidebar
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
    rounds = st.slider("Self-review rounds", 1, 4, 3, help="How many times Kimi may compare its render with your sketch and revise.")
    st.subheader("Print")
    filament = st.selectbox("Filament", list(FILAMENTS))
    st.divider()
    st.caption(f"Tokens used this session: {ss.tokens:,}")
    st.caption("Generated CadQuery runs locally in a subprocess with an import allowlist. Review the code before running it outside this demo.")


# ---------------------------------------------------------------- input
left, right = st.columns([0.9, 1.4], gap="large")

with left:
    tab_upload, tab_camera, tab_sample = st.tabs(["Upload sketch", "Camera", "Samples"])
    with tab_upload:
        up = st.file_uploader("Photo or scan of your sketch", type=["png", "jpg", "jpeg", "webp", "heic"], label_visibility="collapsed")
        if up:
            ss.sketch_bytes = up.getvalue()
    with tab_camera:
        cam = st.camera_input("Snap your napkin", label_visibility="collapsed")
        if cam:
            ss.sketch_bytes = cam.getvalue()
    with tab_sample:
        cols = st.columns(len(SAMPLES))
        for col, (name, (path, hint)) in zip(cols, SAMPLES.items()):
            with col:
                st.image(str(APP_DIR / path), width="stretch")
                if st.button(name, width="stretch"):
                    ss.sketch_bytes = (APP_DIR / path).read_bytes()
                    ss.notes = hint

    if ss.sketch_bytes:
        st.image(ss.sketch_bytes, caption="Your sketch", width="stretch")

    notes = st.text_area("Notes (optional)", key="notes", placeholder="e.g. fits an iPhone 16 at 60°, M4 screws, 3 mm walls", height=80)
    go = st.button("✨ Model it", type="primary", width="stretch", disabled=not ss.sketch_bytes)

# ---------------------------------------------------------------- live progress
with right:
    viewer_slot = st.empty()
    status_slot = st.empty()
    think_slot = st.empty()


def run_with_progress(fn):
    """Run an agent call while streaming its stages and reasoning into the UI."""
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
                shown = buf["content"] or buf["reasoning"]
                head = "writing code" if buf["content"] else "thinking"
                think_slot.markdown(f'<div class="thinking">{head} · …{_esc(shown[-700:])}</div>', unsafe_allow_html=True)
            elif event == "repair":
                status.write(f"🔧 Build error, sending traceback back to Kimi: `{args[0].splitlines()[0][:140]}`")
            elif event == "verdict":
                status.write("✅ Kimi signed off on the model" if args[0] == "PASS" else "🔁 Kimi found issues and is revising")
            elif event == "iteration":
                it: Iteration = args[0]
                if it.build.ok:
                    status.write(f"Built v{it.n}: {' × '.join(f'{v:.0f}' for v in it.build.size)} mm")
                    viewer_slot.image(it.build.render_png, caption=f"v{it.n} render", width="stretch")
            elif event == "usage" and args[0]:
                ss.tokens += args[0].get("total_tokens", 0)

        agent = NapkinAgent(client, model, effort, emit)
        try:
            result = fn(agent)
            status.update(label="Done", state="complete", expanded=False)
        except Exception as exc:
            status.update(label=f"Failed: {exc}", state="error")
            result = None
    think_slot.empty()
    return result


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sketch_part() -> dict:
    return image_part(Image.open(io.BytesIO(ss.sketch_bytes)))


if go:
    history = run_with_progress(lambda agent: agent.design(sketch_part(), notes, rounds))
    if history:
        ss.history = history
        good = [h for h in history if h.build.ok]
        ss.current = good[-1] if good else history[-1]
    st.rerun()

# ---------------------------------------------------------------- result
cur: Iteration | None = ss.current
with right:
    if cur is None:
        viewer_slot.info("Upload a sketch (or pick a sample) and hit **Model it**. Your part will print itself in here.")
    elif not cur.build.ok:
        viewer_slot.error("Kimi couldn't get this design to build. Try again, add notes, or lower the complexity.")
        with st.expander("Last build error"):
            st.code(cur.build.error)
    else:
        b = cur.build
        with viewer_slot.container():
            components.html(viewer_html(b.stl, FILAMENTS[filament], b.size), height=530)
        grams = b.volume / 1000 * PLA_DENSITY_G_CM3
        m1, m2, m3, m4 = st.columns([1.7, 1.1, 1, 0.7])
        m1.metric("Size (mm)", " × ".join(f"{v:.0f}" for v in b.size))
        m2.metric("Volume", f"{b.volume / 1000:.1f} cm³")
        m3.metric("Solid PLA", f"{grams:.0f} g", help="At 100% infill; a 20% infill print uses roughly a third of this.")
        m4.metric("Version", f"v{cur.n}")
        st.markdown(
            f'<span class="pill {"ok" if b.watertight else "warn"}">{"watertight" if b.watertight else "not watertight"}</span>'
            f'<span class="pill {"ok" if b.solids == 1 else "warn"}">{b.solids} solid{"s" if b.solids != 1 else ""}</span>'
            f'<span class="pill {"ok" if b.valid else "warn"}">{"valid B-rep" if b.valid else "B-rep warnings"}</span>',
            unsafe_allow_html=True,
        )
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇ STL", b.stl, "napkin_part.stl", width="stretch", type="primary")
        d2.download_button("⬇ STEP", b.step, "napkin_part.step", width="stretch")
        d3.download_button("⬇ CadQuery .py", cur.code, "napkin_part.py", width="stretch")

if cur is not None and cur.build.ok:
    st.divider()
    p_col, e_col = st.columns([1, 1], gap="large")

    # Sliders re-run the same code locally: no model call, instant-ish.
    with p_col:
        st.subheader("🎛️ Parameters")
        st.caption("These come straight from the `PARAMS` dict Kimi wrote. Changing them rebuilds locally without calling the model.")
        spec = cur.build.spec
        with st.form("params"):
            values = {}
            for name, cfg in spec.items():
                is_int = cfg.get("type") == "int"
                cast = int if is_int else float
                lo = cast(cfg.get("min", 0))
                hi = cast(cfg.get("max", max(cfg["value"] * 3, 1)))
                step = cast(cfg.get("step", 1 if is_int else 0.5)) or cast(1)
                if hi <= lo:
                    hi = lo + step
                val = cast(cur.build.params.get(name, cfg["value"]))
                unit = f" ({cfg['unit']})" if cfg.get("unit") else ""
                values[name] = st.slider(cfg.get("label", name) + unit, lo, hi, min(max(val, lo), hi), step)
            if st.form_submit_button("Rebuild", width="stretch"):
                with st.spinner("Rebuilding…"):
                    build = execute(cur.code, values)
                if build.ok:
                    ss.current = Iteration(cur.n, "tweak", cur.code, cur.notes, build, verdict=cur.verdict)
                    st.rerun()
                else:
                    st.error("Those values don't build:\n\n" + build.error.splitlines()[0])

    with e_col:
        st.subheader("💬 Ask for a change")
        st.caption("Kimi edits the CadQuery code, rebuilds, and fixes its own errors.")
        with st.form("edit", clear_on_submit=True):
            request = st.text_input("Change", placeholder="Add a 10 mm cable hole through the back", label_visibility="collapsed")
            submitted = st.form_submit_button("Apply change", width="stretch")
        if submitted and request.strip():
            n = max(h.n for h in ss.history) + 1
            it = run_with_progress(lambda agent: agent.edit(sketch_part(), cur.code, cur.build.size, request, n))
            if it is not None:
                ss.history.append(it)
                if it.build.ok:
                    ss.current = it
                else:
                    st.error("Kimi couldn't make that change build. Your previous version is still loaded.")
            st.rerun()

# ---------------------------------------------------------------- timeline
if ss.history:
    st.divider()
    st.subheader("🧭 Design timeline")
    st.caption("Every version Kimi built, with what it saw and what it changed.")
    shown = [h for h in ss.history if h.build.ok]
    cols = st.columns(max(len(shown), 1))
    for col, it in zip(cols, shown):
        with col:
            badge = {"PASS": "✅ signed off", "REVISE": "🔁 revised"}.get(it.verdict, "")
            st.image(it.build.render_png, caption=f"v{it.n} · {it.kind} {badge}", width="stretch")
    for it in ss.history:
        with st.expander(f"v{it.n} · {it.kind}" + (f" · {len(it.repairs)} build fix(es)" if it.repairs else "")):
            if it.notes:
                st.markdown(it.notes)
            for i, err in enumerate(it.repairs, 1):
                st.caption(f"Build error {i}, fixed by Kimi:")
                st.code(err.splitlines()[0] if err else "", language="text")
            st.code(it.code, language="python")
