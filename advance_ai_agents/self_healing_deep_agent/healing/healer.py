"""The self-healing layer: sort each tool failure, retry what's temporary, and
repair only real code bugs, behind guardrails.

    Failure                          Kind               What happens
    HTTP 429 / 5xx / timeout         TEMPORARY          middleware waits and retries; code untouched
    HTTP 400 / 404                   BAD_ARGUMENTS      agent corrects its arguments; code untouched
    HTTP 401 / 403                   NEEDS_HUMAN        agent stops and says what a person must do
    crash inside tools/, or output   CODE_BUG           failure report -> tool-fixer subagent ->
    that breaks its contract                            repair_tool (tested, replayed, or rolled back)
"""
from __future__ import annotations

import ast
import difflib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool

from config import FAILURES_DIR, MAX_REPAIRS_PER_TOOL, MAX_RETRIES, ROOT, TESTS_DIR, TOOLS_DIR
from contracts import ContractError, validate
from healing.recorder import Recorder
from provider_api.client import AuthError, RateLimitError, RequestError, ServerError, start_trace
from tools import TOOLS, load_tool

sys.dont_write_bytecode = True   # a patched tool must never be shadowed by a stale .pyc
_LOAD_LOCK = threading.Lock()    # parallel tool calls must not reload a module at the same time


