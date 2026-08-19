from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from ai_drama.models import AudioSettings


MERGE_FORMATS = {"mp3", "wav", "flac"}


class AudioToolError(RuntimeError):
    """Raised when local audio assembly fails."""


@dataclass(frozen=True)
class TimedLine:
    index: int
    speaker_name: str
    text: str
    start_ms: int
    end_ms: int


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise AudioToolError("需要先安装 FFmpeg，才能合并音频和生成字幕")


def duration_ms(path: Path) -> int:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        return max(1, round(float(result.stdout.strip()) * 1000))
    except ValueError as exc:
        raise AudioToolError(f"无法读取音频时长: {path}") from exc


def create_silence(path: Path, duration: int, audio: AudioSettings) -> None:
    if duration <= 0 or path.exists():
        return
    channel_layout = "mono" if audio.channel == 1 else "stereo"
    codec_args = _codec_args(audio)
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={audio.sample_rate}:cl={channel_layout}",
            "-t",
            f"{duration / 1000:.3f}",
            *codec_args,
            "-y",
            str(path),
        ]
    )


def merge_audio(
    segment_paths: list[Path],
    pauses_ms: list[int],
    destination: Path,
    working_dir: Path,
    audio: AudioSettings,
) -> None:
    if len(segment_paths) != len(pauses_ms):
        raise AudioToolError("音频片段和停顿数量不一致")
    if audio.format not in MERGE_FORMATS:
        raise AudioToolError("基础版合并仅支持 mp3、wav 或 flac 输出")
    require_ffmpeg()
    destination.parent.mkdir(parents=True, exist_ok=True)
    silence_dir = working_dir / "silence"
    silence_dir.mkdir(parents=True, exist_ok=True)

    entries: list[Path] = []
    for segment, pause_ms in zip(segment_paths, pauses_ms, strict=True):
        entries.append(segment.resolve())
        if pause_ms > 0:
            silence = silence_dir / f"{pause_ms}ms.{audio.format}"
            create_silence(silence, pause_ms, audio)
            entries.append(silence.resolve())

    concat_file = working_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{_ffmpeg_escape(path)}'\n" for path in entries),
        encoding="utf-8",
    )
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            *(_codec_args(audio)),
            "-ar",
            str(audio.sample_rate),
            "-ac",
            str(audio.channel),
            "-y",
            str(destination),
        ]
    )


def build_timeline(
    segment_paths: list[Path],
    pauses_ms: list[int],
    speakers: list[str],
    texts: list[str],
) -> list[TimedLine]:
    timeline: list[TimedLine] = []
    cursor = 0
    for index, (path, pause, speaker, text) in enumerate(
        zip(segment_paths, pauses_ms, speakers, texts, strict=True), start=1
    ):
        end = cursor + duration_ms(path)
        timeline.append(TimedLine(index, speaker, text, cursor, end))
        cursor = end + pause
    return timeline


def write_srt(path: Path, timeline: list[TimedLine]) -> None:
    blocks = []
    for item in timeline:
        blocks.append(
            f"{item.index}\n{_srt_time(item.start_ms)} --> {_srt_time(item.end_ms)}\n"
            f"{item.speaker_name}：{item.text}\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")


def _codec_args(audio: AudioSettings) -> list[str]:
    if audio.format == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", str(audio.bitrate)]
    if audio.format == "wav":
        return ["-c:a", "pcm_s16le"]
    if audio.format == "flac":
        return ["-c:a", "flac"]
    raise AudioToolError("基础版合并仅支持 mp3、wav 或 flac 输出")


def _ffmpeg_escape(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def _srt_time(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AudioToolError(f"找不到命令: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "未知错误"
        raise AudioToolError(f"音频处理失败: {message}") from exc
