"""Offline tests: no keys, network or model calls. Run: python -m unittest discover -s tests"""

import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main

FIXTURES = json.loads((ROOT / "fixtures" / "sample_responses.json").read_text(encoding="utf-8"))
TODAY = date(2026, 10, 7)
FXMD_KEY = "fxmd-test-key-0123456789"
NEBIUS_KEY = "nebius-test-key-0123456789"


class Response:
    def __init__(self, status, raw):
        self.status, self.raw = status, raw

    def read(self, size=-1):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def encode(body):
    return body if isinstance(body, bytes) else json.dumps(body).encode()


class FakeOpener:
    """Serves FXMacroData fixtures by path and a scripted Nebius reply."""

    def __init__(self, nebius=None, overrides=None):
        self.nebius = nebius
        self.overrides = overrides or {}
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        url = urllib.parse.urlsplit(request.full_url)
        if url.hostname == "api.tokenfactory.nebius.com":
            status, body = self.nebius
        else:
            status, body = self.overrides.get(url.path) or self.fixture(url.path)
        if isinstance(body, Exception):
            raise body
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(encode(body)))
        return Response(status, encode(body))

    @staticmethod
    def fixture(path):
        if path == "/v1/calendar/usd":
            return 200, FIXTURES["calendar_usd"]
        name = "latest_" + path.rsplit("/", 1)[-1]
        if path.startswith("/v1/announcements/usd/") and name in FIXTURES:
            return 200, FIXTURES[name]
        return 404, {"detail": "not found"}


def model_reply(payload):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return 200, {"choices": [{"message": {"content": content}}]}


def run(argv, opener, env=None):
    out = []
    code = main.main(argv, environ=env or {}, opener=opener, today=TODAY, out=out.append)
    return code, "".join(out)


class EvidenceTests(unittest.TestCase):
    def test_keyless_markdown_brief(self):
        opener = FakeOpener()
        code, text = run(["--no-synthesis"], opener)
        self.assertEqual(code, 0)
        self.assertIn("| E1 | Consumer Confidence Proxy (FRBNY SCE) |", text)
        self.assertIn("Inflation (CPI)", text)
        self.assertNotIn("Initial Jobless Claims", text)  # tier 3 is filtered out by default
        self.assertIn("delayed by 15 minutes", text)
        for request in opener.requests:
            self.assertIsNone(request.get_header("X-api-key"))
            self.assertTrue(request.full_url.startswith("https://api.fxmacrodata.com/v1/"))

    def test_calendar_window_and_tier(self):
        opener = FakeOpener()
        code, text = run(["--no-synthesis", "--json", "--days", "3", "--max-tier", "3"], opener)
        self.assertEqual(code, 0)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(opener.requests[0].full_url).query)
        self.assertEqual(query, {"start_date": ["2026-10-07"], "end_date": ["2026-10-10"]})
        releases = [item["release"] for item in json.loads(text)["evidence"]]
        self.assertIn("initial_jobless_claims", releases)

    def test_each_release_is_fetched_once(self):
        opener = FakeOpener()
        run(["--no-synthesis"], opener)
        paths = [urllib.parse.urlsplit(r.full_url).path for r in opener.requests]
        self.assertEqual(len(paths), len(set(paths)))

    def test_missing_series_is_marked_unavailable(self):
        opener = FakeOpener(overrides={"/v1/announcements/usd/core_inflation": (404, {"detail": "nope"})})
        code, text = run(["--no-synthesis", "--json"], opener)
        self.assertEqual(code, 0)
        item = next(i for i in json.loads(text)["evidence"] if i["release"] == "core_inflation")
        self.assertIn("HTTP 404", item["unavailable"])

    def test_key_is_a_header_and_never_printed(self):
        echo = dict(FIXTURES["calendar_usd"], note=FXMD_KEY)
        opener = FakeOpener(overrides={"/v1/calendar/usd": (200, echo)})
        code, text = run(["--no-synthesis", "--json"], opener, env={"FXMACRODATA_API_KEY": f" {FXMD_KEY} "})
        self.assertEqual(code, 0)
        self.assertEqual(opener.requests[0].get_header("X-api-key"), FXMD_KEY)
        self.assertNotIn(FXMD_KEY, opener.requests[0].full_url)
        self.assertNotIn(FXMD_KEY, text)


