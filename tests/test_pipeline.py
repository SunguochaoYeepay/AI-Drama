import json
from pathlib import Path
import tempfile
import unittest

from ai_drama.minimax import SynthesisResult
from ai_drama.models import StoryScript
from ai_drama.pipeline import default_output_dir, generate_story


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, payload: dict) -> SynthesisResult:
        self.calls += 1
        return SynthesisResult(b"audio", f"trace-{self.calls}", {})


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


if __name__ == "__main__":
    unittest.main()
