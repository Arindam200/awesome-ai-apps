"""
Mobile SSH Agent Setup

Sets up a remote server for running AI coding agents (Claude Code, Codex CLI,
Aider) over SSH — useful for accessing agents from mobile devices, tablets,
or any thin client with an SSH app.

Usage:
    python main.py
"""

import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

SSH_HOST = os.getenv("SSH_HOST", "")
SSH_USER = os.getenv("SSH_USER", "")
SSH_PORT = os.getenv("SSH_PORT", "22")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH", "~/.ssh/id_rsa")
AGENT_CLI = os.getenv("AGENT_CLI", "claude")  # claude, codex, aider


def run_ssh(command: str, interactive: bool = False):
    """Run a command on the remote server via SSH."""
    args = [
        "ssh",
        "-p", SSH_PORT,
        "-i", os.path.expanduser(SSH_KEY_PATH),
        "-o", "StrictHostKeyChecking=no",
        f"{SSH_USER}@{SSH_HOST}",
    ]
    if interactive:
        args.insert(1, "-t")
    args.append(command)

    if interactive:
        return subprocess.run(args)
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def check_connection() -> bool:
    """Verify SSH connectivity to the remote server."""
    print(f"Connecting to {SSH_USER}@{SSH_HOST}:{SSH_PORT}...")
    result = run_ssh("echo ok")
    if result.returncode == 0:
        print("SSH connection successful.")
        return True
    print("Failed to connect. Check your SSH credentials and server address.")
    return False


def ensure_node() -> bool:
    """Check if Node.js is available; install via nvm if missing."""
    result = run_ssh("node --version 2>/dev/null || echo MISSING")
    if "MISSING" not in result.stdout:
        print(f"Node.js found: {result.stdout.strip()}")
        return True

    print("Node.js not found. Installing via nvm...")
    cmd = (
        "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && "
        'export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm install --lts'
    )
    result = run_ssh(cmd)
    if result.returncode == 0:
        print("Node.js installed.")
        return True
    print(f"Node.js install failed: {result.stderr}")
    return False


def install_agent(agent: str) -> bool:
    """Install the specified coding agent CLI on the remote server."""
    install_commands = {
        "claude": "npm install -g @anthropic-ai/claude-code",
        "codex": "npm install -g @openai/codex",
        "aider": "pip install aider-chat",
    }
    cmd = install_commands.get(agent)
    if not cmd:
        print(f"Unknown agent: {agent}. Supported: {', '.join(install_commands)}")
        return False

    print(f"Installing {agent}...")
    if agent in ("claude", "codex"):
        cmd = f'export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" 2>/dev/null; {cmd}'

    result = run_ssh(cmd)
    if result.returncode == 0:
        print(f"{agent} installed successfully.")
        return True
    print(f"Failed to install {agent}: {result.stderr}")
    return False


def start_session(agent: str):
    """Open an interactive agent session on the remote server."""
    print(f"\nStarting {agent} on {SSH_HOST}...")
    print("Tip: you can also connect from your phone with a mobile SSH client.\n")

    if agent in ("claude", "codex"):
        cmd = f'export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" 2>/dev/null; {agent}'
    else:
        cmd = agent

    run_ssh(cmd, interactive=True)


def main():
    if not SSH_HOST or not SSH_USER:
        print("Error: SSH_HOST and SSH_USER must be set in your .env file.")
        print("See .env.example for required variables.")
        sys.exit(1)

    if not check_connection():
        sys.exit(1)

    # Node.js is required for Claude Code and Codex CLI
    if AGENT_CLI in ("claude", "codex") and not ensure_node():
        print("Could not set up Node.js. Install it manually on the server.")
        sys.exit(1)

    # Check if agent is already installed
    nvm_prefix = 'export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" 2>/dev/null; '
    check_cmd = f"{nvm_prefix}which {AGENT_CLI} 2>/dev/null || echo MISSING"
    result = run_ssh(check_cmd)

    if "MISSING" in result.stdout:
        if not install_agent(AGENT_CLI):
            sys.exit(1)
    else:
        print(f"{AGENT_CLI} is already installed.")

    start_session(AGENT_CLI)


if __name__ == "__main__":
    main()
