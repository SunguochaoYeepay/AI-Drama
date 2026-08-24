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


@dataclass(frozen=True)
class PlacedEffect:
    path: Path
    start_ms: int
    volume_db: float
    loop: bool
    until_end: bool
    fade_in_ms: int
    fade_out_ms: int


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise AudioToolError("需要先安装 FFmpeg，才能合并音频和生成字幕")


def duration_ms(path: Path) -> int:
    result = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
            "-progress",
            "pipe:1",
        ]
    )
    try:
        decoded_microseconds = max(
            int(line.split("=", 1)[1])
            for line in result.stdout.splitlines()
            if line.startswith("out_time_us=")
        )
        return max(1, round(decoded_microseconds / 1000))
    except (ValueError, IndexError) as exc:
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


def mix_sound_effects(
    dialogue_path: Path,
    effects: list[PlacedEffect],
    destination: Path,
    audio: AudioSettings,
) -> None:
    if not effects:
        raise AudioToolError("至少需要一个环境音才能执行混音")
    require_ffmpeg()
    base_duration_ms = duration_ms(dialogue_path)
    command = ["ffmpeg", "-v", "error", "-i", str(dialogue_path)]
    active_effects: list[tuple[int, PlacedEffect, int]] = []
    for effect in effects:
        available_ms = base_duration_ms - effect.start_ms
        if available_ms <= 0:
            continue
        if effect.loop:
            command.extend(["-stream_loop", "-1"])
        command.extend(["-i", str(effect.path)])
        source_duration_ms = duration_ms(effect.path)
        play_duration_ms = available_ms if effect.until_end else min(source_duration_ms, available_ms)
        active_effects.append((len(active_effects) + 1, effect, play_duration_ms))

    if not active_effects:
        raise AudioToolError("所有环境音都位于对白结束之后，无法混音")

    filters = ["[0:a]anull[dialogue]"]
    labels = ["[dialogue]"]
    for input_index, effect, play_duration_ms in active_effects:
        play_seconds = play_duration_ms / 1000
        chain = (
            f"[{input_index}:a]volume={effect.volume_db}dB,"
            f"atrim=duration={play_seconds:.3f},asetpts=PTS-STARTPTS"
        )
        fade_in_seconds = min(effect.fade_in_ms, play_duration_ms) / 1000
        fade_out_seconds = min(effect.fade_out_ms, play_duration_ms) / 1000
        if fade_in_seconds > 0:
            chain += f",afade=t=in:st=0:d={fade_in_seconds:.3f}"
        if fade_out_seconds > 0:
            fade_out_start = max(0.0, play_seconds - fade_out_seconds)
            chain += f",afade=t=out:st={fade_out_start:.3f}:d={fade_out_seconds:.3f}"
        chain += f",adelay={effect.start_ms}:all=1[sfx{input_index}]"
        filters.append(chain)
        labels.append(f"[sfx{input_index}]")

    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:"
        "normalize=0:dropout_transition=0,alimiter=limit=0.95[mix]"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[mix]",
            *_codec_args(audio),
            "-ar",
            str(audio.sample_rate),
            "-ac",
            str(audio.channel),
            "-y",
            str(destination),
        ]
    )
    _run(command)


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
