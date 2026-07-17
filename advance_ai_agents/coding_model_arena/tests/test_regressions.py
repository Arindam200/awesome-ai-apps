"""Regression tests for arena execution and judging failure states."""

import os
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from execution import run_candidate, run_contree, run_local  # noqa: E402
from judge import judge_submissions  # noqa: E402
from challenges import HiddenTest, by_id as challenge_by_id  # noqa: E402
from runner import generate_solution  # noqa: E402


GOOD_TWO_SUM = """\
def two_sum(nums: list[int], target: int) -> list[int]:
    seen = {}
    for index, number in enumerate(nums):
        complement = target - number
        if complement in seen:
            return [seen[complement], index]
        seen[number] = index
    return []
"""

TWO_SUM_TESTS = """\
assert sorted(solution([2, 7, 11, 15], 9)) == [0, 1]
assert sorted(solution([3, 2, 4], 6)) == [1, 2]
"""

EVENT_RECONCILER_REFERENCE = """\
def reconcile_events(events: list[dict]) -> dict[str, dict]:
    accounts = {event['account'] for event in events}
    seen_ids = set()
    grouped = {account: [] for account in accounts}
    for event in events:
        if event['id'] in seen_ids:
            continue
        seen_ids.add(event['id'])
        grouped[event['account']].append(event)

    output = {}
    for account, account_events in grouped.items():
        state = {
            'balance': 0,
            'frozen': False,
            'next_seq': 1,
            'applied_event_ids': [],
            'rejected_event_ids': [],
            'pending_event_ids': [],
        }
        ordered = sorted(account_events, key=lambda event: event['seq'])
        for index, event in enumerate(ordered):
            if event['seq'] != state['next_seq']:
                state['pending_event_ids'] = [item['id'] for item in ordered[index:]]
                break
            kind = event['kind']
            if kind == 'credit':
                state['balance'] += event['amount']
                state['applied_event_ids'].append(event['id'])
            elif kind == 'debit':
                if state['frozen'] or event['amount'] > state['balance']:
                    state['rejected_event_ids'].append(event['id'])
                else:
                    state['balance'] -= event['amount']
                    state['applied_event_ids'].append(event['id'])
            elif kind == 'freeze':
                state['frozen'] = True
                state['applied_event_ids'].append(event['id'])
            elif kind == 'unfreeze':
                state['frozen'] = False
                state['applied_event_ids'].append(event['id'])
            state['next_seq'] += 1
        output[account] = state
    return output
"""

EVENT_RECONCILER_SHALLOW = """\
def reconcile_events(events: list[dict]) -> dict[str, dict]:
    seen = set()
    grouped = {}
    for event in events:
        grouped.setdefault(event['account'], [])
        if event['id'] not in seen:
            seen.add(event['id'])
            grouped[event['account']].append(event)
    output = {}
    for account, items in grouped.items():
        balance = 0
        applied = []
        for event in sorted(items, key=lambda item: item['seq']):
            if event['kind'] == 'credit':
                balance += event['amount']
                applied.append(event['id'])
            elif event['kind'] == 'debit' and balance >= event['amount']:
                balance -= event['amount']
                applied.append(event['id'])
        output[account] = {
            'balance': balance, 'frozen': False, 'next_seq': len(items) + 1,
            'applied_event_ids': applied, 'rejected_event_ids': [],
            'pending_event_ids': [],
        }
    return output
"""

ROLLOUT_REFERENCE = """\
def plan_rollout(services: list[dict]) -> dict:
    by_name = {service['name']: service for service in services}
    blocked = {
        name for name, service in by_name.items()
        if any(dependency not in by_name for dependency in service['depends_on'])
    }
    changed = True
    while changed:
        changed = False
        for name, service in by_name.items():
            if name not in blocked and any(dep in blocked for dep in service['depends_on']):
                blocked.add(name)
                changed = True

    remaining = set(by_name) - blocked
    deployed = set()
    stages = []
    while remaining:
        ready = [
            name for name in remaining
            if set(by_name[name]['depends_on']) <= deployed
        ]
        if not ready:
            blocked.update(remaining)
            break
        ready.sort(key=lambda name: (-by_name[name]['priority'], name))
        stages.append(ready)
        deployed.update(ready)
        remaining.difference_update(ready)
    return {'stages': stages, 'blocked': sorted(blocked)}
"""

