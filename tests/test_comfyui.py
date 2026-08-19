from pathlib import Path
import tempfile
import unittest

from ai_drama.comfyui import ComfyUIOutput, _collect_outputs
from ai_drama.video_pipeline import H3_WORKFLOW, QWEN_WORKFLOW, load_video_plan, render_workflow


class ComfyUIOutputTests(unittest.TestCase):
    def test_collects_image_and_video_outputs(self) -> None:
        outputs = _collect_outputs(
            {
                "11": {
                    "images": [
                        {"filename": "frame.png", "subfolder": "drama", "type": "output"}
                    ]
                },
                "17": {
                    "images": [
                        {"filename": "shot.mp4", "subfolder": "video", "type": "output"}
                    ]
                },
            }
        )
        self.assertEqual(outputs[0], ComfyUIOutput("frame.png", "drama", "output", "image"))
        self.assertEqual(outputs[1].media_type, "video")


class WorkflowTests(unittest.TestCase):
    def test_qwen_template_preserves_numeric_types(self) -> None:
        workflow = render_workflow(
            QWEN_WORKFLOW,
            {
                "__PROMPT__": "测试提示词",
                "__SEED__": 42,
                "__WIDTH__": 1344,
                "__HEIGHT__": 768,
                "__OUTPUT_PREFIX__": "ai_drama/test",
            },
        )
        self.assertEqual(workflow["5"]["inputs"]["text"], "测试提示词")
        self.assertEqual(workflow["9"]["inputs"]["seed"], 42)
        self.assertIsInstance(workflow["8"]["inputs"]["width"], int)
        self.assertEqual(workflow["9"]["inputs"]["steps"], 4)

    def test_h3_template_uses_official_four_step_settings(self) -> None:
        workflow = render_workflow(
            H3_WORKFLOW,
            {
                "__INPUT_IMAGE__": "opening.png",
                "__PROMPT__": "integrated_multimodal_description: test",
                "__SEED__": 7,
                "__WIDTH__": 1344,
                "__HEIGHT__": 768,
                "__LENGTH__": 124,
                "__OUTPUT_PREFIX__": "video/ai_drama/test",
            },
        )
        self.assertEqual(workflow["3"]["inputs"]["shift_video"], 6.0)
        self.assertEqual(workflow["3"]["inputs"]["shift_audio"], 3.0)
        self.assertEqual(workflow["12"]["inputs"]["steps"], 4)
        self.assertEqual(workflow["8"]["inputs"]["length"], 124)
        self.assertEqual(workflow["7"]["inputs"]["image"], "opening.png")

    def test_loads_family_video_plan(self) -> None:
        plan = load_video_plan(Path("examples/family_money_argument_video.json"))
        self.assertEqual(plan["h3_shots"][0]["keyframe_id"], "opening_conflict")
        self.assertIn("overall_soundscape:", plan["h3_shots"][0]["prompt"])
        self.assertIn("non_diegetic_music: N/A", plan["h3_shots"][0]["prompt"])

    def test_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plan.json"
            path.write_text(
                '{"title":"x","keyframes":[{"id":"a"},{"id":"a"}],'
                '"h3_shots":[{"id":"b"}]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "不能重复"):
                load_video_plan(path)


if __name__ == "__main__":
    unittest.main()
