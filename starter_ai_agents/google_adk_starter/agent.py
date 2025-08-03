from dotenv import load_dotenv
import os
import os

# Load keys
# Load keys
load_dotenv()
import resend
import resend
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

resend.api_key = os.getenv("RESEND_API_KEY")

# Define the email sending function
def send_email(_: str) -> dict:
    """
    Sends an email using the Resend API.

    Args:
        _: str: Placeholder argument (not used).

    Returns:
        dict: A dictionary containing the status and message ID or error message.
    """
    try:
        params = {
            "from": "Anand Demo <hi@mranand.com>",  # Replace with your verified sender email
            "to": ["studioone.tech@gmail.com"],  # Replace with the recipient's email address
            "subject": "Test Email from Google ADK",
            "html": "<p>This is a test email sent from a Google ADK agent using Resend.</p>",
        }
        response = resend.Emails.send(params)
        return {"status": "success", "message_id": response.get("id")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Initialize the LiteLlm model
model = LiteLlm(
    model="openai/meta-llama/Meta-Llama-3.1-8B-Instruct",
    api_base=os.getenv("NEBIUS_API_BASE"),
    api_key=os.getenv("NEBIUS_API_KEY")
)

# Define the EmailAgent
root_agent = Agent(
    name="EmailAgent",
    model=model,
    description="Agent that sends emails using the Resend API.",
    instruction="Use the send_email tool to send an email.",
    tools=[send_email]
)

# Execute the email sending function
result = send_email("")
print(result)

