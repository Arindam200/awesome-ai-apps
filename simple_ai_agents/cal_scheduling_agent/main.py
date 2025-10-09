import os

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.models.openai.like import OpenAILike
from agno.tools.calcom import CalComTools
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

"""
Example showing how to use the Cal.com Tools with Agno.

Requirements:
- Cal.com API key (get from cal.com/settings/developer/api-keys)
- Event Type ID from Cal.com
- pip install requests pytz

Usage:
- Set the following environment variables:
    export CALCOM_API_KEY="your_api_key"
    export CALCOM_EVENT_TYPE_ID="your_event_type_id"

- Or provide them when creating the CalComTools instance
"""

INSTRUCTIONS = f"""You're a scheduling assistant. Today is {datetime.now()}.
You can help users by:
    - Finding available time slots using get_available_slots(start_date, end_date)
    - Creating new bookings using create_booking(start_time, name, email)
    - Managing existing bookings using get_upcoming_bookings(email)
    - Rescheduling bookings using reschedule_booking(booking_uid, new_start_time, reason)
    - Cancelling bookings using cancel_booking(booking_uid, reason)

IMPORTANT STEPS for booking:
1. First check available slots using get_available_slots
2. Then create booking using create_booking with the exact start_time, name, and email provided
3. Finally verify the booking was created using get_upcoming_bookings with the provided email

When asked to book a call, you MUST:
1. Call create_booking with the provided start_time, name, and email
2. Then verify the booking using get_upcoming_bookings
3. Confirm to the user whether the booking was successful

Remember:
- Dates should be in YYYY-MM-DD format
- Times should be in YYYY-MM-DDTHH:MM:SS+TZ format (e.g., 2024-03-20T14:30:00+05:30)
- Always confirm details before making changes
"""

# Create the CalCom tools instance
try:
    calcom_tools = CalComTools(
        user_timezone="Asia/Kolkata",
        api_key=os.environ['CALCOM_API_KEY'],
        event_type_id=os.environ.get('CALCOM_EVENT_TYPE_ID')  # Make sure to set this
    )
except Exception as e:
    print(f"Error initializing CalCom tools: {e}")
    exit(1)



# Create the agent
agent = Agent(
    name="Calendar Assistant",
    instructions=[INSTRUCTIONS],
    model=Nebius(
        id="Qwen/Qwen3-30B-A3B",
        api_key=os.getenv("NEBIUS_API_KEY") # Explicitly pass the API key
    ),
    tools=[calcom_tools],
    show_tool_calls=True,
    tool_choice="auto",
    markdown=True,
)

# Example of how to book a call
def book_example_call():
    # Get today's date and tomorrow's date
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # First, check available slots
    print("Checking available slots...")
    agent.print_response(f"""
    Please check available slots between {today} and {tomorrow}
    """)

    # Then book a specific slot
    print("\nAttempting to book a call...")
    agent.print_response("""
    Please book a call with these details:
    - Start Time: 2025-03-22T21:30:00+05:30
    - Name: Arindam Majumder
    - Email: studioone.tech@gmail.com

    After booking, please verify the booking exists.
    """)

if __name__ == "__main__":
    book_example_call()