\# Playwright MCP Web QA Agent



> An AI-powered web QA agent that uses Playwright MCP to test a local web application from a natural-language QA brief.



The agent reads a QA brief, uses Playwright tools exposed through the Model Context Protocol (MCP) to interact with a local fixture application, verifies expected behavior, and produces structured QA results with evidence for failed checks.



\## 🚀 Features



\* \*\*Natural-language QA briefs\*\*: Describe the web checks the agent should perform.

\* \*\*Playwright MCP browser automation\*\*: Navigate, inspect, fill forms, click controls, and verify UI behavior through Playwright MCP.

\* \*\*PASS/FAIL validation\*\*: Compare observed behavior against expected results.

\* \*\*Failure evidence\*\*: Capture screenshots for failed QA scenarios.

\* \*\*Markdown report\*\*: Generate a human-readable QA report.

\* \*\*JSON report\*\*: Generate machine-readable QA output.

\* \*\*Local-only testing\*\*: Uses an included fixture application and does not automate third-party websites.

\* \*\*Intentional failure scenario\*\*: Demonstrates how the agent reports a failed QA check.



\## 🛠️ Tech Stack



\* \*\*Python\*\*: Core application and agent orchestration

\* \*\*OpenAI Agents SDK\*\*: Runs the QA agent

\* \*\*Gemini API\*\*: Provides the language model through the OpenAI-compatible API

\* \*\*Playwright MCP\*\*: Provides browser automation tools through MCP

\* \*\*Model Context Protocol (MCP)\*\*: Connects the AI agent to browser tools

\* \*\*HTML/CSS/JavaScript\*\*: Local fixture application

\* \*\*JSON/Markdown\*\*: QA report formats



\## Workflow



```text

QA Brief

&#x20;  │

&#x20;  ▼

Playwright QA Agent

&#x20;  │

&#x20;  ▼

Playwright MCP Server

&#x20;  │

&#x20;  ▼

Local Fixture Application

&#x20;  │

&#x20;  ├── PASS → QA result

&#x20;  │

&#x20;  └── FAIL → Screenshot + QA result

&#x20;               │

&#x20;               ▼

&#x20;       Markdown + JSON Reports

```



The agent is restricted to the local fixture application at:



```text

http://127.0.0.1:8000

```



It receives a QA brief, opens the fixture application through Playwright MCP, performs the requested interactions, checks the observed results, and reports PASS or FAIL.



For failed scenarios, the agent is instructed to capture screenshot evidence.



\## 📦 Getting Started



\### Prerequisites



\* Python 3.10+

\* Node.js 18+

\* npm

\* Gemini API key



\### Environment Variables



Create a `.env` file in the project root:



```env

GEMINI\_API\_KEY=your\_gemini\_api\_key\_here

```



Do not commit the `.env` file.



A safe template is provided as:



```text

.env.example

```



\### Installation



From the project directory:



```bash

pip install -r requirements.txt

```



The Playwright MCP server is launched automatically by the agent using:



```bash

npx -y @playwright/mcp@latest --headless

```



No separate MCP server installation is required.



\## ⚙️ Usage



\### 1. Start the local fixture application



From the project directory:



```bash

python -m http.server 8000 --directory ./fixture\_app

```



The application will be available at:



```text

http://127.0.0.1:8000

```



Keep this terminal running.



\### 2. Run the QA agent



Open a second terminal in the project directory:



```bash

python main.py

```



The agent will connect to the local fixture through Playwright MCP and execute the QA scenarios.



\## QA Scenarios



\### 1. Sign-in Validation



The agent submits the sign-in form with both fields empty.



Expected result:



```text

Email is required

```



This scenario should PASS.



\### 2. Product Search Empty State



The agent submits the product search form without entering a search term.



Expected result:



```text

Please enter a search term

```



This scenario should PASS.



\### 3. Intentional Failure



The agent submits the empty product search form but intentionally expects:



```text

No products found

```



The fixture actually returns:



```text

Please enter a search term

```



Therefore, this scenario should be reported as FAIL and screenshot evidence should be captured.



\## 📂 Project Structure



```text

playwright\_mcp\_qa\_agent/

├── fixture\_app/

│   ├── index.html

│   ├── script.js

│   └── style.css

├── reports/

├── screenshots/

├── .env.example

├── .gitignore

├── main.py

├── requirements.txt

└── README.md

```



\### Fixture Application



The `fixture\_app/` directory contains the local web application used for testing.



\### Reports



The `reports/` directory contains generated QA reports:



```text

reports/

├── qa\_report.md

└── qa\_report.json

```



\### Screenshots



The `screenshots/` directory is used for screenshot evidence from failed QA checks.



\## Safety and Scope



This project is intentionally designed for local testing.



The QA agent is instructed to:



\* Use only the local fixture application.

\* Never navigate to external websites.

\* Never use credentials.

\* Never automate third-party websites.



The fixture application is included in the repository so the example can be run without external dependencies or accounts.



\## Example QA Brief



```text

Verify sign-in validation and the product search empty state.



For sign-in:

\- Submit the empty form.

\- Verify that an email validation message is displayed.



For product search:

\- Submit an empty search.

\- Verify that an appropriate empty-search message is displayed.

```



\## Acknowledgments



\* \[Playwright MCP](https://github.com/microsoft/playwright-mcp)

\* \[Model Context Protocol](https://modelcontextprotocol.io/)

\* \[OpenAI Agents SDK](https://github.com/openai/openai-agents-python)

\* \[Google Gemini API](https://ai.google.dev/)