CONFIG_REFERENCE = """\
def apply_config(base: dict, overlays: list[dict]) -> dict:
    import copy
    missing = object()
    deleted = object()

    def merge(current, overlay):
        if isinstance(overlay, dict) and overlay == {'$delete': True}:
            return deleted
        if isinstance(overlay, dict) and set(overlay) == {'$append'}:
            existing = [] if current is missing else copy.deepcopy(current)
            return existing + copy.deepcopy(overlay['$append'])
        if isinstance(overlay, dict):
            result = copy.deepcopy(current) if isinstance(current, dict) else {}
            for key, value in overlay.items():
                merged = merge(result.get(key, missing), value)
                if merged is deleted:
                    result.pop(key, None)
                else:
                    result[key] = merged
            return result
        return copy.deepcopy(overlay)

    result = copy.deepcopy(base)
    for overlay in overlays:
        result = merge(result, overlay)
    return result
"""


class ExecutionRegressionTests(unittest.TestCase):
    def test_known_good_solution_passes_local_hidden_tests(self):
        result = run_local(GOOD_TWO_SUM, TWO_SUM_TESTS)

        self.assertTrue(result.passed)
        self.assertIsNone(result.failure_kind)
        self.assertIn("ALL_TESTS_PASSED", result.stdout)

    def test_candidate_execution_stays_local_when_environment_requests_contree(self):
        with patch.dict(os.environ, {"SANDBOX_BACKEND": "contree"}):
            result = run_candidate(GOOD_TWO_SUM, TWO_SUM_TESTS)

        self.assertTrue(result.passed)
        self.assertEqual(result.backend, "local-subprocess")
        self.assertIsNone(result.failure_kind)

    def test_sandbox_upload_uses_a_local_source_path(self):
        class FakeImage:
            uploaded_source = ""

            def run(self, **kwargs):
                source_path = kwargs["files"]["/submission.py"]
                self.uploaded_source = Path(source_path).read_text()
                return self

            def wait(self):
                return SimpleNamespace(
                    exit_code=0,
                    stdout="ALL_TESTS_PASSED",
                    stderr="",
                )

        fake_image = FakeImage()
        fake_client = SimpleNamespace(
            images=SimpleNamespace(use=lambda _image_name: fake_image)
        )
        fake_module = ModuleType("contree_sdk")
        fake_module.ContreeSync = lambda: fake_client

        with patch.dict(sys.modules, {"contree_sdk": fake_module}):
            result = run_contree(GOOD_TWO_SUM, TWO_SUM_TESTS)

        self.assertTrue(result.passed)
        self.assertIn("def two_sum", fake_image.uploaded_source)

    def test_expert_challenge_awards_partial_credit_per_behavior(self):
        challenge = challenge_by_id("event_reconciler")

        complete = run_local(EVENT_RECONCILER_REFERENCE, challenge.hidden_tests)
        shallow = run_local(EVENT_RECONCILER_SHALLOW, challenge.hidden_tests)

        self.assertTrue(complete.passed)
        self.assertEqual(complete.test_score, 100)
        self.assertGreater(shallow.test_score, 0)
        self.assertLess(shallow.test_score, 100)
        self.assertGreater(shallow.passed_tests, 0)

    def test_additional_litmus_challenges_accept_complete_implementations(self):
        rollout = challenge_by_id("rollout_planner")
        config = challenge_by_id("config_overlay")

        rollout_result = run_local(ROLLOUT_REFERENCE, rollout.hidden_tests)
        config_result = run_local(CONFIG_REFERENCE, config.hidden_tests)

        self.assertTrue(rollout_result.passed, rollout_result.stdout)
        self.assertEqual(rollout_result.test_score, 100)
        self.assertTrue(config_result.passed, config_result.stdout)
        self.assertEqual(config_result.test_score, 100)

    def test_timeout_preserves_completed_hidden_case_credit(self):
        code = """\
def two_sum(nums, target):
    if target == 99:
        while True:
            pass
    return [0, 1]
"""
        tests = (
            HiddenTest("completed first", "assert solution([1, 2], 3) == [0, 1]", weight=2),
            HiddenTest("hangs second", "solution([1, 2], 99)", weight=3),
        )

        with patch("execution.TIMEOUT_SECONDS", 0.2):
            result = run_local(code, tests)

        self.assertFalse(result.passed)
        self.assertEqual(result.passed_tests, 1)
        self.assertEqual(result.earned_points, 2)
        self.assertEqual(result.total_points, 5)
        self.assertIn("TIMEOUT", result.stdout)


