import json
import unittest

from minimax_tts import MiniMaxSpeechClient, MiniMaxSpeechError


class RecordingTransport:
    def __init__(self, response):
        self.response = json.dumps(response).encode()
        self.calls = []

    def __call__(self, endpoint, headers, body, timeout):
        self.calls.append((endpoint, headers, json.loads(body), timeout))
        return self.response


class MiniMaxSpeechClientTests(unittest.TestCase):
    def test_synthesize_uses_global_endpoint_and_decodes_hex_audio(self):
        transport = RecordingTransport(
            {
                "data": {"audio": "52494646", "status": 2},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )
        client = MiniMaxSpeechClient("unit-test-key", transport=transport)

        result = client.synthesize(
            "Hello from the speech client.",
            voice_setting={"voice_id": "English_expressive_narrator"},
            pronunciation_dict={"tone": ["API/A P I"]},
            audio_setting={"format": "wav", "sample_rate": 32000},
            voice_modify={"pitch": 1},
            subtitle_enable=True,
        )

        endpoint, headers, payload, timeout = transport.calls[0]
        self.assertEqual(endpoint, "https://api.minimax.io/v1/t2a_v2")
        self.assertEqual(headers["Authorization"], "Bearer unit-test-key")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(payload["model"], "speech-2.8-hd")
        self.assertEqual(payload["audio_setting"]["format"], "wav")
        self.assertEqual(payload["voice_modify"], {"pitch": 1})
        self.assertTrue(payload["subtitle_enable"])
        self.assertFalse(payload["stream"])
        self.assertEqual(timeout, 60)
        self.assertEqual(result.audio, b"RIFF")
        self.assertEqual(result.status, 2)

    def test_synthesize_uses_china_endpoint_and_parses_audio_url(self):
        audio_url = "https://example.invalid/generated-audio.mp3"
        transport = RecordingTransport(
            {
                "data": {"audio": audio_url, "status": 2},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )
        client = MiniMaxSpeechClient(
            "unit-test-key", region="cn_zh", transport=transport
        )

        result = client.synthesize("Hello from the China endpoint.", output_format="url")

        endpoint, _, payload, _ = transport.calls[0]
        self.assertEqual(endpoint, "https://api.minimaxi.com/v1/t2a_v2")
        self.assertEqual(payload["output_format"], "url")
        self.assertEqual(result.url, audio_url)
        self.assertIsNone(result.audio)

    def test_synthesize_raises_for_api_error(self):
        transport = RecordingTransport(
            {
                "data": None,
                "base_resp": {"status_code": 1001, "status_msg": "invalid request"},
            }
        )
        client = MiniMaxSpeechClient("unit-test-key", transport=transport)

        with self.assertRaisesRegex(MiniMaxSpeechError, "invalid request"):
            client.synthesize("Hello")

    def test_synthesize_rejects_unsupported_audio_format(self):
        client = MiniMaxSpeechClient(
            "unit-test-key",
            transport=RecordingTransport(
                {
                    "data": {"audio": "00", "status": 2},
                    "base_resp": {"status_code": 0},
                }
            ),
        )

        with self.assertRaisesRegex(ValueError, "audio format"):
            client.synthesize("Hello", audio_setting={"format": "ogg"})


if __name__ == "__main__":
    unittest.main()
