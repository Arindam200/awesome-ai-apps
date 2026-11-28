"""Build the self-healing cost-report agent on LangChain Deep Agents."""
from __future__ import annotations

from deepagents import (FilesystemPermission, GeneralPurposeSubagentProfile, HarnessProfile,
                        create_deep_agent, register_harness_profile)
from deepagents.backends import FilesystemBackend

from config import ROOT, make_model
from healing.healer import FixerObserver, Healer, HealingMiddleware

SYSTEM_PROMPT = """You build monthly LLM cost reports from a provider's billing API.

For a report: fetch_usage(month) -> summarize_usage(path) -> fetch_pricing for every model in
the summary -> export_report with one row per model (its usage totals plus its three prices).
Then answer in 2-4 short lines: total cost, the most expensive model, and the CSV path.

Your tools are Python files in tools/ and can break. A failed call comes back with a label:
- CODE_BUG: the tool's code is wrong. Don't fix it yourself. Call task with
  subagent_type="tool-fixer" and a one-line description naming the tool and the report path.
  When the fixer reports REPAIR VERIFIED, repeat the exact same tool call. If it could not fix
  it, stop and tell the user which tool is broken.
- BAD_ARGUMENTS: your arguments were wrong and the code is fine. Read the provider's reply,
  then call again with corrected arguments. If a model id was replaced, price it with the new
  id, keep it in the report, and mention the change in your answer.
- NEEDS_HUMAN or TEMPORARY: no code change can fix it. Stop and tell the user what to do.
Use only numbers that tools returned. Never invent results."""

FIXER_PROMPT = """You repair one broken Python tool in tools/.

1. read_file the failure report you were given. It has the error, the arguments, the traceback,
   the runtime values at the crash, the tool's source and the failing tests.
2. If you need more, read tests/test_<tool>.py or /contracts.py. Nothing else is readable.
3. Call repair_tool with the smallest find/replace edits that fix the root cause for every
   failing test. Keep the function signature and the return shape. Never hardcode test
   inputs. Copy each `find` exactly from the source (without read_file's line numbers).
4. If the result is REPAIR FAILED VERIFICATION, read its output and try once more.
Finish with one sentence: what was wrong and what you changed, or that you couldn't fix it."""

FIXER_DESCRIPTION = ("Repairs a tool in tools/ that has a CODE_BUG. Give it the tool name and the "
                     "failure report path. It patches the code, and the patch is kept only if the "
                     "tool's tests pass and the failing call works.")

# Read-only filesystem: the fixer may read tools, tests, contracts and failure reports.
# Every write goes through repair_tool and its guardrails, never through edit_file.
PERMISSIONS = [
    FilesystemPermission(operations=["read"], mode="allow",
                         paths=["/tools/**", "/tests/**", "/failures/**", "/contracts.py"]),
    FilesystemPermission(operations=["read", "write"], mode="deny", paths=["/**"]),
]

# No default general-purpose subagent, and no write tools: the only way to change code is repair_tool.
register_harness_profile("openai", HarnessProfile(
    general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    excluded_tools=frozenset({"write_file", "edit_file", "delete", "execute", "write_todos"}),
))


def build_agent(healer: Healer):
    model = make_model()
    return create_deep_agent(
        model=model,
        tools=healer.langchain_tools(),
        system_prompt=SYSTEM_PROMPT,
        middleware=[HealingMiddleware(healer)],
        subagents=[{
            "name": "tool-fixer",
            "description": FIXER_DESCRIPTION,
            "system_prompt": FIXER_PROMPT,
            "tools": [healer.repair_tool_for_fixer()],
            "middleware": [FixerObserver(healer.rec)],
            "model": model,
        }],
        backend=FilesystemBackend(root_dir=ROOT, virtual_mode=True),
        permissions=PERMISSIONS,
        name="agent",
    )
