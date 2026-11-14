# Meeting-to-Action Voice Agent

A self-contained Python example that takes a meeting transcript (or audio transcript) and uses an LLM to extract structured operational outputs: action items, owners, deadlines, risks, blockers, and follow-ups.

## Features
- Reads a raw meeting transcript.
- Uses Nebius Token Factory (default), Ollama, or vLLM to extract structured data.
- **Uncertainty Handling:** Explicitly marks missing owners or deadlines as "Uncertain" instead of hallucinating.
- Exports pure JSON for downstream enterprise tools.

## Prerequisites

1. **Default provider: Nebius Token Factory.** Set your API key as an environment variable:
   ```bash
   export NEBIUS_API_KEY="your-api-key-here"
   ```
   The agent uses Nebius Token Factory automatically (`NEBIUS_API_BASE` defaults to `https://api.tokenfactory.nebius.com/v1/` with a Qwen model). See `.env.example` for all supported variables.

## Optional: Use Ollama locally

If you prefer to run the agent locally with Ollama, set the corresponding Nebius-style environment variables:
```bash
# (If running inside Docker, use http://host.docker.internal:11434/v1 instead)
export NEBIUS_API_BASE="http://localhost:11434/v1"
export NEBIUS_API_KEY="not-needed"
export MODEL_NAME="qwen2.5-coder:14b"   # or your preferred model
```
Then install Ollama and pull a compatible model:
```bash
# Install from https://ollama.com/
ollama run qwen2.5-coder:14b
```

## Setup & Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your environment variables (defaults to Nebius Token Factory):
   ```bash
   # Required for the Nebius default provider
   export NEBIUS_API_KEY="your-api-key-here"
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