class ErrorTests(unittest.TestCase):
    def assert_fails(self, argv, opener, env=None):
        stderr = io.StringIO()
        original, sys.stderr = sys.stderr, stderr
        try:
            code, text = run(argv, opener, env)
        finally:
            sys.stderr = original
        self.assertEqual(code, 1)
        self.assertEqual(text, "")
        return stderr.getvalue()

    def test_bad_inputs_make_no_request(self):
        for argv in (["--currency", "usdx"], ["--currency", "u1d"], ["--days", "0"], ["--days", "32"]):
            opener = FakeOpener()
            self.assert_fails(argv + ["--no-synthesis"], opener)
            self.assertEqual(opener.requests, [])

    def test_calendar_needs_a_key_for_other_currencies(self):
        locked = {"/v1/calendar/eur": (401, {"error": "api_key_required", "detail": "This endpoint requires an API key."})}
        message = self.assert_fails(["--currency", "eur", "--no-synthesis"], FakeOpener(overrides=locked))
        self.assertIn("HTTP 401", message)

    def test_error_body_with_http_200(self):
        body = {"error": "api_key_required", "detail": f"bad key {FXMD_KEY}"}
        opener = FakeOpener(overrides={"/v1/calendar/usd": (200, body)})
        message = self.assert_fails(["--no-synthesis"], opener, env={"FXMACRODATA_API_KEY": FXMD_KEY})
        self.assertNotIn(FXMD_KEY, message)

    def test_wrong_shapes_and_non_json(self):
        for body in (b"<html>", [1], {"data": "x"}):
            opener = FakeOpener(overrides={"/v1/calendar/usd": (200, body)})
            self.assert_fails(["--no-synthesis"], opener)

    def test_transport_error_reports_type_only(self):
        opener = FakeOpener(overrides={"/v1/calendar/usd": (200, urllib.error.URLError(f"boom {FXMD_KEY}"))})
        message = self.assert_fails(["--no-synthesis"], opener, env={"FXMACRODATA_API_KEY": FXMD_KEY})
        self.assertIn("URLError", message)
        self.assertNotIn(FXMD_KEY, message)

    def test_malformed_key_is_refused(self):
        message = self.assert_fails(["--no-synthesis"], FakeOpener(), env={"FXMACRODATA_API_KEY": "has space"})
        self.assertNotIn("has space", message)

    def test_redirects_are_refused(self):
        request = urllib.request.Request("https://api.fxmacrodata.com/v1/calendar/usd", headers={"X-API-Key": FXMD_KEY})
        with self.assertRaises(main.BriefError) as ctx:
            main.NoRedirect().redirect_request(request, None, 302, "Found", {}, "https://elsewhere.example/")
        self.assertNotIn(FXMD_KEY, str(ctx.exception))

    def test_base_url_must_be_https(self):
        for url in ("http://api.fxmacrodata.com/v1", "https://"):
            with self.assertRaises(main.BriefError):
                main.FxMacroData(None, FakeOpener(), base_url=url)

    def test_synthesis_needs_nebius_key(self):
        message = self.assert_fails([], FakeOpener())
        self.assertIn("NEBIUS_API_KEY", message)


GOOD_BRIEF = {
    "summary": "US CPI on 14 October is the main event this week.",
    "points": [{"text": "Headline CPI was 3.4% YoY in August.", "evidence": ["E4"]}],
    "caveats": ["No consensus figures are included."],
}


class SynthesisTests(unittest.TestCase):
    def test_grounded_brief(self):
        opener = FakeOpener(nebius=model_reply("<think>plan</think>```json\n" + json.dumps(GOOD_BRIEF) + "\n```"))
        code, text = run([], opener, env={"NEBIUS_API_KEY": NEBIUS_KEY})
        self.assertEqual(code, 0, text)
        self.assertIn("## Brief (model output, unverified)", text)
        self.assertIn("[E4]", text)
        nebius = opener.requests[-1]
        self.assertEqual(nebius.get_header("Authorization"), f"Bearer {NEBIUS_KEY}")
        sent = json.loads(nebius.data)
        self.assertEqual(sent["model"], main.DEFAULT_NEBIUS_MODEL)
        self.assertIn('"id": "E1"', sent["messages"][1]["content"])
        self.assertNotIn(NEBIUS_KEY, text)

    def test_invented_citation_is_rejected(self):
        bad = dict(GOOD_BRIEF, points=[{"text": "x", "evidence": ["E99"]}])
        opener = FakeOpener(nebius=model_reply(bad))
        message = ErrorTests.assert_fails(self, [], opener, env={"NEBIUS_API_KEY": NEBIUS_KEY})
        self.assertIn("does not exist", message)

    def test_bad_model_output_is_rejected(self):
        for reply in (model_reply("not json"), model_reply({"points": []}),
                      model_reply(dict(GOOD_BRIEF, points=[{"text": "x", "evidence": []}])),
                      (200, {"choices": []}), (401, {"error": {"message": NEBIUS_KEY}})):
            message = ErrorTests.assert_fails(self, [], FakeOpener(nebius=reply), env={"NEBIUS_API_KEY": NEBIUS_KEY})
            self.assertNotIn(NEBIUS_KEY, message)


if __name__ == "__main__":
    unittest.main()
