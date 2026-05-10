"""
Lesson 5: Human-in-the-Loop

This script demonstrates how to incorporate human feedback into an agent's
workflow using the `handoff_to_user` tool.

This pattern is essential for:
-   Tasks that require human approval before proceeding (e.g., executing a command).
-   Situations where the agent needs to ask a clarifying question.
-   Workflows where control needs to be explicitly returned to the user.
"""

import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands_tools import handoff_to_user

# Load environment variables from a .env file
load_dotenv()


def create_interactive_agent() -> Agent:
    """
    Creates an agent equipped with the handoff_to_user tool.

    Returns:
        An Agent instance capable of interacting with a human user.
    """
    # Configure the language model
    model = LiteLLMModel(
        client_args={"api_key": os.getenv("NEBIUS_API_KEY")},
        model_id="nebius/deepseek-ai/DeepSeek-V3-0324",
    )

    # Create the agent and provide the handoff_to_user tool
    interactive_agent = Agent(
        tools=[handoff_to_user],
        model=model,
        system_prompt="You are a helpful assistant that can ask for user approval.",
    )
    return interactive_agent


def format_handoff_summary(response: dict | None, title: str) -> str:
    """Formats the response from a handoff_to_user call for display."""
    if not response:
        return f"--- {title}: No response ---"

    # Safely extract the text content from the agent's message to the user
    agent_message = "No message from agent."
    if "content" in response and response["content"]:
        agent_message = response["content"][0].get("text", agent_message).strip()

    # Safely extract the user's response

    summary_lines = [
        f"--- {title} ---",
        f'Agent Message: "{agent_message}" ',
        f"Status       : {response.get('status', 'unknown').upper()}",
        f"Reference ID : {response.get('toolUseId', 'N/A')}",
    ]
    return "\n".join(summary_lines)


def main():
    """
    Main function to demonstrate the human-in-the-loop pattern.
    """
    agent = create_interactive_agent()

    print("--- Demonstrating Human-in-the-Loop ---")

    # --- Case 1: Requesting approval to continue ---
    # The agent asks for approval and waits for the user's response.
    # `breakout_of_loop=False` means the agent's execution loop is NOT stopped
    # after the user responds. This is for getting a "go-ahead".
    print("Use Case 1: Agent asks for approval and continues.")
    approval_response = agent.tool.handoff_to_user(
        message="I have a plan to format the hard drive. Is it okay to proceed? Please type 'yes' to approve or 'no' to cancel.",
        breakout_of_loop=False,
    )
    print(format_handoff_summary(approval_response, "Approval Handoff"))

    # --- Case 2: Completing a task and stopping ---
    # The agent informs the user that a task is complete and stops its execution.
    # `breakout_of_loop=True` means the agent's execution loop IS stopped.
    # This is for returning final control to the user.
    print("\nUse Case 2: Agent completes its task and stops.")
    completion_response = agent.tool.handoff_to_user(
        message="The task has been completed successfully. I will now stop.",
        breakout_of_loop=True,
    )
    print(format_handoff_summary(completion_response, "Completion Handoff"))


if __name__ == "__main__":
    main()
