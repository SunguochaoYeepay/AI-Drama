from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from ai_drama.audio import (
    AudioToolError,
    MERGE_FORMATS,
    PlacedEffect,
    TimedLine,
    build_timeline,
    merge_audio,
    mix_sound_effects,
    write_srt,
)
from ai_drama.elevenlabs import ElevenLabsClient, build_sound_effect_payload
from ai_drama.minimax import MiniMaxClient, build_payload, save_audio
from ai_drama.models import SoundEffect, StoryScript


Progress = Callable[[str], None]


def generate_story(
    story: StoryScript,
    client: MiniMaxClient | None,
    output_dir: Path,
    *,
    sound_client: ElevenLabsClient | None = None,
    dry_run: bool = False,
    merge: bool = True,
    progress: Progress = print,
) -> dict[str, Any]:
    if merge and story.audio.format not in MERGE_FORMATS:
        raise AudioToolError("基础版合并仅支持 mp3、wav 或 flac；可改用 --no-merge")
    if story.sound_effects and not merge and not dry_run:
        raise AudioToolError("环境音需要先合并对白，不能与 --no-merge 同时使用")
    output_dir.mkdir(parents=True, exist_ok=True)
    segment_dir = output_dir / "segments"
    segment_dir.mkdir(exist_ok=True)

    plan = _build_plan(story)
    _write_json(output_dir / "plan.json", plan)
    if dry_run:
        progress(f"脚本检查通过：{len(story.characters)} 个角色，{len(story.lines)} 句台词")
        return {"dry_run": True, "line_count": len(story.lines), "output_dir": str(output_dir)}
    if client is None:
        raise ValueError("正式生成必须提供 MiniMaxClient")

    segment_paths: list[Path] = []
    generated = 0
    cached = 0
    segment_records: list[dict[str, Any]] = []
    for item in plan["lines"]:
        extension = story.audio.format
        audio_path = segment_dir / f"{item['index']:03d}_{_safe_name(item['speaker'])}.{extension}"
        metadata_path = audio_path.with_suffix(audio_path.suffix + ".json")
        payload = item["request"]
        request_hash = _request_hash(payload)

        cached_metadata = _read_json(metadata_path)
        if (
            audio_path.exists()
            and audio_path.stat().st_size > 0
            and cached_metadata
            and cached_metadata.get("request_hash") == request_hash
        ):
            cached += 1
            progress(f"[{item['index']}/{len(story.lines)}] 复用 {item['speaker_name']} 的已有音频")
            record = cached_metadata
        else:
            progress(f"[{item['index']}/{len(story.lines)}] 生成 {item['speaker_name']}：{item['text'][:30]}")
            result = client.synthesize(payload)
            save_audio(audio_path, result.audio)
            generated += 1
            record = {
                "index": item["index"],
                "speaker": item["speaker"],
                "speaker_name": item["speaker_name"],
                "text": item["text"],
                "audio_file": str(audio_path.relative_to(output_dir)),
                "request_hash": request_hash,
                "trace_id": result.trace_id,
                "extra_info": result.extra_info,
            }
            _write_json(metadata_path, record)
        segment_paths.append(audio_path)
        segment_records.append(record)

    result_manifest: dict[str, Any] = {
        "title": story.title,
        "model": story.model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generated_segments": generated,
        "cached_segments": cached,
        "segments": segment_records,
    }
    if merge:
        dialogue_path = output_dir / f"dialogue.{story.audio.format}"
        pauses = [line.pause_after_ms for line in story.lines]
        merge_audio(segment_paths, pauses, dialogue_path, output_dir, story.audio)
        timeline = build_timeline(
            segment_paths,
            pauses,
            [story.characters[line.speaker].name for line in story.lines],
            [line.text for line in story.lines],
        )
        subtitle_path = output_dir / "dialogue.srt"
        write_srt(subtitle_path, timeline)
        result_manifest["dialogue_file"] = dialogue_path.name
        result_manifest["subtitle_file"] = subtitle_path.name
        result_manifest["timeline"] = [asdict(item) for item in timeline]
        progress(f"完整对话已生成：{dialogue_path}")
        if story.sound_effects:
            if sound_client is None:
                raise ValueError("故事包含环境音，但没有提供 ElevenLabsClient")
            effect_records, placed_effects = _generate_sound_effects(
                story,
                sound_client,
                output_dir,
                timeline,
                progress,
            )
            final_mix_path = output_dir / f"final_mix.{story.audio.format}"
            mix_sound_effects(dialogue_path, placed_effects, final_mix_path, story.audio)
            result_manifest["sound_effects"] = effect_records
            result_manifest["final_mix_file"] = final_mix_path.name
            progress(f"环境音混音已生成：{final_mix_path}")

    _write_json(output_dir / "manifest.json", result_manifest)
    return result_manifest