class Healer:
    """Per-run state shared by the middleware and repair_tool."""

    def __init__(self, rec: Recorder, api_url: str):
        self.rec, self.api_url = rec, api_url
        self.open_bugs: dict[str, str] = {}          # tool -> error, for tools with a known code bug
        self.failed_calls: dict[str, list] = {}      # tool -> args that broke it (replayed in verify)
        self.repairs_used: dict[str, int] = {}
        self.local_check_seconds = 0.0

    # ------------------------------------------------------------------ business tools
    def langchain_tools(self) -> list[StructuredTool]:
        def make(name: str):
            def run(**kwargs):
                args = _plain(kwargs)
                with _LOAD_LOCK:
                    func = load_tool(name)           # reload: patched code takes effect at once
                trace = start_trace()
                try:
                    result = func(**args)
                    validate(name, args, result)     # "it returned" is not "it's right"
                except Exception as exc:
                    exc.http_trace = list(trace)     # what the API really sent, for the report
                    raise
                return json.dumps(result)
            return StructuredTool.from_function(func=run, name=name, description=TOOLS[name]["description"],
                                                args_schema=TOOLS[name]["args"])
        return [make(n) for n in TOOLS]

    # ------------------------------------------------------------------ failure report
    def code_bug_report(self, name: str, args: dict, exc: Exception) -> Path:
        self.open_bugs[name] = f"{type(exc).__name__}: {exc}"
        self.failed_calls.setdefault(name, []).append(args)
        _, tests = self.run_tests(name)
        left = MAX_REPAIRS_PER_TOOL - self.repairs_used.get(name, 0)
        tb = "".join(traceback.format_exception(exc)[-4:]) if not isinstance(exc, ContractError) else "(none)"
        report = (
            f"# Failure report: tools/{name}.py\n\n"
            f"error: {type(exc).__name__}: {exc}\n"
            f"kind: {'wrong output (contract check failed)' if isinstance(exc, ContractError) else 'crash'}\n"
            f"args: {_trim(json.dumps(args), 1200)}\n\n"
            f"## Traceback (tail)\n{tb}\n"
            f"## Values at the crashing line\n{_crash_locals(exc)}\n\n"
            f"## HTTP calls the tool made (bodies shortened)\n{_http_trace(exc)}\n\n"
            f"## Source of tools/{name}.py\n```python\n{(TOOLS_DIR / f'{name}.py').read_text(encoding='utf-8')}```\n\n"
            f"## Contract tests: tests/test_{name}.py\n{tests}\n\n"
            f"repair attempts left: {left}\n")
        FAILURES_DIR.mkdir(exist_ok=True)
        path = FAILURES_DIR / f"{name}.md"
        path.write_text(report, encoding="utf-8")
        return path

    # ------------------------------------------------------------------ repair_tool
    def repair_tool_for_fixer(self) -> StructuredTool:
        def repair_tool(tool_name: str, reason: str, edits: list[dict]) -> str:
            """Patch a broken tool in tools/ with exact find/replace edits. The patch is
            syntax-checked, tested in isolation, replayed on the failing call, and rolled
            back if anything fails.

            Args:
                tool_name: The tool to fix, e.g. fetch_pricing.
                reason: One line: the root cause.
                edits: List of {"find": exact text copied from the source, "replace": new text}.
            """
            return self.repair(tool_name, reason, edits)
        return StructuredTool.from_function(repair_tool)

    def repair(self, tool_name: str, reason: str, edits: list) -> str:
        rec = self.rec
        if tool_name not in self.open_bugs:                                    # guardrail 1
            msg = (f"{tool_name} has no open code bug. Only tools that crashed or returned wrong "
                   "output can be repaired.")
            rec.emit("refused", tool=tool_name, message=msg)
            return f"REPAIR REFUSED: {msg}"
        used = self.repairs_used.get(tool_name, 0)
        if used >= MAX_REPAIRS_PER_TOOL:                                       # guardrail 2
            msg = f"repair budget used up for {tool_name} ({used}/{MAX_REPAIRS_PER_TOOL})"
            rec.emit("refused", tool=tool_name, message=msg)
            return f"REPAIR REFUSED: {msg}. Report that the tool needs a person."
        self.repairs_used[tool_name] = used + 1
        rec.emit("repair", tool=tool_name, attempt=used + 1, max=MAX_REPAIRS_PER_TOOL, reason=reason)

        try:
            path = tool_path(tool_name)                                        # guardrail 3
            old = path.read_text(encoding="utf-8")
            new = apply_edits(old, edits)
            ast.parse(new)                                                     # guardrail 4
        except (ValueError, SyntaxError, PermissionError, KeyError, TypeError) as exc:
            msg = f"{type(exc).__name__}: {exc}"
            rec.emit("rejected", tool=tool_name, message=f"patch rejected, file unchanged: {msg}")
            return f"REPAIR REJECTED (file unchanged): {msg}"

        diff = unified_diff(old, new, f"tools/{tool_name}.py")
        rec.emit("patch", tool=tool_name, attempt=used + 1, diff=diff)
        backup = path.with_suffix(".py.bak")
        shutil.copy2(path, backup)                                             # guardrail 5
        path.write_text(new, encoding="utf-8")

        tests_ok, tests_out = self.run_tests(tool_name)                        # guardrail 6
        replay_ok, replay_out = self.replay(tool_name)
        if not (tests_ok and replay_ok):
            shutil.move(backup, path)
            rec.emit("rollback", tool=tool_name, tests=tests_out, replay=replay_out,
                     message=f"checks failed, restored tools/{tool_name}.py from backup")
            return (f"REPAIR FAILED VERIFICATION (rolled back, file unchanged).\n"
                    f"pytest:\n{tests_out}\nreplay of the failing call:\n{replay_out}")
        backup.unlink()
        n_tests = _passed(tests_out)
        rec.emit("verified", tool=tool_name, tests=tests_out, replay=replay_out,
                 message=f"{n_tests} tests passed, failing call replayed OK, patch kept")
        return (f"REPAIR VERIFIED for {tool_name}: {n_tests} tests passed and the failing call "
                f"now works.\nreplay: {replay_out}")

    # ------------------------------------------------------------------ isolated checks
    def run_tests(self, name: str) -> tuple[bool, str]:
        return self._run([sys.executable, "-m", "pytest", "-q", "--tb=line", "--no-header",
                          str(TESTS_DIR / f"test_{name}.py")])

    def replay(self, name: str) -> tuple[bool, str]:
        calls = self.failed_calls.get(name, [])
        if not calls:
            return True, "no failing call to replay"
        return self._run([sys.executable, "-c", _REPLAY, name, json.dumps(calls)], timeout=30)

    def _run(self, cmd: list, timeout: int = 60) -> tuple[bool, str]:
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
               "PROVIDER_API_URL": self.api_url}
        start = time.perf_counter()
        try:
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                               env=env, encoding="utf-8")
        except subprocess.TimeoutExpired:
            return False, f"timed out after {timeout}s"
        finally:
            self.local_check_seconds += time.perf_counter() - start
        out = (p.stdout + p.stderr).strip()
        return p.returncode == 0, "\n".join(out.splitlines()[-15:])


