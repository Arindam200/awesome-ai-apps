"""Voice Incident Commander Agent.

A LiveKit + Gemini Realtime voice agent for on-call / SRE incident workflows.
It answers status questions, records spoken updates, suggests next steps from a
runbook, detects escalation intent, and saves a transcript plus a structured
incident action summary when the session ends.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool
from livekit.plugins import google

load_dotenv()

logger = logging.getLogger(__name__)

REALTIME_MODEL = "gemini-3.1-flash-live-preview"
VOICE = "Zephyr"

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "mock_incidents.json"
LOG_DIR = BASE_DIR / "logs"

VALID_STATUSES = ("investigating", "identified", "monitoring", "resolved")

# Phrases in the engineer's speech that suggest they are stuck or unsure.
ESCALATION_PHRASES = (
    "escalate",
    "need help",
    "get someone",
    "page the",
    "i'm not sure",
    "i am not sure",
    "not sure",
    "no idea",
    "getting worse",
    "still failing",
    "can't fix",
    "cannot fix",
)

INSTRUCTIONS = """You are the Incident Commander, a calm and concise voice assistant
for an on-call engineer handling a live production incident.

How to behave:
- Keep every reply short (1-3 sentences). You are speaking out loud, so avoid lists,
  markdown, and reading out long IDs character by character.
- When asked for the incident status, call get_incident_status.
- When the engineer dictates progress ("database is back up"), call add_incident_update.
- When asked what to do next, call get_next_steps and suggest the first useful step.
- When the engineer commits to doing something, call record_action_item.
- If the engineer sounds unsure, stuck, or the situation is getting worse, call
  flag_escalation and tell them who to escalate to.
- When the engineer says they are done or asks for a summary, call
  generate_incident_summary and read out the key points.
Never invent incident facts. Only use what the tools return."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_incident(incident_id: Optional[str] = None) -> dict:
    """Load an incident from the mock data file (first one by default)."""
    incidents = json.loads(DATA_FILE.read_text())["incidents"]
    if incident_id:
        for incident in incidents:
            if incident["id"] == incident_id:
                return incident
    return incidents[0]


def detect_escalation(text: str) -> Optional[str]:
    """Return the matched phrase if the text signals escalation intent or uncertainty."""
    lowered = text.lower()
    for phrase in ESCALATION_PHRASES:
        if phrase in lowered:
            return phrase
    return None


@dataclass
class IncidentState:
    """Everything we track about the incident across conversation turns."""

    incident: dict
    status: str = ""
    updates: list = field(default_factory=list)
    action_items: list = field(default_factory=list)
    escalation: Optional[dict] = None
    transcript: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.status = self.incident["status"]

    def log_turn(self, role: str, text: str) -> None:
        self.transcript.append({"time": now_iso(), "role": role, "text": text})

    def add_update(self, update: str, new_status: str = "") -> None:
        if new_status:
            self.status = new_status
        self.updates.append({"time": now_iso(), "update": update, "status": self.status})

    def add_action_item(self, action: str, owner: str) -> None:
        self.action_items.append({"time": now_iso(), "action": action, "owner": owner})

    def escalate(self, reason: str, source: str) -> bool:
        """Record an escalation. Returns False if one was already recorded."""
        if self.escalation:
            return False
        self.escalation = {
            "time": now_iso(),
            "reason": reason,
            "source": source,
            "escalate_to": self.incident["on_call"],
        }
        return True

    def summary(self) -> dict:
        return {
            "incident_id": self.incident["id"],
            "title": self.incident["title"],
            "severity": self.incident["severity"],
            "service": self.incident["service"],
            "initial_status": self.incident["status"],
            "final_status": self.status,
            "escalated": self.escalation is not None,
            "escalation": self.escalation,
            "updates": self.updates,
            "action_items": self.action_items,
            "generated_at": now_iso(),
        }


