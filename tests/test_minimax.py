import json
import unittest

from ai_drama.minimax import MiniMaxClient, MiniMaxError
from ai_drama.models import AudioSettings, Voice


class MiniMaxClientTests(unittest.TestCase):
    def test_builds_official_speech_28_payload(self) -> None:
        client = MiniMaxClient("test-key", transport=lambda request, timeout: (200, b"{}"))
        payload = client.build_payload(
            model="speech-2.8-hd",
            text="你好",
            voice=Voice("voice-id", emotion="happy"),
            audio=AudioSettings(),
            language_boost="Chinese",
        )
        self.assertEqual(payload["model"], "speech-2.8-hd")
        self.assertEqual(payload["voice_setting"]["emotion"], "happy")
        self.assertEqual(payload["output_format"], "hex")

    def test_decodes_hex_audio(self) -> None:
        response = json.dumps(
            {
                "data": {"audio": "494433", "status": 2},
                "extra_info": {"audio_format": "mp3"},
                "trace_id": "trace-1",
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        ).encode()
        client = MiniMaxClient("test-key", transport=lambda request, timeout: (200, response))
        result = client.synthesize({"text": "你好"})
        self.assertEqual(result.audio, b"ID3")
        self.assertEqual(result.trace_id, "trace-1")

    def test_surfaces_api_error(self) -> None:
        response = json.dumps(
            {"base_resp": {"status_code": 1004, "status_msg": "invalid token"}}
        ).encode()
        client = MiniMaxClient("test-key", transport=lambda request, timeout: (200, response))
        with self.assertRaisesRegex(MiniMaxError, "invalid token"):
            client.synthesize({"text": "你好"})


if __name__ == "__main__":
    unittest.main()
