from typing import AsyncIterator, Iterator
import os

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.run.workflow import WorkflowRunOutputEvent, WorkflowRunEvent
from agno.tools.file import FileTools
from agno.tools.linear import LinearTools
from agno.tools.slack import SlackTools
from agno.workflow import Step, Workflow
from agno.workflow.parallel import Parallel
from dotenv import load_dotenv
load_dotenv()

model = Nebius(id="moonshotai/Kimi-K2-Instruct", api_key=os.getenv("NEBIUS_API_KEY"))


slack_tools = SlackTools(token=os.getenv("SLACK_BOT_TOKEN"))
linear_tools = LinearTools(api_key=os.getenv("LINEAR_API_KEY"))
file_tools = FileTools()


linear_agent = Agent(
    name="Linear Task Agent",
    model=model,
    tools=[linear_tools],
    instructions=(
        "You are a productivity assistant. "
        "Your job is to create clear, actionable tasks in Linear based on meeting notes or summaries."
        "For each action item, include a concise title, detailed description, assignee, and deadline if specified. "
        "Reference specific decisions and responsibilities from the meeting notes. "
        "If priorities or deadlines are mentioned, include them."
    ),
    markdown=True,
)

slack_agent = Agent(
    name="Slack Notification Agent",
    tools=[slack_tools],
    model=model,
    instructions=(
        "You are a communication assistant. "
        "Send a friendly, informative Slack message to the #agent-chat channel summarizing the meeting outcomes. "
        "Highlight key decisions, assigned tasks (with assignees and deadlines), pricing strategy ($10,000 charge, $2,000 build cost), "
        "and next steps. Use bullet points for clarity and mention any upcoming meetings or deadlines.\n\n"
        "Example message:\n"

        "Hey team! Here's a quick recap of our key decisions from today's session:"
        "🎯 Key Decisions:"
        "• Pricing set at $10,000.\n"
        "• Build cost approved for $2,000.\n\n"
        "📋 Assigned Tasks:\n"
        "• Set up repo: Assigned to Alice, due by 2025-09-20.\n"
        "• Draft proposal: Assigned to Bob, due by 2025-09-18.\n\n"
        "🚴‍♂️ Next Steps:"
        "\n"
        "• Schedule follow-up meeting.\n"
        "• Finalize requirements with the client."
        "You'll find the tasks in Linear. Let's keep the momentum going! 🚀"
    ),
)

meeting_task_agent = Agent(
    name="Meeting Transcription Agent",
    tools=[file_tools],
    model=model,
    instructions=(
        "You are a meeting transcription assistant. You'll find the meeting notes at {file_path}. (only read this file, Don't modify it) "
        "Transcribe the provided meeting notes into a clean, readable summary. "
        "Capture all important discussion points, including project goals, cost estimates, product tiers, pricing strategy, technical stack, timeline, "
        "decisions, and assigned tasks with deadlines. Format the summary with clear headings and bullet points for easy reading."
        "Write the summary in ./meeting_summary.md file."
    ),
    markdown=True,
)

summary_agent = Agent(
    name="Meeting Summary Agent",
    model=model,
    instructions=(
        "You are a summarization assistant. "
        "Generate a concise summary of the meeting, focusing on main topics, decisions, pricing ($10,000 charge, $2,000 build cost), "
        "assigned tasks, and next steps. Format the summary for easy reading and quick reference.\n\n"
        "Also mention: You can also see a quick summary on Slack and tasks on Linear.\n\n"
        "Example summary:\n"
        "# 📋 Meeting Summary\n"
        "## 🎯 Main Topics\n"
        "- Project goals and timeline\n"
        "- Pricing strategy\n"
        "- Technical stack\n\n"
        "## 💡 Decisions\n"
        "| Decision      | Details         |\n"
        "|--------------|-----------------|\n"
        "| Pricing       | $10,000 charge  |\n"
        "| Build Cost    | $2,000          |\n"
        "| Tech Stack    | Python, React   |\n\n"
        "## 📝 Assigned Tasks\n"
        "| Task           | Assignee | Deadline    |\n"
        "|---------------|---------|-------------|\n"
        "| Set up repo    | Alice   | 2025-09-20  |\n"
        "| Draft proposal | Bob     | 2025-09-18  |\n\n"
        "## 🚴‍♂️ Next Steps\n"
        "- Schedule follow-up meeting\n"
        "- Finalize requirements\n"
        "- Confirm pricing with client\n\n"
        "_You can also see a quick summary on Slack and tasks on Linear._"
    ),
    markdown=True,
)

meeting_transcription_task = Step(
    name="Meeting Transcription Task",
    agent=meeting_task_agent,
)
linear_task = Step(
    name="Linear Task",
    agent=linear_agent,
)
slack_notification_task = Step(
    name="Slack Notification Task",
    agent=slack_agent,
)
summary_task = Step(
    name="Summary Task",
    agent=summary_agent,
)

workflow = Workflow(
    name="Enhanced Meeting Assistant Workflow",
    steps=[
        meeting_transcription_task,
        Parallel(
            slack_notification_task,
            linear_task,
            name="Notification Tasks",
        ),
        summary_task,
    ],
)

if __name__ == "__main__":
    workflow.print_response(
        "Process the meeting notes: summarize, create Linear tasks, and send a Slack notification with key outcomes."
    )