_REPLAY = """
import json, sys
from tools import load_tool
from contracts import validate
name, calls = sys.argv[1], json.loads(sys.argv[2])
for args in calls:
    result = load_tool(name)(**args)
    validate(name, args, result)
    print("replay ok:", json.dumps(result)[:160])
"""


# ====================================================================== middleware
class HealingMiddleware(AgentMiddleware):
    """Wraps every tool call of the main agent: records it, and sorts any failure."""

    def __init__(self, healer: Healer):
        super().__init__()
        self.healer = healer

    def wrap_tool_call(self, request, handler):
        rec, call = self.healer.rec, request.tool_call
        name, args, call_id = call["name"], _plain(call.get("args", {})), call["id"]

        if name == "task":
            rec.emit("delegate", description=args.get("description", ""), to=args.get("subagent_type"))
            out = handler(request)
            rec.emit("delegate_done", summary=_trim(_content(out), 220))
            return out
        if name not in TOOLS:                       # Deep Agents' own tools: read_file, ls, grep...
            if name in ("read_file", "ls", "glob", "grep"):
                rec.emit("file_read", agent="agent", path=args.get("file_path") or args.get("path")
                         or args.get("pattern", ""))
            return handler(request)

        rec.emit("tool_call", agent="agent", name=name, args=args)
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                out = handler(request)
            except (RateLimitError, ServerError) as exc:            # TEMPORARY
                if attempt <= MAX_RETRIES:
                    wait = exc.retry_after or float(2 ** (attempt - 1))
                    rec.emit("retry", name=name, attempt=attempt, max=MAX_RETRIES, wait=wait, error=str(exc))
                    time.sleep(wait)
                    continue
                return self._fail(call_id, name, exc, "TEMPORARY",
                                  f"{name} still failed after {MAX_RETRIES} retries ({exc}). The tool code "
                                  "is fine; do not repair it. Stop and tell the user the provider is "
                                  "unavailable right now and to try again later.")
            except AuthError as exc:                                 # NEEDS_HUMAN
                return self._fail(call_id, name, exc, "NEEDS_HUMAN",
                                  f"The provider rejected the API key ({exc}). This is not a bug in "
                                  f"tools/{name}.py (the key is configured outside the tools) and no code change can fix it. Do not delegate a repair. "
                                  "Stop, make no report, and tell the user exactly what to do.")
            except RequestError as exc:                              # BAD_ARGUMENTS
                return self._fail(call_id, name, exc, "BAD_ARGUMENTS",
                                  f"The provider rejected these arguments: {json.dumps(args)}. Its reply: "
                                  f"{json.dumps(exc.body)}. tools/{name}.py worked correctly; do not repair "
                                  f"it. Call {name} again with corrected arguments.")
            except Exception as exc:                                 # CODE_BUG (or bad args)
                if not (isinstance(exc, ContractError) or _raised_in_tools(exc)):
                    return self._fail(call_id, name, exc, "BAD_ARGUMENTS",
                                      f"The call was rejected before the tool ran: {exc}. "
                                      "Check the arguments and call again.")
                report = self.healer.code_bug_report(name, args, exc)
                rel = "/" + report.relative_to(ROOT).as_posix()
                return self._fail(call_id, name, exc, "CODE_BUG",
                                  f"tools/{name}.py has a bug ({type(exc).__name__}: {_trim(str(exc), 300)}). "
                                  f"The full failure report is at {rel}. Do not fix it yourself: call task "
                                  f"with subagent_type='tool-fixer' and a description naming the tool and "
                                  f"the report path. When the fixer says REPAIR VERIFIED, call {name} again "
                                  "with exactly the same arguments.", report=rel)
            break

        result = _content(out)
        if name in self.healer.open_bugs:
            self.healer.open_bugs.pop(name)
            rec.emit("recovered", name=name, result=_trim(result, 300))
        else:
            rec.emit("tool_ok", agent="agent", name=name, result=_trim(result, 300))
        return out

    def _fail(self, call_id, name, exc, kind, explanation, report=None):
        self.healer.rec.emit("tool_error", agent="agent", name=name, kind=kind,
                             error=_trim(f"{type(exc).__name__}: {exc}", 240),
                             explanation=_KIND_TEXT[kind], report=report)
        return ToolMessage(content=f"{kind}: {explanation}", tool_call_id=call_id, name=name, status="error")


