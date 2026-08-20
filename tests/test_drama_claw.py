import unittest
from pathlib import Path

from ai_drama.drama_claw import DramaClawClient, build_canvas_nodes
from ai_drama.models import StoryScript


class DramaClawTests(unittest.TestCase):
    def setUp(self) -> None:
        self.story = StoryScript.from_dict(
            {
                "title": "测试家庭故事",
                "characters": {
                    "a": {"name": "角色甲", "voice_id": "voice-a"},
                    "b": {"name": "角色乙", "voice_id": "voice-b"},
                },
                "lines": [
                    {"speaker": "a", "text": "第一句。", "pause_after_ms": 300},
                    {"speaker": "b", "text": "第二句。"},
                ],
            }
        )

    def test_builds_script_and_overview_nodes(self) -> None:
        nodes, edges = build_canvas_nodes(self.story, None, {}, Path("outputs/test"))
        self.assertEqual([node["id"] for node in nodes], ["story-overview", "story-script"])
        self.assertEqual(nodes[1]["type"], "scriptNode")
        self.assertEqual(len(nodes[1]["data"]["scriptResult"]["rows"]), 2)
        self.assertEqual(edges, [{"id": "edge-story-overview-story-script", "source": "story-overview", "target": "story-script", "type": "default"}])

    def test_client_unwraps_drama_claw_envelope(self) -> None:
        client = DramaClawClient("http://example.test")
        client._send = lambda request: {"id": "project-1", "name": "demo"}  # type: ignore[method-assign]
        self.assertEqual(client.get_canvas("project-1", "demo")["name"], "demo")


if __name__ == "__main__":
    unittest.main()
