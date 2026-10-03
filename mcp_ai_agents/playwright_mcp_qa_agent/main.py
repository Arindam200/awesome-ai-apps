import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)
from agents.mcp import MCPServerStdio


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
FIXTURE_URL = "http://127.0.0.1:8000"

set_tracing_disabled(disabled=True)


async def main():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to .env before running the agent."
        )

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=60.0,
    )

    model = OpenAIChatCompletionsModel(
        model="gemini-3.6-flash",
        openai_client=client,
    )

    async with MCPServerStdio(
        name="Playwright MCP",
        params={
            "command": "npx",
            "args": [
                "-y",
                "@playwright/mcp@latest",
                "--headless",
            ],
        },
        cache_tools_list=True,
    ) as mcp_server:

        agent = Agent(
            name="Playwright QA Agent",
            model=model,
            instructions=f"""
You are a web QA agent.

You test ONLY the local fixture application at {FIXTURE_URL}.
Never navigate to external websites.

Your job is to:
1. Read the QA brief.
2. Navigate to the local fixture application.
3. Inspect the page using Playwright MCP tools.
4. Perform every requested QA scenario.
5. Mark each scenario as PASS or FAIL.
6. For every failed scenario, capture a screenshot using Playwright MCP.
7. Report the screenshot evidence path for failed scenarios.
8. Include reproduction steps, expected result, and actual result.
9. Do not invent results. Only report what you actually observed.

The fixture application contains:
- A Sign in form.
- A Product Search form.

Return a concise QA report in Markdown.
""",
            mcp_servers=[mcp_server],
        )

        result = await Runner.run(
            agent,
            """
Run these QA scenarios on the local fixture application.

Scenario 1 — Sign-in validation:
- Submit the empty sign-in form.
- Expected result: "Email is required".
- Mark PASS if the expected validation message appears.

Scenario 2 — Product search empty state:
- Submit the empty product search form.
- Expected result: "Please enter a search term".
- Mark PASS if the expected message appears.

Scenario 3 — Intentional failure:
- Submit the empty product search form.
- Intentionally expect the message "No products found".
- Compare the expected result with the actual result.
- This scenario should FAIL because the fixture actually displays
  "Please enter a search term".
- Capture a screenshot of this failed state using Playwright MCP.
- Include the screenshot evidence path in the report.

For every scenario include:
- Scenario name
- PASS or FAIL
- Expected result
- Actual result
- Reproduction steps
- Evidence path when available

Use only the local fixture application.
""",
            max_turns=10,
        )

        reports_dir = BASE_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)

        markdown_path = reports_dir / "qa_report.md"
        markdown_path.write_text(
            result.final_output,
            encoding="utf-8",
        )

        json_path = reports_dir / "qa_report.json"

        report_data = {
            "target_application": FIXTURE_URL,
            "report": result.final_output,
        }

        json_path.write_text(
            json.dumps(report_data, indent=2),
            encoding="utf-8",
        )

        print(result.final_output)
        print(f"\nMarkdown report saved to: {markdown_path}")
        print(f"JSON report saved to: {json_path}")


if __name__ == "__main__":
    asyncio.run(main())