_KIND_TEXT = {
    "TEMPORARY": "provider is temporarily unavailable, not a code bug",
    "NEEDS_HUMAN": "credentials problem, a person has to act; no code change",
    "BAD_ARGUMENTS": "the provider rejected the arguments; the tool code is fine",
    "CODE_BUG": "the tool's own code is wrong; sending it to the tool-fixer",
}


class FixerObserver(AgentMiddleware):
    """Records which files the tool-fixer subagent reads."""

    def __init__(self, rec: Recorder):
        super().__init__()
        self.rec = rec

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        if call["name"] in ("read_file", "ls", "glob", "grep"):
            a = call.get("args", {})
            self.rec.emit("file_read", agent="tool-fixer",
                          path=a.get("file_path") or a.get("path") or a.get("pattern", ""))
        return handler(request)


# ====================================================================== helpers
def tool_path(tool_name: str) -> Path:
    """Allowlist: only the registered tools/<name>.py files may be patched."""
    path = (TOOLS_DIR / f"{tool_name}.py").resolve()
    if tool_name not in TOOLS or path.parent != TOOLS_DIR.resolve() or not path.exists():
        raise PermissionError(f"{tool_name!r} is not a tool in tools/; only those files can be patched")
    return path


def apply_edits(source: str, edits: list) -> str:
    if not edits:
        raise ValueError("no edits given")
    for i, edit in enumerate(edits, 1):
        count = source.count(edit["find"])
        if count != 1:
            raise ValueError(f"edit {i}: `find` must match the source exactly once (matched {count} times)")
        source = source.replace(edit["find"], edit["replace"])
    return source


def unified_diff(old: str, new: str, name: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"a/{name}", tofile=f"b/{name}", n=1))


def _raised_in_tools(exc: Exception) -> bool:
    tb = exc.__traceback__
    while tb:
        f = Path(tb.tb_frame.f_code.co_filename).resolve()
        if f.parent == TOOLS_DIR.resolve() and f.name != "__init__.py":
            return True
        tb = tb.tb_next
    return False


def _crash_locals(exc: Exception) -> str:
    """The runtime values in the deepest tools/ frame, like a crash reporter shows."""
    frame, tb = None, exc.__traceback__
    while tb:
        f = Path(tb.tb_frame.f_code.co_filename).resolve()
        if f.parent == TOOLS_DIR.resolve() and f.name != "__init__.py":
            frame = tb.tb_frame
        tb = tb.tb_next
    if frame is None:
        return "(the tool returned normally; its output failed the contract check)"
    return "\n".join(f"{k} = {_trim(repr(v), 400)}" for k, v in frame.f_locals.items() if not k.startswith("__"))


def _http_trace(exc: Exception) -> str:
    calls = getattr(exc, "http_trace", None)
    if not calls:
        return "(none)"
    return "\n".join(f"{c['request']} -> {c['status']}\n  {_trim(json.dumps(_shorten(c['body'])), 700)}"
                     for c in calls[:6])


def _shorten(obj):
    """Keep the shape of a JSON body, drop the bulk: long lists keep their first item."""
    if isinstance(obj, dict):
        return {k: _shorten(v) for k, v in obj.items()}
    if isinstance(obj, list) and len(obj) > 1:
        return [_shorten(obj[0]), f"... {len(obj) - 1} more items"]
    return obj


def _plain(obj):
    """Pydantic models -> plain dicts/lists, so tools get JSON-like arguments."""
    return json.loads(json.dumps(obj, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o)))


def _content(out) -> str:
    update = getattr(out, "update", None)            # a Command from the task tool
    if isinstance(update, dict) and update.get("messages"):
        out = update["messages"][-1]
    c = getattr(out, "content", out)
    if isinstance(c, list):
        c = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c)


def _passed(pytest_out: str) -> str:
    for line in reversed(pytest_out.splitlines()):
        if "passed" in line:
            return line.split(" passed")[0].split()[-1]
    return "all"


def _trim(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."
