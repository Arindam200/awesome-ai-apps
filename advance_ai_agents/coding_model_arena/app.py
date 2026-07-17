"""Nebius Coding Model Arena Streamlit UI.

Every selected model receives the same coding challenge. Submissions run against
hidden tests before an independent model judges correctness, quality, and
efficiency.
"""

import base64
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from challenges import PRESETS, Challenge
from challenges import by_id as challenge_by_id
from execution import ExecutionResult, run_candidate
from judge import JudgeVerdict, judge_submissions
from models import (
    CONTESTANTS,
    DEFAULT_JUDGE,
    DEFAULT_SELECTION,
    JUDGE_MODELS,
    by_id as model_by_id,
)
from runner import GenerationResult, generate_solution

APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR / ".env")

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
NEBIUS_GREEN = "#b7f34a"
RESULT_SCHEMA_VERSION = 2

st.set_page_config(
    page_title="Coding Model Arena | Nebius Token Factory",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _asset_b64(name: str) -> str:
    path = APP_DIR / "assets" / name
    return base64.b64encode(path.read_bytes()).decode() if path.exists() else ""


nebius_b64 = _asset_b64("Nebius.png")
nebius_logo = (
    f'<img src="data:image/png;base64,{nebius_b64}" alt="Nebius">'
    if nebius_b64
    else '<span class="brand-wordmark">NEBIUS</span>'
)

st.markdown(
    f"""
    <style>
    :root {{
        --nb-black: #080a09;
        --nb-ink: #f2f5ef;
        --nb-muted: #9ca49d;
        --nb-green: {NEBIUS_GREEN};
        --nb-green-dark: #9bdc31;
        --nb-canvas: #090b0a;
        --nb-surface: #121512;
        --nb-line: #2a302a;
        --nb-soft: #1d211d;
        --nb-danger: #ff8b83;
        --nb-success: #9ce3aa;
        --nb-radius: 12px;
    }}

    html {{ color-scheme: dark; }}
    html, body, [class*="css"] {{
        font-family: "Avenir Next", "IBM Plex Sans", "Helvetica Neue", sans-serif;
        color: var(--nb-ink);
    }}

    .stApp {{ background: var(--nb-canvas); }}
    .block-container {{ max-width: 1280px; padding-top: 1.4rem; padding-bottom: 4rem; }}
    header[data-testid="stHeader"] {{ background: rgba(9, 11, 10, 0.92); }}
    [data-testid="stToolbar"] {{ right: 1rem; }}

    section[data-testid="stSidebar"] {{
        width: 23rem !important;
        background: #0e110f;
        border-right: 1px solid var(--nb-line);
    }}
    section[data-testid="stSidebar"] > div {{ width: 23rem !important; }}
    section[data-testid="stSidebar"] .block-container {{ padding-top: 1.35rem; }}
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
        color: var(--nb-muted);
    }}

    .sidebar-brand {{
        display: flex;
        align-items: center;
        min-height: 56px;
        margin: -0.25rem 0 1.25rem;
        padding: 8px 0 20px;
    }}
    .sidebar-brand img {{ display: block; width: 132px; height: auto; }}
    .sidebar-brand .brand-wordmark {{ color: white; font-size: 24px; font-weight: 800; }}

    .side-section {{ margin: 1.15rem 0 .6rem; }}
    .side-kicker {{
        color: var(--nb-green-dark);
        font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
    }}
    .side-title {{ margin-top: 3px; color: var(--nb-ink); font-size: 18px; font-weight: 700; }}

    .hero {{
        margin-bottom: 1.8rem;
        padding: 30px 0 32px;
        border-bottom: 1px solid var(--nb-line);
        color: white;
    }}
    .hero h1 {{
        max-width: 780px;
        margin: 0 0 10px;
        color: white;
        font-size: clamp(34px, 5vw, 58px);
        font-weight: 650;
        letter-spacing: -.045em;
        line-height: 1.02;
    }}
    .hero h1 span {{ color: var(--nb-green); }}
    .hero-copy {{ max-width: 720px; margin: 0; color: var(--nb-muted); font-size: 16px; line-height: 1.55; }}
    .hero-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }}
    .hero-meta span {{
        padding: 6px 10px;
        border: 1px solid var(--nb-line);
        border-radius: 6px;
        color: #cdd3cd;
        font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
        font-size: 11px;
    }}

    .section-label {{
        margin-bottom: 5px;
        color: var(--nb-green-dark);
        font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
    }}
    .section-heading {{ margin: 0 0 6px; color: var(--nb-ink) !important; font-size: 27px; line-height: 1.2; }}
    .section-copy {{ margin: 0 0 18px; color: var(--nb-muted); font-size: 14px; }}

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-color: var(--nb-line);
        border-radius: var(--nb-radius);
        background: var(--nb-surface);
        box-shadow: none;
    }}

    .challenge-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }}
    .challenge-head h3 {{ margin: 0; color: var(--nb-ink); font-size: 24px; line-height: 1.2; }}
    .difficulty {{
        padding: 4px 8px;
        border-radius: 5px;
        background: #263719;
        color: var(--nb-green);
        font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: .05em;
        text-transform: uppercase;
    }}
    .challenge-prompt {{ color: #d5dad5 !important; }}
    .challenge-prompt p {{ color: #d5dad5 !important; line-height: 1.65; }}
    .challenge-prompt code {{
        padding: 2px 5px;
        border-radius: 4px;
        background: #1b2714;
        color: var(--nb-green);
        font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
    }}
    .challenge-prompt pre {{ border: 1px solid var(--nb-line); border-radius: 8px; background: #101310; }}

    .empty-state {{
        margin-top: 1.2rem;
        padding: 24px 0;
        border-top: 1px solid var(--nb-line);
    }}
    .empty-state h3 {{ margin: 0 0 6px; color: var(--nb-ink); font-size: 19px; }}
    .empty-state p {{ margin: 0; color: var(--nb-muted); font-size: 14px; }}
    .result-head {{ margin: 2.4rem 0 1rem; }}
    .result-head h2 {{ margin: 0 0 5px; font-size: 30px; letter-spacing: -.025em; }}
    .result-head p {{ margin: 0; color: var(--nb-muted); font-size: 14px; }}
    .rank-line {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }}
    .rank-number {{
        color: var(--nb-green-dark);
        font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
    }}
    .model-name {{ margin: 5px 0 2px; color: var(--nb-ink); font-size: 20px; font-weight: 700; }}
    .model-tag {{ color: var(--nb-muted); font-size: 12px; }}
    .score {{ color: var(--nb-ink); font-size: 36px; font-weight: 650; letter-spacing: -.04em; line-height: 1; }}
    .score small {{ color: #858c85; font-size: 12px; font-weight: 500; letter-spacing: 0; }}
    .result-meta {{ display: flex; flex-wrap: wrap; gap: 7px; margin: 16px 0 2px; }}
    .status-badge, .time-badge {{
        padding: 5px 8px;
        border-radius: 5px;
        font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
        font-size: 10px;
        font-weight: 700;
    }}
    .status-badge.pass {{ background: #16321d; color: var(--nb-success); }}
    .status-badge.partial {{ background: #383214; color: #e8d76d; }}
    .status-badge.fail {{ background: #3a1c1a; color: var(--nb-danger); }}
    .time-badge {{ background: #1c201c; color: #aab1aa; }}

    .stButton > button[kind="primary"] {{
        min-height: 48px;
        border: 1px solid var(--nb-green);
        border-radius: 8px;
        background: var(--nb-green);
        color: #10130d;
        font-weight: 700;
        box-shadow: none;
        transition: background-color 140ms ease-out, color 140ms ease-out, transform 140ms ease-out;
    }}
    .stButton > button[kind="primary"]:hover {{
        border-color: #d1ff83;
        background: #d1ff83;
        color: #10130d;
    }}
    .stButton > button[kind="primary"]:active {{ transform: translateY(1px); }}
    .stButton > button:focus-visible {{ outline: 3px solid rgba(69, 112, 22, .34); outline-offset: 2px; }}
    .stButton > button[kind="primary"] p {{ color: #10130d !important; }}

    [data-baseweb="select"] > div, [data-baseweb="input"] > div {{
        border-color: var(--nb-line) !important;
        background: #151815 !important;
        color: var(--nb-ink) !important;
    }}
    [data-baseweb="select"] input, [data-baseweb="input"] input {{ color: var(--nb-ink) !important; }}
    [data-baseweb="select"] svg, [data-baseweb="input"] svg {{ fill: var(--nb-muted) !important; }}
    section[data-testid="stSidebar"] [data-testid="stTextInputRootElement"],
    section[data-testid="stSidebar"] div[role="group"]:has(input[role="combobox"]) {{
        border-color: var(--nb-line) !important;
        background: #151815 !important;
    }}
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] button:has(+ input),
    section[data-testid="stSidebar"] div[role="group"]:has(input[role="combobox"]) button {{
        background: #151815 !important;
        color: var(--nb-ink) !important;
    }}
    section[data-testid="stSidebar"] input {{ caret-color: var(--nb-green); }}
    section[data-testid="stSidebar"] input::placeholder {{ color: #737b74 !important; }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: var(--nb-muted) !important; }}
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ color: var(--nb-muted) !important; }}
    [data-testid="stExpander"] {{ border-color: var(--nb-line); border-radius: 8px; background: #101310; }}
    [data-testid="stAlert"] {{ border-radius: 8px; }}
    [data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}

    @media (max-width: 780px) {{
        .block-container {{ padding: 1rem 1rem 3rem; }}
        .hero {{ min-height: auto; padding: 24px 0 28px; }}
        .hero h1 {{ font-size: 38px; }}
        .hero-copy {{ font-size: 15px; }}
        .empty-state {{ padding: 22px 20px; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{ scroll-behavior: auto !important; transition-duration: .01ms !important; }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# Sidebar configuration
with st.sidebar:
    st.markdown(
        f'<div class="sidebar-brand">{nebius_logo}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="side-section"><div class="side-kicker">01 / Connect</div>'
        '<div class="side-title">API access</div></div>',
        unsafe_allow_html=True,
    )
    api_key = st.text_input(
        "Nebius API key",
        value=os.environ.get("NEBIUS_API_KEY", ""),
        type="password",
        placeholder="Paste a Token Factory API key",
        help="Create a project API key in the Nebius Token Factory console.",
    )
    st.caption("Configured from the environment." if api_key else "Required only when you run the arena.")

    st.markdown(
        '<div class="side-section"><div class="side-kicker">02 / Brief</div>'
        '<div class="side-title">Challenge</div></div>',
        unsafe_allow_html=True,
    )
    challenge_titles = {c.id: f"{c.title} · {c.difficulty}" for c in PRESETS}
    challenge_id = st.selectbox(
        "Coding challenge",
        options=list(challenge_titles),
        format_func=lambda cid: challenge_titles[cid],
        label_visibility="collapsed",
        key="challenge_selector_v2",
    )
    st.caption(f"{len(PRESETS)} curated challenges · Expert litmus tests appear first.")

    st.markdown(
        '<div class="side-section"><div class="side-kicker">03 / Evaluate</div>'
        '<div class="side-title">Independent judge</div></div>',
        unsafe_allow_html=True,
    )
    judge_ids = [model.id for model in JUDGE_MODELS]
    judge_labels = {model.id: f"{model.label} · {model.tagline}" for model in JUDGE_MODELS}
    judge_model = st.selectbox(
        "Judge model",
        options=judge_ids,
        index=judge_ids.index(DEFAULT_JUDGE),
        format_func=lambda model_id: judge_labels[model_id],
        help="The judge is kept outside the contestant pool and reviews all submissions together.",
        label_visibility="collapsed",
    )

    st.markdown(
        '<div class="side-section"><div class="side-kicker">04 / Compete</div>'
        '<div class="side-title">Contestant roster</div></div>',
        unsafe_allow_html=True,
    )
    contestant_ids = [model.id for model in CONTESTANTS]
    contestant_labels = {model.id: f"{model.label} · {model.tagline}" for model in CONTESTANTS}
    model_a = st.selectbox(
        "Model A",
        options=contestant_ids,
        index=contestant_ids.index(DEFAULT_SELECTION[0]),
        format_func=lambda model_id: contestant_labels[model_id],
        help="The first model in this head-to-head benchmark.",
        key="model_a_selector_v3",
    )
    model_b_options = [model_id for model_id in contestant_ids if model_id != model_a]
    preferred_model_b = DEFAULT_SELECTION[1] if DEFAULT_SELECTION[1] in model_b_options else model_b_options[0]
    model_b = st.selectbox(
        "Model B",
        options=model_b_options,
        index=model_b_options.index(preferred_model_b),
        format_func=lambda model_id: contestant_labels[model_id],
        help="The second model. A model cannot compete against itself.",
        key="model_b_selector_v3",
    )
    selected_ids = [model_a, model_b]
    run_clicked = st.button(
        "Run model benchmark",
        type="primary",
        use_container_width=True,
    )


challenge: Challenge = challenge_by_id(challenge_id)

st.markdown(
    f"""
    <section class="hero">
        <h1>Coding model <span>arena</span></h1>
        <p class="hero-copy">One brief. Multiple open models. Hidden tests establish ground truth,
        then an independent judge ranks the code that survives.</p>
        <div class="hero-meta">
            <span>{len(PRESETS)} challenges</span>
            <span>2 model head-to-head</span>
            <span>parallel execution</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.container():
    st.markdown(
        f'<div class="challenge-head"><h3>{challenge.title}</h3>'
        f'<span class="difficulty">{challenge.difficulty}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="challenge-prompt">{challenge.prompt}</div>', unsafe_allow_html=True)


def run_arena(
    challenge: Challenge,
    model_ids: list[str],
    judge_model: str,
    client: OpenAI,
    progress=None,
):
    """Generate, execute, and judge submissions for one arena run."""
    notify = progress or (lambda _message: None)
    generations: dict[str, GenerationResult] = {}
    with ThreadPoolExecutor(max_workers=max(len(model_ids), 1)) as pool:
        futures = {
            pool.submit(generate_solution, client, model_id, challenge.prompt): model_id
            for model_id in model_ids
        }
        for future in as_completed(futures):
            model_id = futures[future]
            generation = future.result()
            generations[model_id] = generation
            label = model_by_id(model_id).label
            state = "finished" if generation.code else "failed"
            notify(f"{label} generation {state} in {format_duration(generation.latency_seconds)}.")

    executions: dict[str, ExecutionResult] = {}
    with ThreadPoolExecutor(max_workers=max(len(model_ids), 1)) as pool:
        futures = {
            pool.submit(
                run_candidate, generations[model_id].code, challenge.hidden_tests
            ): model_id
            for model_id in model_ids
            if generations[model_id].code
        }
        for future in as_completed(futures):
            model_id = futures[future]
            executions[model_id] = future.result()
            execution = executions[model_id]
            notify(
                f"{model_by_id(model_id).label} passed "
                f"{execution.passed_tests}/{execution.total_tests} hidden cases."
            )

    submissions = {
        model_by_id(model_id).label: {
            "code": generations[model_id].code,
            "passed": executions.get(
                model_id, ExecutionResult(False, "", "no code generated", 0, "n/a")
            ).passed,
            "test_score": executions.get(
                model_id, ExecutionResult(False, "", "no code generated", 0, "n/a")
            ).test_score,
            "passed_tests": executions.get(
                model_id, ExecutionResult(False, "", "no code generated", 0, "n/a")
            ).passed_tests,
            "total_tests": executions.get(
                model_id, ExecutionResult(False, "", "no code generated", 0, "n/a")
            ).total_tests,
            "test_output": (
                executions[model_id].stdout + "\n" + executions[model_id].stderr
                if model_id in executions
                else generations[model_id].error or "no code generated"
            ),
        }
        for model_id in model_ids
    }
    generation_failed = any(not generations[model_id].code for model_id in model_ids)
    infrastructure_failed = any(
        execution.failure_kind == "infrastructure" for execution in executions.values()
    )
    if generation_failed:
        failed_labels = [
            model_by_id(model_id).label
            for model_id in model_ids
            if not generations[model_id].code
        ]
        verdict = JudgeVerdict(
            error="Judging was skipped because code generation failed for "
            + ", ".join(failed_labels)
            + "."
        )
    elif infrastructure_failed:
        verdict = JudgeVerdict(
            error="Judging was skipped because the hidden-test backend did not run."
        )
    else:
        notify("Hidden tests finished. Starting independent judging.")
        verdict = judge_submissions(client, judge_model, challenge.prompt, submissions)
    return generations, executions, verdict


def unavailable_models(client: OpenAI, model_ids: list[str]) -> list[str]:
    """Return requested model IDs missing from the authenticated live catalog."""
    available_ids = {
        model.id
        for model in client.with_options(timeout=20, max_retries=0).models.list().data
    }
    return [model_id for model_id in model_ids if model_id not in available_ids]


def format_duration(seconds: float) -> str:
    """Keep fast local test runs visible instead of rounding them to 0.0s."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.1f}s"


if run_clicked:
    if not api_key:
        st.error("Add a Nebius Token Factory API key in the sidebar before starting the benchmark.")
    else:
        client = OpenAI(
            api_key=api_key,
            base_url=NEBIUS_BASE_URL,
            timeout=90,
            max_retries=0,
        )
        run_status = st.status("Running the model benchmark", expanded=True)
        run_status.write("Validating the selected models against the live Token Factory catalog.")
        try:
            missing_models = unavailable_models(client, [*selected_ids, judge_model])
            if missing_models:
                raise RuntimeError(
                    "These models are not available in the current Nebius Token Factory "
                    f"catalog: {', '.join(missing_models)}"
                )
            run_status.write(f"Sending the brief to {len(selected_ids)} models in parallel.")
            generations, executions, verdict = run_arena(
                challenge,
                selected_ids,
                judge_model,
                client,
                progress=run_status.write,
            )
        except Exception as exc:  # Keep API/runtime failures inside the app UI.
            run_status.update(label="Benchmark stopped", state="error", expanded=True)
            st.error(f"The run could not be completed: {exc}")
        else:
            generation_failed = any(
                not generations[model_id].code for model_id in selected_ids
            )
            infrastructure_failed = any(
                execution.failure_kind == "infrastructure"
                for execution in executions.values()
            )
            if generation_failed:
                run_status.update(
                    label="Code generation needs attention",
                    state="error",
                    expanded=True,
                )
            elif infrastructure_failed:
                run_status.update(
                    label="Code generated; test execution needs attention",
                    state="error",
                    expanded=False,
                )
            elif verdict.error:
                run_status.update(
                    label="Tests finished; judge needs attention",
                    state="error",
                    expanded=False,
                )
            else:
                run_status.write("Hidden tests finished. Independent judging is complete.")
                run_status.update(label="Benchmark complete", state="complete", expanded=False)
            st.session_state["arena_result"] = {
                "challenge": challenge,
                "model_ids": selected_ids,
                "generations": generations,
                "executions": executions,
                "verdict": verdict,
                "execution_backend": "local",
                "schema_version": RESULT_SCHEMA_VERSION,
            }

result = st.session_state.get("arena_result")
if result and (
    result.get("execution_backend") != "local"
    or result.get("schema_version") != RESULT_SCHEMA_VERSION
):
    # Discard results cached before local execution and reliable generation states.
    st.session_state.pop("arena_result", None)
    result = None
if result and result["challenge"].id == challenge.id:
    generations = result["generations"]
    executions = result["executions"]
    verdict: JudgeVerdict = result["verdict"]
    model_ids = result["model_ids"]
    infrastructure_failed = any(
        execution.failure_kind == "infrastructure" for execution in executions.values()
    )
    generation_failed = any(not generations[model_id].code for model_id in model_ids)

    st.markdown(
        '<div class="result-head"><div class="section-label">Benchmark results</div>'
        '<h2>Leaderboard</h2><p>Objective test performance carries 60% of the score. '
        "The independent code review contributes 40%.</p></div>",
        unsafe_allow_html=True,
    )
    if generation_failed:
        st.error(
            "At least one model did not return a complete code answer, so tests and "
            "judging were skipped for that submission. See the model result below."
        )
    elif infrastructure_failed:
        st.error(
            "The generated code was not tested because the execution backend is unavailable. "
            "Open Execution details under either model to see the exact setup error."
        )
    elif verdict.error:
        st.warning(f"The judge was unavailable ({verdict.error}). Rankings use hidden tests only.")

    def total_score(model_id: str) -> int:
        """Return the weighted score for a model on a 0–100 scale."""
        label = model_by_id(model_id).label
        execution = executions.get(model_id)
        test_score = execution.test_score if execution else 0
        judge_score = verdict.scores.get(label)
        if not judge_score:
            return test_score
        return round(0.6 * test_score + 0.4 * judge_score.total)

    evaluated = not generation_failed and not infrastructure_failed
    ranked = sorted(model_ids, key=total_score, reverse=True) if evaluated else model_ids
    columns = st.columns(2, gap="large")
    for column, model_id in zip(columns, ranked):
        rank = ranked.index(model_id) + 1
        spec = model_by_id(model_id)
        generation = generations[model_id]
        execution = executions.get(model_id)
        passed = bool(execution and execution.passed)
        execution_error = bool(execution and execution.failure_kind == "infrastructure")
        partially_passed = bool(execution and execution.passed_tests > 0 and not passed)
        test_class = "pass" if passed else "partial" if partially_passed else "fail"
        if execution_error:
            test_label = "Execution error"
        elif execution:
            test_label = (
                f"{execution.passed_tests}/{execution.total_tests} tests · "
                f"{execution.test_score}%"
            )
        else:
            test_label = "Tests unavailable"
        if generation.error:
            test_label = "Generation failed"
            test_class = "fail"
        rank_label = f"Rank {rank:02d}" if evaluated else f"Model {rank:02d}"
        score_display = str(total_score(model_id)) if evaluated else "N/A"
        timing = f"Generate {format_duration(generation.latency_seconds)}"
        if execution:
            timing += f" · Run {format_duration(execution.elapsed_seconds)}"

        with column:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="rank-line">
                        <div>
                            <div class="rank-number">{rank_label}</div>
                            <div class="model-name">{spec.label}</div>
                            <div class="model-tag">{spec.tagline}</div>
                        </div>
                        <div class="score">{score_display}<small>/100</small></div>
                    </div>
                    <div class="result-meta">
                        <span class="status-badge {test_class}">{test_label}</span>
                        <span class="time-badge">{timing}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown("**Generated solution**")
                if generation.error:
                    st.error(generation.error)
                if generation.code:
                    st.code(generation.code, language="python")
                if execution and not execution.passed:
                    with st.expander("Execution details"):
                        details = "\n".join(
                            part for part in (execution.stderr, execution.stdout) if part
                        )
                        st.code(details or "The execution backend returned no diagnostic output.")
else:
    st.markdown(
        """
        <div class="empty-state">
            <h3>Your leaderboard will appear here</h3>
            <p>Connect an API key, confirm the roster, and start the benchmark. Results stay available while you inspect the winning code.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
