.PHONY: run start stop restart install open logs

## Start the Dexter server (port 8080)
run: ; uv run python3 src/main.py
start: run  ## alias for run

## Force-kill anything on port 8080/8081 (use this instead of Ctrl+C)
stop:
	@lsof -ti :8080 | xargs kill -9 2>/dev/null; lsof -ti :8081 | xargs kill -9 2>/dev/null; echo "✅ Ports cleared"

## Stop then start fresh
restart: stop
	sleep 1.5
	uv run python3 src/main.py

## Install dependencies into .venv
install:
	uv venv && uv pip install -r requirements.txt

## Open the UI in the default browser
open:
	open http://localhost:8080

## Tail server output (attach to a running server's process)
logs:
	@lsof -ti :8080 | xargs -I{} sh -c 'echo "Attaching to PID {}"; tail -f /proc/{}/fd/1 2>/dev/null || echo "Use the terminal where uv run is executing to see logs"'
