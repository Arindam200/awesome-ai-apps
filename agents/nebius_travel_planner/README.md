# VoyageCompass Travel Planner

A Streamlit travel planning app built with LangChain and Nebius. It is inspired
by AI travel-agent demos, but it uses a different app structure and planning
flow:

- Nebius `ChatNebius` through the `langchain-nebius` package
- Streamlit trip brief plus follow-up chat
- No OpenAI API key or ChatOpenAI usage
- No required search or weather API keys beyond `NEBIUS_API_KEY`
- Tools for geocoding, near-term weather, web research, currency conversion,
  budget estimates, and packing prep

## Setup

```bash
cd agents/nebius_travel_planner
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

Edit `.env` and add your Nebius API key:

```bash
NEBIUS_API_KEY=your-nebius-api-key
NEBIUS_MODEL=Qwen/Qwen3-30B-A3B
```

You can also paste the API key into the Streamlit sidebar or configure it in
Streamlit secrets.

## Run

```bash
streamlit run app.py
```

## How It Works

The app creates a LangChain agent with:

- `ChatNebius` from `langchain_nebius`
- `create_agent` from LangChain
- Tool calling for travel research and calculations
- A system prompt that requires grounded weather, search, and budget output

The LangChain Nebius provider docs are here:
https://docs.langchain.com/oss/python/integrations/providers/nebius

## Files

- `app.py` - Streamlit UI
- `agent.py` - Nebius LangChain agent setup
- `tools.py` - Travel tools
- `main.py` - Optional CLI check
- `env.example` - Environment template

## Notes

Weather uses Open-Meteo's no-key forecast APIs. Forecasts are limited to the
near-term forecast window, so plans for dates far in the future should treat
weather guidance as seasonal planning context rather than a live forecast.

Currency conversion uses Frankfurter's public exchange-rate API. Budget output
starts with transparent estimates and should be refined with destination search
results for current prices.