def save_logs(state: IncidentState) -> Path:
    """Write the transcript and the structured summary to the logs/ folder."""
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{state.incident['id']}_{stamp}"
    (LOG_DIR / f"{prefix}_transcript.json").write_text(json.dumps(state.transcript, indent=2))
    summary_path = LOG_DIR / f"{prefix}_summary.json"
    summary_path.write_text(json.dumps(state.summary(), indent=2))
    logger.info("Saved incident logs to %s", LOG_DIR)
    return summary_path


class IncidentCommander(Agent):
    def __init__(self, state: IncidentState) -> None:
        super().__init__(instructions=INSTRUCTIONS)
        self.state = state

    @function_tool
    async def get_incident_status(self, context: RunContext) -> str:
        """Get the current incident status, severity, impact, and recent timeline."""
        incident = self.state.incident
        return json.dumps(
            {
                "id": incident["id"],
                "title": incident["title"],
                "severity": incident["severity"],
                "status": self.state.status,
                "impact": incident["impact"],
                "on_call": incident["on_call"],
                "timeline": incident["timeline"],
                "updates_this_session": self.state.updates,
                "escalated": self.state.escalation is not None,
            }
        )

    @function_tool
    async def add_incident_update(
        self, context: RunContext, update: str, new_status: str = ""
    ) -> str:
        """Record a progress update dictated by the engineer.

        Args:
            update: A short description of what happened or what was found.
            new_status: Optional new status. One of investigating, identified,
                monitoring, resolved. Leave empty if the status did not change.
        """
        new_status = new_status.strip().lower()
        if new_status and new_status not in VALID_STATUSES:
            return f"Invalid status. Use one of: {', '.join(VALID_STATUSES)}."
        self.state.add_update(update, new_status)
        return f"Update recorded. Current status: {self.state.status}."

    @function_tool
    async def get_next_steps(self, context: RunContext) -> str:
        """Get the runbook steps for this incident."""
        return json.dumps({"runbook": self.state.incident["runbook"]})

    @function_tool
    async def record_action_item(
        self, context: RunContext, action: str, owner: str = "unassigned"
    ) -> str:
        """Record an action item the engineer commits to.

        Args:
            action: What needs to be done.
            owner: Who will do it. Defaults to unassigned.
        """
        self.state.add_action_item(action, owner)
        return f"Action item recorded for {owner}."

    @function_tool
    async def flag_escalation(self, context: RunContext, reason: str) -> str:
        """Flag that this incident should be escalated because the engineer is
        unsure, stuck, or the situation is getting worse.

        Args:
            reason: Why escalation is needed.
        """
        created = self.state.escalate(reason, source="agent")
        target = self.state.incident["on_call"]
        if created:
            return f"Escalation flagged. Escalate to: {target}."
        return f"Escalation was already flagged. Escalate to: {target}."

    @function_tool
    async def generate_incident_summary(self, context: RunContext) -> str:
        """Save the transcript and produce a structured action summary of the incident."""
        save_logs(self.state)
        return json.dumps(self.state.summary())


server = AgentServer()


@server.rtc_session(agent_name="incident-commander-agent")
async def entrypoint(ctx: agents.JobContext):
    state = IncidentState(load_incident())

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=REALTIME_MODEL,
            voice=VOICE,
        )
    )

    @session.on("conversation_item_added")
    def on_item_added(event):
        item = event.item
        text = getattr(item, "text_content", None)
        if not text:
            return
        state.log_turn(item.role, text)
        # Safety net: catch escalation phrases even if the model forgets the tool call.
        if item.role == "user":
            phrase = detect_escalation(text)
            if phrase and state.escalate(f'Engineer said "{phrase}"', source="keyword"):
                logger.info("Escalation intent detected: %s", phrase)

    async def on_shutdown():
        save_logs(state)

    ctx.add_shutdown_callback(on_shutdown)

    await session.start(
        room=ctx.room,
        agent=IncidentCommander(state),
    )

    incident = state.incident
    await session.generate_reply(
        instructions=(
            "Greet the on-call engineer in one or two sentences. Use exactly these "
            f"facts: incident {incident['id']}, {incident['title']}, "
            f"severity {incident['severity']}, current status {state.status}."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)