from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from ai_drama.audio import build_timeline, merge_audio, write_srt
from ai_drama.models import AudioSettings


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 FFmpeg")
class AudioTests(unittest.TestCase):
    def test_merges_segments_with_pause_and_writes_srt(self) -> None:
        settings = AudioSettings()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.mp3"
            second = root / "second.mp3"
            for path, frequency in ((first, 440), (second, 660)):
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency={frequency}:duration=0.12",
                        "-ar",
                        "32000",
                        "-ac",
                        "1",
                        "-b:a",
                        "128k",
                        "-y",
                        str(path),
                    ],
                    check=True,
                )
            destination = root / "dialogue.mp3"
            merge_audio([first, second], [100, 0], destination, root, settings)
            timeline = build_timeline(
                [first, second], [100, 0], ["甲", "乙"], ["你好", "你好"]
            )
            subtitle = root / "dialogue.srt"
            write_srt(subtitle, timeline)

            self.assertGreater(destination.stat().st_size, 0)
            self.assertGreaterEqual(timeline[1].start_ms - timeline[0].end_ms, 100)
            self.assertIn("甲：你好", subtitle.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
