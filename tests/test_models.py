import unittest

from ai_drama.models import ScriptValidationError, StoryScript


def valid_story() -> dict:
    return {
        "title": "测试故事",
        "characters": {
            "narrator": {
                "name": "旁白",
                "voice_id": "Chinese (Mandarin)_Lyrical_Voice",
            }
        },
        "lines": [{"speaker": "narrator", "text": "故事开始了。"}],
    }


class StoryScriptTests(unittest.TestCase):
    def test_loads_defaults(self) -> None:
        story = StoryScript.from_dict(valid_story())
        self.assertEqual(story.model, "speech-2.8-hd")
        self.assertEqual(story.audio.format, "mp3")
        self.assertEqual(story.lines[0].pause_after_ms, 250)

    def test_loads_elevenlabs_voice_id(self) -> None:
        data = valid_story()
        data["characters"]["narrator"]["elevenlabs_voice_id"] = "voice-zh"
        story = StoryScript.from_dict(data)
        self.assertEqual(story.characters["narrator"].elevenlabs_voice_id, "voice-zh")

    def test_rejects_unknown_speaker(self) -> None:
        data = valid_story()
        data["lines"][0]["speaker"] = "missing"
        with self.assertRaisesRegex(ScriptValidationError, "未定义角色"):
            StoryScript.from_dict(data)

    def test_rejects_unsupported_emotion(self) -> None:
        data = valid_story()
        data["lines"][0]["emotion"] = "excited"
        with self.assertRaisesRegex(ScriptValidationError, "emotion"):
            StoryScript.from_dict(data)

    def test_rejects_invalid_audio_object(self) -> None:
        data = valid_story()
        data["audio"] = "mp3"
        with self.assertRaisesRegex(ScriptValidationError, "audio 必须是对象"):
            StoryScript.from_dict(data)

    def test_loads_sound_effect(self) -> None:
        data = valid_story()
        data["sound_effects"] = [
            {
                "id": "rain",
                "prompt": "Steady rain, no music",
                "start_at_line": 1,
                "duration_seconds": 8,
                "loop": True,
                "until_end": True,
            }
        ]
        story = StoryScript.from_dict(data)
        self.assertEqual(story.sound_effects[0].id, "rain")

    def test_rejects_until_end_without_loop(self) -> None:
        data = valid_story()
        data["sound_effects"] = [
            {"id": "rain", "prompt": "rain", "until_end": True}
        ]
        with self.assertRaisesRegex(ScriptValidationError, "loop=true"):
            StoryScript.from_dict(data)


if __name__ == "__main__":
    unittest.main()