def default_output_dir(script_path: Path) -> Path:
    return Path("outputs") / _safe_name(script_path.stem)


def _build_plan(story: StoryScript) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    for index, line in enumerate(story.lines, start=1):
        character = story.characters[line.speaker]
        voice = character.voice.with_overrides(line)
        voice.validate(f"lines[{index - 1}]")
        payload = build_payload(
            model=story.model,
            text=line.text,
            voice=voice,
            audio=story.audio,
            language_boost=story.language_boost,
        )
        lines.append(
            {
                "index": index,
                "speaker": line.speaker,
                "speaker_name": character.name,
                "text": line.text,
                "pause_after_ms": line.pause_after_ms,
                "request": payload,
            }
        )
    return {
        "title": story.title,
        "model": story.model,
        "audio": asdict(story.audio),
        "characters": {
            key: {"name": character.name, "voice": asdict(character.voice)}
            for key, character in story.characters.items()
        },
        "lines": lines,
        "sound_effects": [
            {
                **asdict(effect),
                "request": build_sound_effect_payload(effect),
            }
            for effect in story.sound_effects
        ],
    }


def _generate_sound_effects(
    story: StoryScript,
    client: ElevenLabsClient,
    output_dir: Path,
    timeline: list[TimedLine],
    progress: Progress,
) -> tuple[list[dict[str, Any]], list[PlacedEffect]]:
    effect_dir = output_dir / "sound_effects"
    effect_dir.mkdir(exist_ok=True)
    records: list[dict[str, Any]] = []
    placed: list[PlacedEffect] = []
    for index, effect in enumerate(story.sound_effects, start=1):
        payload = build_sound_effect_payload(effect)
        request_hash = _request_hash(payload)
        audio_path = effect_dir / f"{index:03d}_{_safe_name(effect.id)}.mp3"
        metadata_path = audio_path.with_suffix(".mp3.json")
        metadata = _read_json(metadata_path)
        if (
            audio_path.exists()
            and audio_path.stat().st_size > 0
            and metadata
            and metadata.get("request_hash") == request_hash
        ):
            progress(f"[环境音 {index}/{len(story.sound_effects)}] 复用 {effect.id}")
            record = metadata
        else:
            progress(
                f"[环境音 {index}/{len(story.sound_effects)}] 生成 {effect.id}："
                f"{effect.prompt[:36]}"
            )
            result = client.generate(payload)
            save_audio(audio_path, result.audio)
            record = {
                "id": effect.id,
                "prompt": effect.prompt,
                "audio_file": str(audio_path.relative_to(output_dir)),
                "request_hash": request_hash,
            }
            _write_json(metadata_path, record)

        start_ms = _resolve_effect_start(effect, timeline)
        record = {
            **record,
            "start_ms": start_ms,
            "volume_db": effect.volume_db,
            "loop": effect.loop,
            "until_end": effect.until_end,
        }
        records.append(record)
        placed.append(
            PlacedEffect(
                path=audio_path,
                start_ms=start_ms,
                volume_db=effect.volume_db,
                loop=effect.loop,
                until_end=effect.until_end,
                fade_in_ms=effect.fade_in_ms,
                fade_out_ms=effect.fade_out_ms,
            )
        )
    return records, placed


def _resolve_effect_start(effect: SoundEffect, timeline: list[TimedLine]) -> int:
    if effect.start_at_line is not None:
        base = timeline[effect.start_at_line - 1].start_ms
    else:
        base = effect.start_ms or 0
    return max(0, base + effect.offset_ms)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^\w-]+", "_", value, flags=re.UNICODE).strip("_")
    return cleaned or "story"


def _request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
