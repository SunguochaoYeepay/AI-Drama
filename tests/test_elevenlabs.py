import base64
import json
import unittest

from ai_drama.elevenlabs import (
    DialogueResult,
    ElevenLabsClient,
    ElevenLabsError,
    build_dialogue_payload,
    build_sound_effect_payload,
)
from ai_drama.models import SoundEffect


class ElevenLabsClientTests(unittest.TestCase):
    def test_builds_official_sound_effect_payload(self) -> None:
        effect = SoundEffect(
            id="rain",
            prompt="Steady rain, no music",
            duration_seconds=8,
            prompt_influence=0.7,
            loop=True,
        )
        payload = build_sound_effect_payload(effect)
        self.assertEqual(payload["model_id"], "eleven_text_to_sound_v2")
        self.assertEqual(payload["duration_seconds"], 8)
        self.assertTrue(payload["loop"])

    def test_returns_binary_audio(self) -> None:
        client = ElevenLabsClient(
            "test-key",
            transport=lambda request, timeout: (200, b"ID3-audio"),
        )
        result = client.generate({"text": "rain"})
        self.assertEqual(result.audio, b"ID3-audio")

    def test_surfaces_api_error(self) -> None:
        client = ElevenLabsClient(
            "test-key",
            transport=lambda request, timeout: (401, b'{"detail":"invalid key"}'),
        )
        with self.assertRaisesRegex(ElevenLabsError, "invalid key"):
            client.generate({"text": "rain"})

    def test_explains_missing_sound_generation_permission(self) -> None:
        body = (
            b'{"detail":{"status":"missing_permissions",'
            b'"message":"missing permission sound_generation"}}'
        )
        client = ElevenLabsClient(
            "test-key",
            transport=lambda request, timeout: (401, body),
        )
        with self.assertRaisesRegex(ElevenLabsError, "sound_generation"):
            client.generate({"text": "rain"})

    def test_decodes_dialogue_audio_and_timestamps(self) -> None:
        response = json.dumps(
            {
                "audio_base64": base64.b64encode(b"ID3-dialogue").decode(),
                "voice_segments": [
                    {
                        "voice_id": "voice-a",
                        "start_time_seconds": 0,
                        "end_time_seconds": 1.2,
                        "dialogue_input_index": 0,
                    }
                ],
                "alignment": None,
                "normalized_alignment": None,
            }
        ).encode()
        client = ElevenLabsClient(
            "test-key",
            transport=lambda request, timeout: (200, response),
        )
        result = client.generate_dialogue(
            build_dialogue_payload([{"text": "你好", "voice_id": "voice-a"}])
        )
        self.assertEqual(result.audio, b"ID3-dialogue")
        self.assertEqual(result.voice_segments[0]["end_time_seconds"], 1.2)


if __name__ == "__main__":
    unittest.main()
