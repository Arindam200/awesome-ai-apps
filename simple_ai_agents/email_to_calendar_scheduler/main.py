from agno.agent import Agent
from typing import Iterator
from agno.team import Team, TeamRunOutputEvent
from agno.models.nebius import Nebius
from agno.tools.gmail import GmailTools
from agno.tools.googlesheets import GoogleSheetsTools
from agno.tools.googlecalendar import GoogleCalendarTools
import dotenv
from dotenv import load_dotenv
from agno.utils.pprint import pprint_run_response
from agno.db.sqlite import SqliteDb
import os
import sys


load_dotenv()
nebius_api_key = os.getenv("NEBIUS_API_KEY")
timezone = os.getenv("TIMEZONE")
# Validate required environment variables
if not nebius_api_key:
    print("❌ Error: NEBIUS_API_KEY not found in environment.")
    print("Please set NEBIUS_API_KEY in your .env file.")
    sys.exit(1)
if not timezone:
    print("❌ Error: TIMEZONE not found in environment.")
    print("Please set TIMEZONE in your .env file (e.g., 'America/New_York').")
    sys.exit(1)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_PATH = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_PATH = os.path.join(SCRIPT_DIR, "token.json")
DB_PATH = os.getenv("DB_PATH", os.path.join(SCRIPT_DIR, "tmp", "data.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
# Validate required files
if not os.path.exists(CREDS_PATH):
    print("❌ Error: credentials.json not found.")
    print("Please download OAuth credentials from Google Cloud Console.")
    print("See README.md for setup instructions.")
    sys.exit(1)

if not os.path.exists(TOKEN_PATH):
    print("❌ Error: token.json not found.")
    print("Please run 'python authenticate.py' first to generate the token.")
    sys.exit(1)

db = SqliteDb(db_file=DB_PATH)


email_agent = Agent(
    model=Nebius(id="Qwen/Qwen3-32b", api_key=nebius_api_key),
    markdown=True,
    tools=[GmailTools(credentials_path=CREDS_PATH, port=8090)],
    description="You are a Gmail reading specialist that can search and read emails.",
    instructions=[
        "Use the tools to search and read emails from Gmail.",
        "Focus on extracting key details such as sender, subject, and body of the email.",
        "Summarize the body of the email concisely.",
        "Never fabricate email content; only use the information available in the emails.",
        "If no emails are found, respond with 'No emails found.'",
    ],
    db=db,
    add_history_to_context=True,
    num_history_runs=3,
    read_chat_history=True,
)


calendar_agent = Agent(
    model=Nebius(id="Qwen/Qwen3-32b", api_key=nebius_api_key),
    tools=[
        GoogleCalendarTools(
            credentials_path=CREDS_PATH,
            allow_update=True,
        )
    ],
    instructions=[
        f"""
    You are a scheduling assistant.
    You should help users to perform these actions in their Google calendar:
        - get their scheduled events from a certain date and time
        - create events based on provided details
        - update existing events
        - delete events
        - find available time slots for scheduling
        - all times are in {timezone}
    """
    ],
    add_datetime_to_context=True,
    db=db,
    add_history_to_context=True,
    num_history_runs=3,
    read_chat_history=True,
)


team = Team(
    name="Productivity Agent",
    members=[email_agent, calendar_agent],
    description="Team to extract emails, filter important emails  and update Google Calendar based on email content.",
    model=Nebius(id="Qwen/Qwen3-32b", api_key=nebius_api_key),
    instructions=[
        f"First, use the email agent to find and read the latest emails and extract the important emails with the important details such as sender, subject, and summarized body.",
        "Then, use the calendar agent to update Google Calendar based on the email content.",
        "If an Event is to be added, updated or deleted, ensure to provide all necessary details such as event name, date, time, and any other relevant information.",
        "If some details are missing for updating or adding an event, make reasonable assumptions based on the email content.",
        "Collaborate effectively to ensure accurate data extraction and updating.",
        "Output the final calendar updates made to Google Calendar.",
    ],
    db=db,
    add_history_to_context=True,
    num_history_runs=3,
    read_team_history=True,
)



print("🧠 Smart Scheduler Assistant is running. Type 'exit' to quit.\n")
user_input = input("You: ")

while True:
    if user_input.lower() in ["exit", "quit"]:
        print("Goodbye 👋")
        break
    
    if not user_input.strip():
        print("⚠️  Please enter a message.\n")
        user_input = input("You: ")
        continue

    try:
        run_response = team.run(user_input)
        print("\nAgent:", run_response.content, "\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    
    user_input = input("You: ")
