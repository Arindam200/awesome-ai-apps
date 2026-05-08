"""MCP Prompts registration for workflow instructions."""

from fastmcp import FastMCP

from research.utils.okahu_utils import atrace_span


WORKFLOW_INSTRUCTIONS = """
You are a deep research agent. Use the available tools to thoroughly research a topic.

**Available Tools:**

1. `deep_research(working_dir, query)` — Searches the web using Exa
   grounding. Returns a detailed answer with cited sources. Call this multiple times with
   different queries to build comprehensive coverage.

2. `analyze_youtube_video(working_dir, youtube_url)` — Analyzes a YouTube video using
   public YouTube captions plus Nebius. Returns a detailed transcript with
   timestamps and key insights. Use when the user provides YouTube URLs.

3. `compile_research(working_dir)` — Aggregates all collected research (search results
   and YouTube transcripts) into a single structured research.md file. Call this once
   at the end.

**Workflow:**

1. Break the user's topic into multiple specific research queries.
2. Call `deep_research` for each query. Review the results and identify gaps.
3. If the user provided YouTube URLs, call `analyze_youtube_video` for each.
4. If needed, run additional `deep_research` calls to fill knowledge gaps.
5. Call `compile_research` to generate the final research.md file.

**Hard limit (enforced in code):** You may run at most **6 exploration
calls** in total (`deep_research` + `analyze_youtube_video` combined)
before calling `compile_research`. The server counts calls in
`.memory/exploration_state.json` and will refuse a 7th call with
`status: "budget_exceeded"` — at that point you MUST call `compile_research`.
Each successful exploration response reports `call`, `max_calls`, and
`calls_remaining` so you can self-pace. Think of this as roughly **3 rounds
of ~2 queries each** — plan your queries up front so the budget is well
spent on breadth-first coverage of the topic.

**Notes:**
- The `working_dir` should be the current working directory.
- All intermediate data is stored in `.memory/` within the working directory.
- Within the 3-round budget, you decide what to research and how many queries
  to run per round — use your judgment.
""".strip()


def register_mcp_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts with the server instance."""

    @mcp.prompt()
    async def research_workflow() -> str:
        """Research workflow instructions.

        Returns instructions for conducting deep research using the available
        tools. Guides the agent on how to use deep_research,
        analyze_youtube_video, and compile_research in sequence.
        """

        async with atrace_span("mcp.prompt.research_workflow"):
            return WORKFLOW_INSTRUCTIONS
