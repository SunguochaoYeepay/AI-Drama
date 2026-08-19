import json
from pathlib import Path
import tempfile
import unittest

from ai_drama.audio import TimedLine
from ai_drama.elevenlabs import DialogueResult, SoundEffectResult
from ai_drama.minimax import SynthesisResult
from ai_drama.models import StoryScript
from ai_drama.pipeline import (
    default_output_dir,
    _generate_sound_effects,
    generate_elevenlabs_story,
    generate_story,
)


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, payload: dict) -> SynthesisResult:
        self.calls += 1
        return SynthesisResult(b"audio", f"trace-{self.calls}", {})


class FakeDialogueClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_dialogue(self, payload: dict) -> DialogueResult:
        self.calls += 1
        return DialogueResult(
            audio=b"ID3-dialogue",
            voice_segments=[
                {
                    "voice_id": "voice-a",
                    "start_time_seconds": 0,
                    "end_time_seconds": 1.2,
                    "dialogue_input_index": 0,
                },
                {
                    "voice_id": "voice-b",
                    "start_time_seconds": 1.3,
                    "end_time_seconds": 2.1,
                    "dialogue_input_index": 1,
                },
            ],
            alignment=None,
            normalized_alignment=None,
        )


class FakeSoundClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, payload: dict) -> SoundEffectResult:
        self.calls += 1
        return SoundEffectResult(audio=b"ID3-effect")


class PipelineTests(unittest.TestCase):
    def test_dry_run_writes_generation_plan(self) -> None:
        story = StoryScript.from_dict(
            {
                "title": "测试故事",
                "characters": {
                    "a": {"name": "角色甲", "voice_id": "voice-a"},
                    "b": {"name": "角色乙", "voice_id": "voice-b"},
                },
                "lines": [
                    {"speaker": "a", "text": "第一句。"},
                    {"speaker": "b", "text": "第二句。", "emotion": "surprised"},
                ],
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = generate_story(story, None, output, dry_run=True, progress=lambda _: None)
            plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(plan["lines"]), 2)
        self.assertEqual(plan["lines"][1]["request"]["voice_setting"]["emotion"], "surprised")

    def test_reuses_unchanged_segments(self) -> None:
        story = StoryScript.from_dict(
            {
                "title": "测试故事",
                "characters": {"a": {"name": "角色甲", "voice_id": "voice-a"}},
                "lines": [{"speaker": "a", "text": "这一句只应生成一次。"}],
            }
        )
        client = FakeClient()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            first = generate_story(story, client, output, merge=False, progress=lambda _: None)
            second = generate_story(story, client, output, merge=False, progress=lambda _: None)

        self.assertEqual(client.calls, 1)
        self.assertEqual(first["generated_segments"], 1)
        self.assertEqual(second["cached_segments"], 1)

    def test_preserves_chinese_script_name_in_default_output(self) -> None:
        self.assertEqual(default_output_dir(Path("深夜来电.json")), Path("outputs/深夜来电"))
        self.assertEqual(
            default_output_dir(Path("深夜来电.json"), "elevenlabs"),
            Path("outputs/深夜来电_elevenlabs"),
        )

    def test_dry_run_includes_sound_effect_request(self) -> None:
        story = StoryScript.from_dict(
            {
                "title": "雨夜",
                "characters": {"a": {"name": "角色甲", "voice_id": "voice-a"}},
                "lines": [{"speaker": "a", "text": "下雨了。"}],
                "sound_effects": [
                    {
                        "id": "rain",
                        "prompt": "Steady rain, no music",
                        "duration_seconds": 5,
                        "start_at_line": 1,
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            generate_story(story, None, output, dry_run=True, progress=lambda _: None)
            plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["sound_effects"][0]["request"]["text"], "Steady rain, no music")
        self.assertEqual(plan["sound_effects"][0]["request"]["duration_seconds"], 5)

    def test_generates_and_caches_elevenlabs_dialogue_with_timeline(self) -> None:
        story = StoryScript.from_dict(
            {
                "title": "对话测试",
                "characters": {
                    "a": {
                        "name": "角色甲",
                        "voice_id": "minimax-a",
                        "elevenlabs_voice_id": "voice-a",
                    },
                    "b": {
                        "name": "角色乙",
                        "voice_id": "minimax-b",
                        "elevenlabs_voice_id": "voice-b",
                    },
                },
                "lines": [
                    {"speaker": "a", "text": "你来了。", "emotion": "calm"},
                    {"speaker": "b", "text": "我来了。", "emotion": "happy"},
                ],
            }
        )
        client = FakeDialogueClient()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            first = generate_elevenlabs_story(story, client, output, progress=lambda _: None)
            second = generate_elevenlabs_story(story, client, output, progress=lambda _: None)
            subtitle = (output / "dialogue.srt").read_text(encoding="utf-8")
            plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))

        self.assertEqual(client.calls, 1)
        self.assertFalse(first["cached_dialogue"])
        self.assertTrue(second["cached_dialogue"])
        self.assertIn("角色乙：我来了。", subtitle)
        self.assertEqual(plan["request"]["inputs"][1]["text"], "[happy] 我来了。")

    def test_shares_sound_effect_cache_across_provider_outputs(self) -> None:
        story = StoryScript.from_dict(
            {
                "title": "环境音缓存",
                "characters": {"a": {"name": "角色甲", "voice_id": "voice-a"}},
                "lines": [{"speaker": "a", "text": "下雨了。"}],
                "sound_effects": [
                    {"id": "rain", "prompt": "Steady rain", "start_ms": 0}
                ],
            }
        )
        timeline = [TimedLine(1, "角色甲", "下雨了。", 0, 1000)]
        client = FakeSoundClient()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_output = root / "minimax"
            second_output = root / "elevenlabs"
            first_output.mkdir()
            second_output.mkdir()
            _generate_sound_effects(
                story, client, first_output, timeline, progress=lambda _: None
            )
            _generate_sound_effects(
                story, client, second_output, timeline, progress=lambda _: None
            )

        self.assertEqual(client.calls, 1)


if __name__ == "__main__":
    unittest.main()
