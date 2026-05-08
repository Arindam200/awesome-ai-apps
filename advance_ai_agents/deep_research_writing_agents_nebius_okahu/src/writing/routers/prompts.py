"""MCP Prompts registration for workflow instructions."""

from fastmcp import FastMCP

from writing.utils.okahu_utils import atrace_span


WORKFLOW_INSTRUCTIONS = """
Your job is to execute the LinkedIn post writing workflow below.

All the tools require a `working_dir` parameter — the path to the working directory.
If the user doesn't provide it, ask for it before executing any tool.

The working directory must contain:
- `guideline.md` — describes what the post should be about (topic, angle, audience)
- `research.md` — provides factual material to draw from (from the research agent)

**Workflow:**

1. **Setup:**

    1.1. Explain the numbered steps of the workflow to the user. Be concise.

    1.2. Ask the user for the working directory path, if not provided. Verify that
    guideline.md and research.md exist in it.

2. **Generate the LinkedIn post:**

    Call the `generate_post` tool with the working_dir.

    This internally runs:
    - Generates an initial post from the guideline + research + writing profiles
    - Runs N rounds of review + edit (evaluator-optimizer loop)
    - Saves intermediate versions in .memory/
    - Saves the final post as post.md

    Present the final post to the user.

3. **Generate an image:**

    Call the `generate_image` tool with the working_dir.

    This generates a professional LinkedIn-appropriate image based on the post
    content and saves it as post_image.png.

    Present both the final post and the image to the user.

4. **Edit with feedback (optional, repeat as needed):**

    If the user wants changes, call the `edit_post` tool with the working_dir
    and their feedback.

    This runs one review+edit pass guided by the human feedback, which takes
    highest priority over all other constraints.

    Present the edited post to the user.

**File Structure After Completion:**

```
working_dir/
├── guideline.md                # Input: What the post should be about
├── research.md                 # Input: Research material to draw from
├── .memory/                    # Intermediate files (reviews JSON)
│   ├── reviews_1.json          # Reviews from iteration 1
│   └── reviews_2.json          # Reviews from iteration 2
├── post_0.md                   # Initial generated post (version 0)
├── post_1.md                   # Post after review/edit iteration 1
├── post_2.md                   # Post after review/edit iteration 2
├── post.md                     # Final LinkedIn post (same as latest version)
└── post_image.png              # Generated image
```

**Critical Failure Policy:**

If a tool reports a failure, halt the workflow:
1. State the exact tool that failed and quote the output.
2. Ask the user for guidance on how to proceed.
""".strip()


def register_mcp_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts with the server instance."""

    @mcp.prompt()
    async def linkedin_post_workflow() -> str:
        """Complete LinkedIn post writing workflow instructions.

        Returns the full workflow instructions for generating a LinkedIn post
        using the available tools.
        """

        async with atrace_span("mcp.prompt.linkedin_post_workflow"):
            return WORKFLOW_INSTRUCTIONS
