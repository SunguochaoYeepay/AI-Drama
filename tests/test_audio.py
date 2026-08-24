from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from ai_drama.audio import (
    PlacedEffect,
    build_timeline,
    duration_ms,
    merge_audio,
    mix_sound_effects,
    write_srt,
)
from ai_drama.models import AudioSettings


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 FFmpeg")
class AudioTests(unittest.TestCase):
    def _tone(self, path: Path, frequency: int, duration: float = 0.12) -> None:
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration={duration}",
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

    def test_merges_segments_with_pause_and_writes_srt(self) -> None:
        settings = AudioSettings()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.mp3"
            second = root / "second.mp3"
            for path, frequency in ((first, 440), (second, 660)):
                self._tone(path, frequency)
            destination = root / "dialogue.mp3"
            merge_audio([first, second], [100, 0], destination, root, settings)
            timeline = build_timeline(
                [first, second], [100, 0], ["甲", "乙"], ["你好", "你好"]
            )
            subtitle = root / "dialogue.srt"
            write_srt(subtitle, timeline)

            self.assertGreater(destination.stat().st_size, 0)
            self.assertGreaterEqual(timeline[1].start_ms - timeline[0].end_ms, 100)
            self.assertLess(
                abs(duration_ms(destination) - timeline[-1].end_ms),
                50,
            )
            self.assertIn("甲：你好", subtitle.read_text(encoding="utf-8"))

    def test_mixes_placed_effect_without_extending_dialogue(self) -> None:
        settings = AudioSettings()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dialogue = root / "dialogue.mp3"
            effect = root / "rain.mp3"
            destination = root / "final_mix.mp3"
            self._tone(dialogue, 440, 0.8)
            self._tone(effect, 220, 0.2)
            mix_sound_effects(
                dialogue,
                [
                    PlacedEffect(
                        path=effect,
                        start_ms=100,
                        volume_db=-18,
                        loop=True,
                        until_end=True,
                        fade_in_ms=50,
                        fade_out_ms=50,
                    )
                ],
                destination,
                settings,
            )
            self.assertGreater(destination.stat().st_size, 0)
            self.assertLess(abs(duration_ms(destination) - duration_ms(dialogue)), 100)


if __name__ == "__main__":
    unittest.main()
