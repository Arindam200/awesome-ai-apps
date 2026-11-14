# Meeting-to-Action Voice Agent

A self-contained Python example that takes a meeting transcript (or audio transcript) and uses an LLM to extract structured operational outputs: action items, owners, deadlines, risks, blockers, and follow-ups.

## Features
- Reads a raw meeting transcript.
- Uses an LLM (OpenAI, Ollama, or vLLM) to extract structured data.
- **Uncertainty Handling:** Explicitly marks missing owners or deadlines as "Uncertain" instead of hallucinating.
- Exports pure JSON for downstream enterprise tools.

## Prerequisites


1. Install Ollama from https://ollama.com/
2. Pull the default model by running: `ollama run llama3`


## Setup & Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your environment variables (defaults to local Ollama):
   ```bash
   # Example for Ollama
   export OPENAI_API_BASE="http://localhost:11434/v1"
   export MODEL_NAME="llama3"
   
   # Example for OpenAI
   # export OPENAI_API_KEY="sk-..."
   # export OPENAI_API_BASE="https://api.openai.com/v1"
   # export MODEL_NAME="gpt-4o-mini"
   ```

3. Run the agent:
   ```bash
   python main.py
   ```

4. Check the generated `output.json`.

## Sample Output
```json
{
    "action_items": [
        {
            "task": "Finalize the budget",
            "owner": "Sarah",
            "deadline": "Friday"
        },
        {
            "task": "Order more swag for the conference",
            "owner": "Uncertain",
            "deadline": "Uncertain"
        }
    ],
    "risks": ["Database migration"],
    "blockers": ["Waiting on design assets from the agency for the landing page"],
    "follow_ups": ["Table the database migration for now and follow up next week"]
}
```