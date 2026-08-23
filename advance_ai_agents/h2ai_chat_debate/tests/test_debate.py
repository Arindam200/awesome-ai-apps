"""Unit tests for the debate flow. No API keys and no network needed."""

from __future__ import annotations

import json

import pytest

from debate import (
    HISTORY_ROLE,
    Agent,
    Debate,
    build_messages,
    format_transcript,
    load_agents,
    speaking_order,
)


def make_agent(name: str, role: str = "a role") -> Agent:
    return Agent(
        name=name,
        role=role,
        model="a-model",
        base_url="http://localhost:1234/v1",
        api_key_env="LOCAL_API_KEY",
    )


@pytest.fixture
def debate() -> Debate:
    return Debate(
        topic="Should AI systems be allowed to refuse a task?",
        agents=[make_agent("Ada", "the optimist"), make_agent("Kant", "the skeptic")],
        total_rounds=2,
    )


def test_the_shipped_roster_loads():
    agents = load_agents()
    assert len(agents) >= 2
    assert all(agent.name and agent.model for agent in agents)


def test_a_roster_with_a_missing_field_is_rejected(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(
        json.dumps([{"name": "Ada", "role": "r", "model": "m"}]), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="base_url"):
        load_agents(path)


def test_two_agents_with_the_same_name_are_rejected(tmp_path):
    entry = {
        "name": "Ada",
        "role": "r",
        "model": "m",
        "base_url": "u",
        "api_key_env": "K",
    }
    path = tmp_path / "agents.json"
    path.write_text(json.dumps([entry, dict(entry)]), encoding="utf-8")
    with pytest.raises(ValueError, match="same name"):
        load_agents(path)


def test_one_agent_is_not_a_debate(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(
        json.dumps(
            [
                {
                    "name": "Ada",
                    "role": "r",
                    "model": "m",
                    "base_url": "u",
                    "api_key_env": "K",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="at least two"):
        load_agents(path)


def test_an_empty_transcript_says_so_instead_of_being_blank():
    assert "nothing has been said" in format_transcript([])


def test_the_transcript_keeps_who_said_what_and_in_order(debate):
    debate.add("Ada", "I start.")
    debate.add("Kant", "I disagree.")
    transcript = debate.transcript()
    assert transcript.index("Ada: I start.") < transcript.index("Kant: I disagree.")


def test_a_speaker_is_told_who_the_others_are_but_not_itself(debate):
    system = build_messages(debate, debate.agents[0], round_number=1)[0]["content"]
    assert "Kant (the skeptic)" in system
    assert "Ada (the optimist)" not in system


def test_the_whole_conversation_travels_as_user_never_as_assistant(debate):
    debate.add("Ada", "something said earlier")
    messages = build_messages(debate, debate.agents[1], round_number=1)
    assert [message["role"] for message in messages] == ["system", HISTORY_ROLE]
    assert HISTORY_ROLE == "user"
    assert "something said earlier" in messages[1]["content"]


def test_the_speaker_knows_which_round_it_is(debate):
    body = build_messages(debate, debate.agents[0], round_number=2)[1]["content"]
    assert "Round 2 of 2" in body


def test_the_moderator_note_reaches_the_next_speaker(debate):
    body = build_messages(debate, debate.agents[0], 1, moderator_note="stick to costs")[
        1
    ]["content"]
    assert "stick to costs" in body


def test_without_a_note_no_moderator_line_is_invented(debate):
    body = build_messages(debate, debate.agents[0], round_number=1)[1]["content"]
    assert "moderator" not in body.lower()


def test_the_opening_speaker_rotates_every_round(debate):
    first_round = [agent.name for agent in speaking_order(debate.agents, 1)]
    second_round = [agent.name for agent in speaking_order(debate.agents, 2)]
    assert first_round == ["Ada", "Kant"]
    assert second_round == ["Kant", "Ada"]


def test_rotating_never_drops_or_duplicates_a_speaker(debate):
    for round_number in range(1, 7):
        order = speaking_order(debate.agents, round_number)
        assert sorted(agent.name for agent in order) == ["Ada", "Kant"]
