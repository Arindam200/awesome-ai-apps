"""Watch a proactive on-call agent work a shift: nobody types, it acts on events.

streamlit run app.py
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent import RunRecord  # noqa: E402
from runtime import OnCallRuntime  # noqa: E402

st.set_page_config(page_title="Proactive On-Call Agent", page_icon="⏰", layout="wide")
# Lime buttons take deep-blue text (Nebius Token Factory palette, see .streamlit/config.toml).
st.markdown(
    "<style>[data-testid='stBaseButton-primary'], [data-testid='stBaseButton-primary'] p "
    "{color: #052B42 !important; font-weight: 600;}</style>",
    unsafe_allow_html=True,
)

EVENT_ICON = {"deploy": "🚀", "rollback": "⏪", "chat": "💬", "ticket": "🎫", "status": "🌐", "approval": "📱"}
ALERT_ICON = {"critical": "🔥", "warning": "⚠️", "info": "ℹ️"}
RUN_ICON = {"static": "⏰", "follow-up": "🔁", "recurring": "🔄"}
INJECT = {
    "bad_deploy": "💥 Bad checkout deploy",
    "provider_outage": "🌩️ Payments provider outage",
    "ticket": "🎫 Customer ticket",
    "chat": "💬 Team chatter",
}


def md(text: str) -> str:
    """Escape what Streamlit markdown would misread ($ starts LaTeX)."""
    return text.replace("$", "\\$")


def short(v: object, n: int = 90) -> str:
    s = v if isinstance(v, str) else repr(v)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def get_runtime() -> OnCallRuntime:
    if "rt" not in st.session_state:
        st.session_state.rt = OnCallRuntime()
    return st.session_state.rt


# ---- header --------------------------------------------------------------------
st.title("⏰ Proactive On-Call Agent")
st.markdown(
    "Nobody types anything here. A cron server wakes **Kimi K3.1 Pro** every 5 simulated minutes to triage "
    "what happened in the event stream. The agent decides on its own what matters, pages you, asks you to "
    "approve rollbacks, and **schedules its own follow-ups**. It's the "
    "[proactive agents](https://www.langchain.com/blog/proactive-agents) pattern from LangChain, running on "
    "[Nebius Token Factory](https://dub.sh/nebius)."
)

if not os.getenv("NEBIUS_API_KEY"):
    st.error("Set `NEBIUS_API_KEY` in `.env` (copy `.env.example`), then reload this page.")
    st.stop()

rt = get_runtime()


@st.fragment(run_every=2.0)
def memory_panel() -> None:
    """Refreshes on its own: the agent writes memory from the background loop."""
    if rt.memory.notes:
        for note in rt.memory.notes:
            st.caption(md(note))
        if st.button("Forget everything", use_container_width=True):
            rt.memory.clear()
            st.rerun(scope="fragment")
    else:
        st.caption("Empty. The agent saves lessons here with `remember`, and every future shift starts with them.")


# ---- sidebar controls -------------------------------------------------------------
with st.sidebar:
    st.header("Shift controls")
    c1, c2 = st.columns(2)
    if rt.running:
        if c1.button("⏸ Pause", use_container_width=True):
            rt.pause()
            st.rerun()
    elif c1.button("▶ Start shift" if not rt.runs else "▶ Resume", type="primary", use_container_width=True):
        rt.start()
        st.rerun()
    if c2.button("↺ New shift", use_container_width=True):
        rt.pause()
        st.session_state.rt = OnCallRuntime(auto_approve_after=rt.auto_approve_after)
        st.rerun()

    rt.speed = st.slider(
        "Real seconds per simulated minute",
        0.5,
        5.0,
        1.5,
        0.5,
        help="The clock stops while the agent is thinking, so it never misses an event.",
    )
    auto = st.toggle(
        "Simulate the on-call human",
        value=False,
        help="On: rollback requests get approved after 2 simulated minutes. "
        "Off: you approve or deny them on the phone panel.",
    )
    rt.auto_approve_after = 2 if auto else None

    st.subheader("Make trouble")
    st.caption("Lands in the event stream now. The agent sees it at its next wake-up.")
    for key, label in INJECT.items():
        if st.button(label, use_container_width=True, key=f"inject-{key}"):
            rt.inject(key)

    st.subheader("🧠 Long-term memory")
    memory_panel()
    st.divider()
    st.caption(f"Model: `{rt.model_id}` on Nebius Token Factory")


# ---- live view ----------------------------------------------------------------------
def render_run(r: RunRecord) -> None:
    if r.status == "skipped":
        st.caption(f"💤 {r.at:%H:%M} `{r.schedule_id}`: nothing new, stayed asleep (no model call)")
        return
    why = {
        "static": f"schedule `{r.schedule_id}`",
        "follow-up": f"its own follow-up `{r.schedule_id}`",
        "recurring": f"its own recurring watch `{r.schedule_id}`",
    }[r.kind]
    live = " · 🟢 **awake now**" if r.status == "running" else ""
    with st.container(border=True):
        st.markdown(f"{RUN_ICON[r.kind]} **{r.at:%H:%M}** woken by {why}{live}")
        steps = list(r.steps)
        if steps:
            st.code(
                "\n".join(
                    f"→ {s.tool}(" + ", ".join(f"{k}={short(v)}" for k, v in s.args.items()) + ")" for s in steps
                ),
                language=None,
                wrap_lines=True,
            )
        if r.status == "error":
            st.error(r.summary)
        elif r.summary:
            st.markdown(md(r.summary))
        if r.status != "running":
            st.caption(f"{r.seconds:.1f}s · {len(steps)} tool calls · {r.tokens:,} tokens")


@st.fragment(run_every=1.0)
def live_view() -> None:
    rt.heartbeat()
    w = rt.world
    runs = list(rt.runs)
    notes = list(rt.desk.notifications)

    if rt.error:
        st.error(f"The loop stopped: {rt.error}")
    if not runs and not rt.running:
        st.info(
            "Press **▶ Start shift** in the sidebar. The scripted morning runs 09:00 to 09:48; after that, "
            "make trouble from the sidebar and watch how the agent reacts."
        )

    upcoming = rt.cron.upcoming(1)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Simulated time", f"{w.now:%H:%M}")
    if rt.current:
        m2.metric("Agent", "🟢 awake")
        m2.caption(f"woken by `{rt.current.schedule_id}`")
    else:
        m2.metric("Agent", "😴 asleep" if rt.running else "⏸ paused")
    if upcoming and upcoming[0].next_run:
        m3.metric("Next wake-up", f"{upcoming[0].next_run:%H:%M}")
        m3.caption(f"`{upcoming[0].id}`")
    woke = sum(r.status != "skipped" for r in runs)
    m4.metric("Wake-ups → messages to you", f"{woke} → {len(notes)}")
    m4.caption(f"{sum(r.status == 'skipped' for r in runs)} quiet triages skipped with no model call")

    left, mid, right = st.columns([1.05, 1.35, 1.0])
    with left:
        st.subheader("📡 Event stream")
        with st.container(height=520):
            for e in reversed(list(w.events)):
                icon = ALERT_ICON.get(e.severity, "") if e.kind == "alert" else EVENT_ICON.get(e.kind, "•")
                svc = f"**{e.service}** " if e.service else ""
                unread = " 🆕" if e.id > w.read_upto else ""
                st.markdown(f"`{e.at:%H:%M}` {icon} {svc}{md(e.text)}{unread}")
    with mid:
        st.subheader("🤖 Agent wake-ups")
        with st.container(height=520):
            for r in reversed(runs[-40:]):
                render_run(r)
    with right:
        st.subheader("📱 Your phone")
        with st.container(height=520):
            for a in [a for a in w.approvals if a.status == "pending"]:
                with st.container(border=True):
                    st.markdown(f"**Approve rollback?** `{a.service}` {a.from_version} → **{a.to_version}**")
                    st.caption(md(a.reason))
                    b1, b2 = st.columns(2)
                    if b1.button("Approve", key=f"approve-{a.id}", type="primary", use_container_width=True):
                        rt.decide(a.id, True)
                        st.rerun(scope="fragment")
                    if b2.button("Deny", key=f"deny-{a.id}", use_container_width=True):
                        rt.decide(a.id, False)
                        st.rerun(scope="fragment")
            if not notes:
                st.caption("Quiet. The agent only messages you when something needs a human.")
            for n in reversed(notes):
                box = {"page": st.error, "warn": st.warning}.get(n.level, st.info)
                box(f"**{n.at:%H:%M} · {n.level.upper()} · {md(n.title)}**\n\n{md(n.message)}")

    c1, c2 = st.columns([1.1, 1.4])
    with c1:
        df = pd.DataFrame(list(w.metrics)[-60:]).set_index("at")
        st.markdown("**checkout-api 5xx %**")
        st.line_chart(df[["error_rate"]], height=160, color="#DAFF33")
        st.markdown("**orders-db disk %**")
        st.line_chart(df[["disk_pct"]], height=160, color="#C1C1FF")
    with c2:
        st.markdown("**⏰ Schedules** (static ones live in `schedules/`; the rest the agent made itself)")
        rows = sorted(rt.cron.schedules.values(), key=lambda s: (not s.active, s.next_run or s.created_at))
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "id": s.id,
                        "kind": s.kind,
                        "when": s.when,
                        "next": f"{s.next_run:%H:%M}" if s.active and s.next_run else "",
                        "status": "active" if s.active else s.ended,
                        "made by": s.created_by or "code",
                        "prompt": s.prompt,
                    }
                    for s in rows
                ]
            ),
            hide_index=True,
            use_container_width=True,
            height=200,
        )
        st.markdown("**🧯 Incidents**")
        if not rt.desk.incidents:
            st.caption("None yet.")
        for inc in reversed(rt.desk.incidents):
            icon = "🔴" if inc.status == "open" else "✅"
            st.markdown(f"{icon} {md(inc.describe())}")
    if w.minute > 48 and rt.running:
        st.caption("The scripted morning is over. Make trouble from the sidebar to see how the agent reacts.")
    # Inside the fragment so the file is rebuilt with the live state on every refresh.
    st.download_button(
        "Download shift log (JSON)",
        rt.shift_log_json(),
        file_name="shift-log.json",
        mime="application/json",
        key="download-log",
    )


live_view()
