"""Tests for the optional live backend: lazy init and mocked provider paths."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from guardrail_eval_harness.backends import ScriptedModel
from guardrail_eval_harness.live import LiveBackend, live_report, resolve_live_model
from guardrail_eval_harness.scenarios import load_scenarios
from guardrail_eval_harness.schemas import (
    ActorContext,
    RequestedCall,
    RunTrace,
    Scenario,
)


def make_live_scenario() -> Scenario:
    return Scenario(
        id="live-owned-ticket",
        suite="default",
        category="ticket",
        description="live smoke",
        user_input="What is the status of TCK-1001?",
        actor=ActorContext(actor_id="user-1"),
        scripted_responses=[
            RequestedCall(
                kind="final",
                text='{"status":"answered","message":"TCK-1001 is open.","refusal_reason":null}',
            )
        ],
        expected={
            "required": [],
            "allowed": ["get_ticket_status", "search_help_articles"],
        },
    )


class TestLiveConfiguration:
    def test_missing_model_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        monkeypatch.delenv("EXAMPLE_MODEL_NAME", raising=False)
        with pytest.raises(ValueError, match="--live-model"):
            LiveBackend(model_name="")

    def test_missing_key_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="NEBIUS_API_KEY"):
            LiveBackend(model_name="any-model")

    def test_client_lazy_and_not_created_at_init(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "fake-key")
        backend = LiveBackend(model_name="any-model")
        assert backend._client is None


class TestLiveModelResolution:
    def test_explicit_flag_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXAMPLE_MODEL_NAME", "env/model")
        assert resolve_live_model("flag/model") == "flag/model"

    def test_env_fallback_used_when_flag_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXAMPLE_MODEL_NAME", " env/model ")
        assert resolve_live_model(None) == "env/model"

    def test_missing_flag_and_env_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("EXAMPLE_MODEL_NAME", raising=False)
        with pytest.raises(ValueError, match="EXAMPLE_MODEL_NAME"):
            resolve_live_model(None)

    def test_whitespace_only_model_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXAMPLE_MODEL_NAME", "   ")
        with pytest.raises(ValueError, match="EXAMPLE_MODEL_NAME"):
            resolve_live_model("")


class TestLiveCli:
    def test_live_without_model_or_key_is_config_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from guardrail_eval_harness import cli

        monkeypatch.chdir(tmp_path)  # keep load_dotenv away from any local .env
        monkeypatch.delenv("EXAMPLE_MODEL_NAME", raising=False)
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        assert cli.main(["--mode", "live"]) == cli.EXIT_CONFIG_ERROR

    def test_live_without_key_is_config_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from guardrail_eval_harness import cli

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EXAMPLE_MODEL_NAME", "test/model")
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        assert cli.main(["--mode", "live"]) == cli.EXIT_CONFIG_ERROR


class TestLiveMocked:
    def test_mocked_provider_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "fake-key")
        backend = LiveBackend(model_name="test-model", per_case_timeout_seconds=5.0)
        fake_model = ScriptedModel(
            [
                [
                    {
                        "type": "message",
                        "text": '{"status":"answered","message":"TCK-1001 is open.","refusal_reason":null}',
                    }
                ]
            ]
        )
        backend.build_model = lambda: fake_model  # type: ignore[method-assign]
        scenario = make_live_scenario()
        trace = asyncio.run(backend.run_case(scenario))
        assert isinstance(trace, RunTrace)
        assert trace.final_response is not None
        assert backend._client is None

    def test_live_report_counts_error_for_provider_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NEBIUS_API_KEY", "fake-key")
        backend = LiveBackend(model_name="test-model")

        class ExplodingModel(ScriptedModel):
            def __init__(self) -> None:
                super().__init__([])

            async def get_response(self, *args, **kwargs):
                raise TimeoutError("provider unreachable")

        backend.build_model = lambda: ExplodingModel()  # type: ignore[method-assign]
        _cases, totals, aggregate = live_report(backend, [make_live_scenario()])
        assert aggregate == "error"
        assert totals.errored > 0

    def test_offline_never_touches_live_module(self) -> None:
        from guardrail_eval_harness.evaluation import evaluate_scenarios

        scenarios = load_scenarios("default")
        _cases, _totals, aggregate = evaluate_scenarios(scenarios, mode="offline")
        assert aggregate == "pass"
