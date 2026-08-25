#!/usr/bin/env bash
# fix.sh — the eval-driven fix loop.
#
# Runs the pytest eval suite. If anything fails, writes the failure block
# plus editing instructions to .fix-prompt.md, then hands it off to a
# coding-agent CLI in headless mode so your terminal is never hijacked.
#
# Usage:
#   ./fix.sh                     # default: AGENT=opencode
#   AGENT=opencode  ./fix.sh     # OpenCode CLI (opencode run) — the default
#   AGENT=claude    ./fix.sh     # Claude Code CLI, non-interactive
#   AGENT=cursor    ./fix.sh     # Cursor Agent (cursor-agent -p)
#   AGENT=aider     ./fix.sh     # Aider (aider --message --yes-always)
#   AGENT=paste     ./fix.sh     # no CLI, just write .fix-prompt.md
#   AGENT=copilot   ./fix.sh     # gh copilot has no headless edit mode — falls through to paste
#
# The prompt file is always written to .fix-prompt.md, so even without a
# CLI you can open it and paste into any chat surface (Copilot Chat,
# Cursor Chat, ChatGPT web, etc.).

set -uo pipefail

cd "$(dirname "$0")"

AGENT="${AGENT:-opencode}"
PROMPT_FILE=".fix-prompt.md"
OUT="$(mktemp -t temporal-tx-eval-XXXXXX).log"

echo "==> Running eval suite..."
pytest evals/test_temporal_tx_coverage.py -v --tb=short 2>&1 | tee "$OUT"
STATUS=${PIPESTATUS[0]}

if [ "$STATUS" -eq 0 ]; then
  echo "==> Evals green. Nothing to fix."
  rm -f "$OUT" "$PROMPT_FILE"
  exit 0
fi

echo ""
echo "==> Evals red. Writing fix prompt to $PROMPT_FILE..."

cat > "$PROMPT_FILE" <<EOF
# Fix the failing evals

The eval suite for the temporal transaction AI agent just failed. Full
pytest output is at the end of this file.

## Constraints
You may only edit files under \`temporal-tx-agent/ai/\` (that's where
the AI prompts, decision thresholds, and model wiring live). Do NOT
touch the tests in \`evals/\`, the Temporal workflows, the Couchbase
code, or the FastAPI layer. If a fix would require changes outside
\`ai/\`, explain why and stop.

## Loop
Once you've made edits, re-run:

    python record_from_scenarios.py
    pytest evals/test_temporal_tx_coverage.py -v

and iterate until every test passes. Each \`record_from_scenarios.py\`
call spends ~5 short LLM calls against the configured provider, so
iterate at most 3 times.

## Pytest output

\`\`\`
$(cat "$OUT")
\`\`\`
EOF

rm -f "$OUT"

echo ""

case "$AGENT" in
  opencode)
    if ! command -v opencode >/dev/null 2>&1; then
      echo "opencode CLI not found. Install from https://opencode.ai," >&2
      echo "or run: AGENT=paste ./fix.sh to just get the prompt file." >&2
      echo "Prompt is in $PROMPT_FILE." >&2
      exit 2
    fi
    echo "==> Handing prompt to opencode (headless)..."
    opencode run "$(cat "$PROMPT_FILE")"
    ;;
  claude)
    if ! command -v claude >/dev/null 2>&1; then
      echo "claude CLI not found. Install Claude Code," >&2
      echo "or run: AGENT=paste ./fix.sh to just get the prompt file." >&2
      echo "Prompt is in $PROMPT_FILE." >&2
      exit 2
    fi
    echo "==> Handing prompt to claude (headless, accepting file edits)..."
    claude -p --permission-mode acceptEdits "$(cat "$PROMPT_FILE")"
    ;;
  cursor)
    if ! command -v cursor-agent >/dev/null 2>&1; then
      echo "cursor-agent CLI not found. Install from https://cursor.com/cli," >&2
      echo "or run: AGENT=paste ./fix.sh to just get the prompt file." >&2
      echo "Prompt is in $PROMPT_FILE." >&2
      exit 2
    fi
    echo "==> Handing prompt to cursor-agent (headless)..."
    cursor-agent -p "$(cat "$PROMPT_FILE")"
    ;;
  aider)
    if ! command -v aider >/dev/null 2>&1; then
      echo "aider not found. Install with 'pip install aider-install && aider-install'," >&2
      echo "or run: AGENT=paste ./fix.sh to just get the prompt file." >&2
      echo "Prompt is in $PROMPT_FILE." >&2
      exit 2
    fi
    echo "==> Handing prompt to aider (--message --yes-always on temporal-tx-agent/ai/*.py)..."
    aider --message "$(cat "$PROMPT_FILE")" --yes-always temporal-tx-agent/ai/*.py
    ;;
  paste)
    echo "==> AGENT=paste — no CLI invoked."
    echo "Open $PROMPT_FILE and paste the contents into your agent of choice:"
    echo "  - Copilot Chat inside VS Code"
    echo "  - Cursor Chat / Windsurf Chat / Zed AI"
    echo "  - ChatGPT / Claude web UI"
    ;;
  copilot)
    echo "==> gh copilot doesn't support headless file edits."
    echo "Prompt saved to $PROMPT_FILE. Options:"
    echo "  1. Open .fix-prompt.md and paste into GitHub Copilot Chat in VS Code."
    echo "  2. Use OpenCode with a Copilot backend model: AGENT=opencode ./fix.sh"
    ;;
  *)
    echo "Unknown AGENT=$AGENT" >&2
    echo "Supported: opencode (default), claude, cursor, aider, paste, copilot" >&2
    echo "Prompt saved to $PROMPT_FILE anyway." >&2
    exit 2
    ;;
esac
