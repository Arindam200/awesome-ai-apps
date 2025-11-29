# 🧠 Smart Scheduler Assistant

> An intelligent AI-powered assistant that reads your Gmail, filters important emails, and automatically manages your Google Calendar.

An advanced multi-agent system that automates email management and calendar scheduling. Built with Agno framework, leveraging multiple specialized AI agents to streamline your productivity workflow.

## 🚀 Features

- **Smart Email Reading**: Automatically fetches and reads your latest Gmail messages with detailed extraction of sender, subject, and body content.
- **Intelligent Noise Filtering**: AI-powered content analysis to distinguish important emails from noise and spam.
- **Automated Calendar Management**: Seamlessly creates, updates, and deletes Google Calendar events based on email content.
- **Multi-Agent Collaboration**: Coordinated team of specialized agents working together for optimal results.
- **Conversational Interface**: Interactive command-line interface for natural language interactions.
- **Persistent Memory**: Built-in SQLite database to maintain conversation context and history.

## 🛠️ Tech Stack

- **Python**: Core programming language
- **Agno Framework**: For multi-agent AI orchestration
- **Nebius**: For fast LLM inference (Qwen 3 32B model)
- **Gmail API**: For email reading and management
- **Google Calendar API**: For calendar event management
- **SQLite**: For conversation history and agent memory

## Workflow

The Smart Scheduler Assistant operates through a coordinated multi-agent system:

1. **Email Agent** retrieves and reads the latest emails from your Gmail account, summarizes them and filters out unnecessary emails.
2. **Calendar Agent** processes the filtered emails and updates your Google Calendar accordingly
3. **Team Coordinator** orchestrates the workflow between all agents to ensure seamless operation

The system intelligently extracts event details from emails (dates, times, locations) and automatically schedules them in your calendar, making assumptions where necessary for missing information.

## 📦 Getting Started

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) or pip for package management
- API keys and credentials for the following services:
  - [NEBIUS API](https://tokenfactory.nebius.com/) for LLM access
  - Google Cloud Project with Gmail and Calendar APIs enabled
  - OAuth 2.0 credentials file (`credentials.json`)

### Environment Variables

Create a `.env` file in the project root and add the following variables:

```env
NEBIUS_API_KEY="your_NEBIUS_api_key_here"
TIMEZONE=<your-timezone-here>  # Use IANA timezone format (e.g., America/New_York, Asia/Kolkata, Europe/London)
```

### Google API Setup

Follow these steps carefully to set up Google Cloud credentials:

#### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top and select "New Project"
3. Give your project a name (e.g., "Smart Scheduler Assistant")
4. Click "Create" and wait for the project to be created
5. Select your newly created project from the project dropdown

#### Step 2: Enable Required APIs

1. In the Google Cloud Console, navigate to "APIs & Services" > "Library"
2. Search for "Gmail API" and click on it
3. Click the "Enable" button
4. Go back to the API Library
5. Search for "Google Calendar API" and click on it
6. Click the "Enable" button

#### Step 3: Create OAuth 2.0 Credentials

1. Navigate to "APIs & Services" > "Credentials"
2. Click "Create Credentials" at the top and select "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Select "External" user type and click "Create"
   - Fill in the required fields:
     - App name: "Smart Scheduler Assistant"
     - User support email: Your email
     - Developer contact email: Your email
   - Click "Save and Continue" through the scopes and test users sections
4. Back in the Credentials page, click "Create Credentials" > "OAuth client ID"
5. Select "Desktop app" as the application type
6. Give it a name (e.g., "Smart Scheduler Desktop Client")
7. Click "Create"

#### Step 4: Download Credentials

1. After creating the OAuth client, a dialog will appear with your credentials
2. Click "Download JSON"
3. Rename the downloaded file to `credentials.json`
4. Move `credentials.json` to your project root directory

#### Step 5: Authenticate and Generate Token

Before running the main application, you need to authenticate once to generate the `token.json` file:

1. Run the authentication script:

   ```bash
   python authenticate.py
   ```

2. A browser window will open automatically:

   - Select your Google account
   - Click "Allow" to grant access to Gmail and Calendar
   - You may see a warning that the app isn't verified - click "Advanced" and then "Go to Smart Scheduler Assistant (unsafe)"
   - Grant all the requested permissions

3. After successful authentication, a `token.json` file will be created in your project root

4. You're now ready to run the main application!

**Note:** The `token.json` file stores your access and refresh tokens. Keep this file secure and do not share it publicly. If you encounter authentication issues, simply delete `token.json` and run `authenticate.py` again.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/simple_ai_agents/email_to_calendar_scheduler
   ```

2. **Create and activate a virtual environment:**

   - **Using `venv`:**
     ```bash
     python -m venv .venv
     source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
     ```

3. **Install dependencies:**

   - **Using `uv` (recommended):**
     ```bash
     uv sync
     ```
   - **Using `pip`:**
     ```bash
     pip install -r requirements.txt
     ```

4. **Place your Google credentials:**
   - Ensure `credentials.json` is in the project root directory

## ⚙️ Usage

1. **Run the application:**

   ```bash
   python main.py
   ```

2. **Interact with the assistant:**

   - The assistant will greet you with: "🧠 Smart Scheduler Assistant is running. Type 'exit' to quit."
   - Type your requests in natural language, such as:
     - "Read my latest 5 emails and schedule any meetings"
     - "Check my calendar for tomorrow"
     - "Create an event for team meeting on Friday at 3 PM"
     - "Update the project review event to 4 PM"

3. **Exit the application:**
   - Type `exit` or `quit` to close the assistant

## 📂 Project Structure

```text
email_to_calendar_scheduler/
├── tmp/                   # SQLite database storage
│   └── data.db            # Agent memory and conversation history
├── .venv/                 # Virtual environment
├── .env                   # Environment variables (API keys)
├── credentials.json       # Google OAuth credentials(MUST BE GENERATED FIRST)
├── authenticate.py        # Authentication script to generate token.json
├── LICENSE
├── main.py                # Main application entry point
├── requirements.txt       # Python dependencies
└── README.md              # Project documentation
```

## 🔧 Configuration

You can customize the assistant's behavior by modifying these variables in `main.py`:

- Agent instructions and behavior can be customized in their respective definitions

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- Shoutout to [Agno Framework](https://github.com/agno-agi/agno) for their powerful multi-agent system.
- Thanks to [Nebius](https://tokenfactory.nebius.com/) for providing fast LLM inference.
- Built with the Qwen 3 32B model for intelligent reasoning and task execution.
