"""
AG2 Due Diligence Pipeline

4-stage pipeline using AG2 ConversableAgents:
1. Seed Crawler - scrapes company URL for initial profile
2. 6 Specialist Agents - research in parallel via ThreadPoolExecutor
3. Validator - cross-checks collected data
4. Synthesis - produces final markdown report
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse

from autogen import AssistantAgent, UserProxyAgent

from prompts import (
    FINANCIALS,
    FINANCIALS_MSG,
    FOUNDERS_TEAM,
    FOUNDERS_TEAM_MSG,
    INVESTORS,
    INVESTORS_MSG,
    PRESS,
    PRESS_MSG,
    SEED_CRAWLER,
    SEED_CRAWLER_MSG,
    SOCIAL,
    SOCIAL_MSG,
    SYNTHESIS,
    TECH_STACK,
    TECH_STACK_MSG,
    VALIDATOR,
)


def _get_llm_config():
    """Build AG2 LLM config using Nebius API."""
    return {
        "model": os.getenv("NEBIUS_MODEL_ID", "deepseek-ai/DeepSeek-V3-0324"),
        "api_type": "openai",
        "base_url": "https://api.tokenfactory.nebius.com/v1",
        "api_key": os.getenv("NEBIUS_API_KEY"),
        "temperature": 0.3,
    }


def _register_tinyfish(assistant, executor):
    """Register TinyFishTool on both the assistant and executor agents."""
    from autogen.tools.experimental import TinyFishTool

    tool = TinyFishTool(api_key=os.getenv("TINYFISH_API_KEY"))
    tool.register_for_llm(assistant)
    tool.register_for_execution(executor)


def _extract_json(text):
    """Extract the first JSON object from agent output."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return {}


def _last_assistant_message(chat_result):
    """Get the last assistant message from a chat result."""
    for msg in reversed(chat_result.chat_history):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return ""


def _run_agent(name, system_prompt, message, use_tinyfish=True):
    """Run a single agent conversation and return the raw output text."""
    llm_config = _get_llm_config()

    assistant = AssistantAgent(
        name=name,
        system_message=system_prompt,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    executor = UserProxyAgent(
        name=f"{name}_executor",
        human_input_mode="NEVER",
        code_execution_config=False,
        is_termination_msg=lambda msg: "TASK_COMPLETE" in (msg.get("content") or ""),
    )

    if use_tinyfish:
        _register_tinyfish(assistant, executor)

    result = executor.initiate_chat(
        recipient=assistant,
        message=message,
        max_turns=10,
    )

    return _last_assistant_message(result)


def _run_specialist(spec_name, system_prompt, message):
    """Run a specialist agent, returning (name, raw_output, parsed_json)."""
    output = _run_agent(spec_name, system_prompt, message)
    parsed = _extract_json(output)
    return spec_name, output, parsed


def run_due_diligence(company_url, on_progress=None):
    """
    Run the full 4-stage due diligence pipeline.

    Args:
        company_url: The company website URL to research.
        on_progress: Optional callback(stage_number, message) for status updates.

    Returns:
        (output_dir, report_markdown)
    """

    def progress(stage, msg):
        if on_progress:
            on_progress(stage, msg)

    domain = urlparse(company_url).netloc or company_url
    slug = re.sub(r"[^a-z0-9]", "_", domain.lower().replace("www.", ""))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"due_diligence_{slug}_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    # Stage 1: Seed Crawler
    progress(1, "Crawling company website for initial profile...")
    seed_output = _run_agent(
        "seed_crawler", SEED_CRAWLER, SEED_CRAWLER_MSG.format(url=company_url)
    )
    seed_data = _extract_json(seed_output)

    with open(os.path.join(output_dir, "company_profile.json"), "w") as f:
        json.dump(seed_data, f, indent=2)

    company_name = seed_data.get("company_name", domain)
    team_urls = seed_data.get("team_page_urls", [])
    press_urls = seed_data.get("press_page_urls", [])
    job_urls = seed_data.get("job_urls", [])

    # Stage 2: Parallel Specialists
    progress(2, "Running 6 specialist agents in parallel...")

    specialists = {
        "founders_team": (
            FOUNDERS_TEAM,
            FOUNDERS_TEAM_MSG.format(
                company_name=company_name,
                seed_url=company_url,
                team_urls=", ".join(team_urls) if team_urls else "none found",
            ),
        ),
        "investors": (
            INVESTORS,
            INVESTORS_MSG.format(
                company_name=company_name, seed_url=company_url
            ),
        ),
        "press": (
            PRESS,
            PRESS_MSG.format(
                company_name=company_name,
                press_urls=", ".join(press_urls) if press_urls else "none found",
            ),
        ),
        "financials": (
            FINANCIALS,
            FINANCIALS_MSG.format(
                company_name=company_name, seed_url=company_url
            ),
        ),
        "tech_stack": (
            TECH_STACK,
            TECH_STACK_MSG.format(
                company_name=company_name,
                domain=domain,
                job_urls=", ".join(job_urls) if job_urls else "none found",
            ),
        ),
        "social": (
            SOCIAL,
            SOCIAL_MSG.format(
                company_name=company_name, seed_url=company_url
            ),
        ),
    }

    specialist_results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_run_specialist, name, prompt, msg): name
            for name, (prompt, msg) in specialists.items()
        }
        for future in as_completed(futures):
            name, _raw, parsed = future.result()
            specialist_results[name] = parsed
            with open(os.path.join(output_dir, f"{name}.json"), "w") as f:
                json.dump(parsed, f, indent=2)

    # Stage 3: Validator
    progress(3, "Validating collected data...")

    all_data = json.dumps({"seed": seed_data, **specialist_results}, indent=2)
    validator_msg = (
        f"Validate this due diligence data for {company_name}:\n\n{all_data}"
    )
    validator_output = _run_agent(
        "validator", VALIDATOR, validator_msg, use_tinyfish=False
    )
    validation = _extract_json(validator_output)

    with open(os.path.join(output_dir, "validation_notes.json"), "w") as f:
        json.dump(validation, f, indent=2)

    # Stage 4: Synthesis
    progress(4, "Synthesizing final report...")

    synthesis_msg = (
        f"Write a due diligence report for {company_name}.\n\n"
        f"Seed data:\n{json.dumps(seed_data, indent=2)}\n\n"
        f"Specialist findings:\n{json.dumps(specialist_results, indent=2)}\n\n"
        f"Validation notes:\n{json.dumps(validation, indent=2)}"
    )
    report = _run_agent(
        "synthesis", SYNTHESIS, synthesis_msg, use_tinyfish=False
    )

    report = report.replace("TASK_COMPLETE", "").strip()

    with open(os.path.join(output_dir, "report.md"), "w") as f:
        f.write(report)

    return output_dir, report
