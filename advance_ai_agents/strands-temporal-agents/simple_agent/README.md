# Simple Agent

Basic Strands agent demonstrating simple and Temporal implementations with time, file, and weather tools.

## Files

- **agent.py** - Simple agent with direct execution
- **temporal_agent.py** - Temporal workflow and activities
- **worker.py** - Temporal worker process
- **client.py** - Temporal client interface
- **test_workflow.py** - Workflow tests

## Quick Start

### Simple Agent

```bash
cd simple_agent
python agent.py
```

Try these queries:
- "What time is it?"
- "List Python files"
- "What's the weather in Tokyo?"

### Temporal Agent

**Terminal 1: Start Temporal Server**
```bash
temporal server start-dev
```

**Terminal 2: Start Worker**
```bash
cd simple_agent
python worker.py
```

**Terminal 3: Run Client**
```bash
cd simple_agent
python client.py
```

## Configuration

Uses configuration from `../config.py`:
- Nebius LiteLLM settings
- Temporal connection
- Timeout values

## Tools

Both implementations provide:
- **get_time()** - Current timestamp
- **list_files()** - List Python files in current directory
- **get_weather(city)** - Weather data from wttr.in

## Testing

```bash
cd simple_agent
pytest test_workflow.py
```

## Architecture

**Simple Agent**: Direct function calls
```
User Query → Agent → Tools → Result
```

**Temporal Agent**: Distributed workflow
```
User Query → Client → Temporal Server → Worker → Activities → Result
```

See main README for more details.