class JudgeRegressionTests(unittest.TestCase):
    def test_empty_judge_response_has_actionable_error(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=""),
                    finish_reason="stop",
                )
            ]
        )
        client = MagicMock()
        client.chat.completions.create.return_value = response

        verdict = judge_submissions(
            client,
            "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "Implement two_sum.",
            {"Candidate A": {"code": GOOD_TWO_SUM, "passed": True, "test_output": "ok"}},
        )

        self.assertIn("empty response", verdict.error)
        call_kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})


class GenerationRegressionTests(unittest.TestCase):
    @staticmethod
    def _response(content: str, finish_reason: str):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                    finish_reason=finish_reason,
                )
            ]
        )

    def test_length_limited_empty_reasoning_response_retries_with_larger_budget(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            self._response("", "length"),
            self._response(f"```python\n{GOOD_TWO_SUM}```", "stop"),
        ]

        result = generate_solution(client, "test/model", "Implement two_sum.")

        self.assertFalse(result.error)
        self.assertIn("def two_sum", result.code)
        self.assertEqual(result.attempts, 2)
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(calls[0].kwargs["max_completion_tokens"], 6000)
        self.assertEqual(calls[1].kwargs["max_completion_tokens"], 10000)
        self.assertEqual(calls[0].kwargs["reasoning_effort"], "low")

    def test_repeated_incomplete_response_is_an_explicit_generation_failure(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            self._response("", "length"),
            self._response("def two_sum(", "length"),
        ]

        result = generate_solution(client, "test/model", "Implement two_sum.")

        self.assertEqual(result.code, "")
        self.assertIn("did not return a complete code answer", result.error)
        self.assertEqual(result.finish_reason, "length")
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_stopped_response_without_required_entrypoint_is_retried(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            self._response("```python\nvalue = 42\n```", "stop"),
            self._response(f"```python\n{GOOD_TWO_SUM}```", "stop"),
        ]

        result = generate_solution(client, "test/model", "def two_sum(nums, target): ...")

        self.assertFalse(result.error)
        self.assertIn("def two_sum", result.code)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_generation_requests_have_a_hard_timeout(self):
        client = MagicMock()
        client.chat.completions.create.return_value = self._response(
            f"```python\n{GOOD_TWO_SUM}```", "stop"
        )

        generate_solution(client, "test/model", "def two_sum(nums, target): ...")

        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["timeout"],
            90,
        )

    def test_hybrid_models_disable_thinking_to_preserve_answer_budget(self):
        client = MagicMock()
        client.chat.completions.create.return_value = self._response(
            f"```python\n{GOOD_TWO_SUM}```", "stop"
        )

        generate_solution(client, "zai-org/GLM-5.2", "def two_sum(nums, target): ...")

        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": False}},
        )

    def test_minimax_receives_enough_budget_for_native_reasoning_and_code(self):
        client = MagicMock()
        client.chat.completions.create.return_value = self._response(
            f"```python\n{GOOD_TWO_SUM}```", "stop"
        )

        result = generate_solution(
            client,
            "MiniMaxAI/MiniMax-M3",
            "def two_sum(nums, target): ...",
        )

        self.assertFalse(result.error)
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["max_completion_tokens"],
            24000,
        )


if __name__ == "__main__":
    unittest.main()
