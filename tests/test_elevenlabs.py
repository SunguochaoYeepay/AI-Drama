import unittest

from ai_drama.elevenlabs import (
    ElevenLabsClient,
    ElevenLabsError,
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
            b'"message":"missing permission"}}'
        )
        client = ElevenLabsClient(
            "test-key",
            transport=lambda request, timeout: (401, body),
        )
        with self.assertRaisesRegex(ElevenLabsError, "sound_generation"):
            client.generate({"text": "rain"})


if __name__ == "__main__":
    unittest.main()
