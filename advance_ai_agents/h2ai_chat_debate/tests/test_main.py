"""Tests for the moderator loop and the console rendering in ``main.py``.

These cover the wiring rather than the pure functions: the debate flow itself is
tested in ``test_debate.py``. No API keys and no network needed — the call to
the model is replaced by a recorder.
"""

from __future__ import annotations

import argparse
import io
import json
import sys

import pytest
from rich.console import Console

import main
from debate import Agent


def make_agent():
    return Agent(
        name="Ada",
        role="the optimist",
        model="a-model",
        base_url="http://localhost:1234/v1",
        api_key_env="LOCAL_API_KEY",
    )


ROSTER = [
    {
        "name": "Ada",
        "role": "the optimist",
        "model": "a-model",
        "base_url": "http://localhost:1234/v1",
        "api_key_env": "LOCAL_API_KEY",
    },
    {
        "name": "Kant",
        "role": "the skeptic",
        "model": "a-model",
        "base_url": "http://localhost:1234/v1",
        "api_key_env": "LOCAL_API_KEY",
    },
    {
        "name": "Vera",
        "role": "the pragmatist",
        "model": "a-model",
        "base_url": "http://localhost:1234/v1",
        "api_key_env": "LOCAL_API_KEY",
    },
]


@pytest.fixture
def roster_file(tmp_path):
    path = tmp_path / "agents.json"
    path.write_text(json.dumps(ROSTER), encoding="utf-8")
    return path


def run_debate(monkeypatch, roster_file, *, rounds, answer, note, topic="a topic"):
    """Run the whole moderator loop with the model and the terminal replaced.

    Returns what each speaker was actually sent, in order, plus everything the
    console rendered.
    """
    buffer = io.StringIO()
    monkeypatch.setattr(main, "console", Console(file=buffer, width=200))
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main,
        "parse_args",
        lambda: argparse.Namespace(
            topic=topic, rounds=rounds, agents=str(roster_file), auto=False
        ),
    )
    give_note = note if callable(note) else (lambda: note)
    monkeypatch.setattr(main, "moderator_note", give_note)

    sent = []

    def recording_ask(agent, messages):
        sent.append((agent.name, messages[1]["content"]))
        return answer

    monkeypatch.setattr(main, "ask", recording_ask)

    main.main()
    return sent, buffer.getvalue()


def test_the_moderator_note_reaches_every_speaker_in_the_round(
    monkeypatch, roster_file
):
    """The human steers the whole round, not just whoever happens to open it."""
    sent, _ = run_debate(
        monkeypatch, roster_file, rounds=2, answer="noted", note="stick to costs"
    )

    second_round = sent[len(ROSTER) :]
    assert len(second_round) == len(ROSTER)
    unheard = [name for name, body in second_round if "stick to costs" not in body]
    assert unheard == [], f"these speakers never heard the moderator: {unheard}"


def test_a_note_steers_one_round_and_then_a_silent_moderator_is_obeyed(
    monkeypatch, roster_file
):
    """A note steers the next round only. Staying quiet afterwards means quiet."""
    notes = iter(["stick to costs", None])
    sent, _ = run_debate(
        monkeypatch, roster_file, rounds=3, answer="noted", note=lambda: next(notes)
    )

    per_round = [sent[i : i + len(ROSTER)] for i in range(0, len(sent), len(ROSTER))]
    assert all("stick to costs" not in body for _, body in per_round[0])
    assert all("stick to costs" in body for _, body in per_round[1])
    assert all("moderator" not in body.lower() for _, body in per_round[2])


def test_model_output_is_never_read_as_console_markup(monkeypatch, roster_file):
    """What a model writes is text, not instructions for our terminal."""
    answer = "Use the [bold] tag to shout."
    _, output = run_debate(monkeypatch, roster_file, rounds=1, answer=answer, note=None)

    assert "[bold] tag to shout" in output


def test_a_malformed_tag_from_a_model_does_not_kill_the_debate(
    monkeypatch, roster_file
):
    """A stray closing tag used to raise MarkupError after the call was paid for."""
    sent, output = run_debate(
        monkeypatch, roster_file, rounds=1, answer="I am done here[/quote]", note=None
    )

    assert len(sent) == len(ROSTER)
    assert "[/quote]" in output


def test_a_topic_with_brackets_is_shown_as_written(monkeypatch, roster_file):
    """The topic comes from the command line and is text too."""
    _, output = run_debate(
        monkeypatch,
        roster_file,
        rounds=1,
        answer="fine",
        note=None,
        topic="Is [citation needed] a fair answer?",
    )

    assert "[citation needed]" in output


def test_a_debate_with_no_rounds_is_rejected(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--topic", "a topic", "--rounds", "0"])
    with pytest.raises(SystemExit) as raised:
        main.parse_args()
    assert raised.value.code == 2


def test_a_debate_with_negative_rounds_is_rejected(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["main.py", "--topic", "a topic", "--rounds", "-3"]
    )
    with pytest.raises(SystemExit) as raised:
        main.parse_args()
    assert raised.value.code == 2


def test_a_normal_number_of_rounds_still_works(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--topic", "a topic", "--rounds", "5"])
    assert main.parse_args().rounds == 5


class RespuestaSinNada:
    """Lo que devuelve un proveedor que contesta 200 pero no dice nada."""

    choices: list = []


class MensajeVacio:
    content = None


class EleccionVacia:
    message = MensajeVacio()


class RespuestaConHueco:
    """Lo que devuelve un proveedor que contesta con el texto a nulo."""

    choices = [EleccionVacia()]


def cliente_que_devuelve(respuesta):
    class Completions:
        @staticmethod
        def create(**kwargs):
            return respuesta

    class Chat:
        completions = Completions()

    class Cliente:
        chat = Chat()

    return Cliente()


def test_a_provider_answering_with_no_choices_costs_a_turn_not_the_debate(monkeypatch):
    """An empty completion used to raise IndexError and end the whole debate."""
    monkeypatch.setattr(
        main, "client_for", lambda agent: cliente_que_devuelve(RespuestaSinNada())
    )
    salida = main.ask(make_agent(), [{"role": "user", "content": "your turn"}])
    assert salida.startswith("(no answer")


def test_a_provider_answering_with_empty_content_gives_an_empty_turn(monkeypatch):
    """Content of None is a silent turn, not a crash."""
    monkeypatch.setattr(
        main, "client_for", lambda agent: cliente_que_devuelve(RespuestaConHueco())
    )
    assert main.ask(make_agent(), [{"role": "user", "content": "your turn"}]) == ""
