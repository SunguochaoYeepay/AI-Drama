from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


SUPPORTED_MODELS = {"speech-2.8-hd", "speech-2.8-turbo"}
SUPPORTED_EMOTIONS = {
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgusted",
    "surprised",
    "calm",
}
SUPPORTED_FORMATS = {"mp3", "wav", "flac", "pcm", "pcmu_raw", "pcmu_wav", "opus"}
SUPPORTED_SAMPLE_RATES = {8000, 16000, 22050, 24000, 32000, 44100}
SUPPORTED_BITRATES = {32000, 64000, 128000, 256000}


class ScriptValidationError(ValueError):
    """Raised when a story script cannot be safely sent to MiniMax."""


@dataclass(frozen=True)
class Voice:
    voice_id: str
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    emotion: str | None = None
    text_normalization: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any], location: str) -> Voice:
        voice = cls(
            voice_id=str(data.get("voice_id", "")).strip(),
            speed=float(data.get("speed", 1.0)),
            vol=float(data.get("vol", 1.0)),
            pitch=int(data.get("pitch", 0)),
            emotion=_optional_text(data.get("emotion")),
            text_normalization=bool(data.get("text_normalization", True)),
        )
        voice.validate(location)
        return voice

    def validate(self, location: str) -> None:
        if not self.voice_id:
            raise ScriptValidationError(f"{location}.voice_id 不能为空")
        if not 0.5 <= self.speed <= 2:
            raise ScriptValidationError(f"{location}.speed 必须在 0.5 到 2 之间")
        if not 0 < self.vol <= 10:
            raise ScriptValidationError(f"{location}.vol 必须大于 0 且不超过 10")
        if not -12 <= self.pitch <= 12:
            raise ScriptValidationError(f"{location}.pitch 必须在 -12 到 12 之间")
        if self.emotion and self.emotion not in SUPPORTED_EMOTIONS:
            raise ScriptValidationError(
                f"{location}.emotion 不支持 {self.emotion!r}，可用值: "
                + ", ".join(sorted(SUPPORTED_EMOTIONS))
            )

    def with_overrides(self, line: Line) -> Voice:
        return Voice(
            voice_id=self.voice_id,
            speed=line.speed if line.speed is not None else self.speed,
            vol=line.vol if line.vol is not None else self.vol,
            pitch=line.pitch if line.pitch is not None else self.pitch,
            emotion=line.emotion if line.emotion is not None else self.emotion,
            text_normalization=self.text_normalization,
        )


@dataclass(frozen=True)
class Character:
    name: str
    voice: Voice

    @classmethod
    def from_dict(cls, key: str, data: dict[str, Any]) -> Character:
        name = str(data.get("name", key)).strip()
        if not name:
            raise ScriptValidationError(f"characters.{key}.name 不能为空")
        return cls(name=name, voice=Voice.from_dict(data, f"characters.{key}"))


@dataclass(frozen=True)
class Line:
    speaker: str
    text: str
    emotion: str | None = None
    speed: float | None = None
    vol: float | None = None
    pitch: int | None = None
    pause_after_ms: int = 250

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> Line:
        line = cls(
            speaker=str(data.get("speaker", "")).strip(),
            text=str(data.get("text", "")).strip(),
            emotion=_optional_text(data.get("emotion")),
            speed=_optional_float(data.get("speed")),
            vol=_optional_float(data.get("vol")),
            pitch=_optional_int(data.get("pitch")),
            pause_after_ms=int(data.get("pause_after_ms", 250)),
        )
        location = f"lines[{index}]"
        if not line.speaker:
            raise ScriptValidationError(f"{location}.speaker 不能为空")
        if not line.text:
            raise ScriptValidationError(f"{location}.text 不能为空")
        if len(line.text) >= 10_000:
            raise ScriptValidationError(f"{location}.text 必须少于 10000 个字符")
        if line.emotion and line.emotion not in SUPPORTED_EMOTIONS:
            raise ScriptValidationError(f"{location}.emotion 不支持 {line.emotion!r}")
        if line.speed is not None and not 0.5 <= line.speed <= 2:
            raise ScriptValidationError(f"{location}.speed 必须在 0.5 到 2 之间")
        if line.vol is not None and not 0 < line.vol <= 10:
            raise ScriptValidationError(f"{location}.vol 必须大于 0 且不超过 10")
        if line.pitch is not None and not -12 <= line.pitch <= 12:
            raise ScriptValidationError(f"{location}.pitch 必须在 -12 到 12 之间")
        if not 0 <= line.pause_after_ms <= 30_000:
            raise ScriptValidationError(f"{location}.pause_after_ms 必须在 0 到 30000 之间")
        return line


@dataclass(frozen=True)
class AudioSettings:
    sample_rate: int = 32000
    bitrate: int = 128000
    format: str = "mp3"
    channel: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AudioSettings:
        data = data or {}
        if not isinstance(data, dict):
            raise ScriptValidationError("audio 必须是对象")
        settings = cls(
            sample_rate=int(data.get("sample_rate", 32000)),
            bitrate=int(data.get("bitrate", 128000)),
            format=str(data.get("format", "mp3")).lower(),
            channel=int(data.get("channel", 1)),
        )
        if settings.sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise ScriptValidationError("audio.sample_rate 不受 MiniMax 支持")
        if settings.bitrate not in SUPPORTED_BITRATES:
            raise ScriptValidationError("audio.bitrate 不受 MiniMax 支持")
        if settings.format not in SUPPORTED_FORMATS:
            raise ScriptValidationError("audio.format 不受 MiniMax 支持")
        if settings.channel not in {1, 2}:
            raise ScriptValidationError("audio.channel 必须是 1 或 2")
        return settings


@dataclass(frozen=True)
class SoundEffect:
    id: str
    prompt: str
    start_ms: int | None = None
    start_at_line: int | None = None
    offset_ms: int = 0
    duration_seconds: float | None = None
    prompt_influence: float = 0.3
    loop: bool = False
    until_end: bool = False
    volume_db: float = -16.0
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    model_id: str = "eleven_text_to_sound_v2"

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> SoundEffect:
        location = f"sound_effects[{index}]"
        effect = cls(
            id=str(data.get("id", "")).strip(),
            prompt=str(data.get("prompt", "")).strip(),
            start_ms=_optional_int(data.get("start_ms")),
            start_at_line=_optional_int(data.get("start_at_line")),
            offset_ms=int(data.get("offset_ms", 0)),
            duration_seconds=_optional_float(data.get("duration_seconds")),
            prompt_influence=float(data.get("prompt_influence", 0.3)),
            loop=bool(data.get("loop", False)),
            until_end=bool(data.get("until_end", False)),
            volume_db=float(data.get("volume_db", -16)),
            fade_in_ms=int(data.get("fade_in_ms", 0)),
            fade_out_ms=int(data.get("fade_out_ms", 0)),
            model_id=str(data.get("model_id", "eleven_text_to_sound_v2")).strip(),
        )
        effect.validate(location)
        return effect

    def validate(self, location: str) -> None:
        if not self.id:
            raise ScriptValidationError(f"{location}.id 不能为空")
        if not self.prompt:
            raise ScriptValidationError(f"{location}.prompt 不能为空")
        if self.start_ms is not None and self.start_at_line is not None:
            raise ScriptValidationError(f"{location} 不能同时设置 start_ms 和 start_at_line")
        if self.start_ms is not None and self.start_ms < 0:
            raise ScriptValidationError(f"{location}.start_ms 不能小于 0")
        if self.start_at_line is not None and self.start_at_line < 1:
            raise ScriptValidationError(f"{location}.start_at_line 必须从 1 开始")
        if self.duration_seconds is not None and not 0.5 <= self.duration_seconds <= 30:
            raise ScriptValidationError(f"{location}.duration_seconds 必须在 0.5 到 30 之间")
        if not 0 <= self.prompt_influence <= 1:
            raise ScriptValidationError(f"{location}.prompt_influence 必须在 0 到 1 之间")
        if not -60 <= self.volume_db <= 6:
            raise ScriptValidationError(f"{location}.volume_db 必须在 -60 到 6 之间")
        if self.fade_in_ms < 0 or self.fade_out_ms < 0:
            raise ScriptValidationError(f"{location} 的淡入淡出时间不能小于 0")
        if self.until_end and not self.loop:
            raise ScriptValidationError(f"{location}.until_end=true 时必须同时设置 loop=true")
        if not self.model_id:
            raise ScriptValidationError(f"{location}.model_id 不能为空")


@dataclass(frozen=True)
class StoryScript:
    title: str
    model: str
    characters: dict[str, Character]
    lines: tuple[Line, ...]
    audio: AudioSettings = field(default_factory=AudioSettings)
    language_boost: str = "Chinese"
    sound_effects: tuple[SoundEffect, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryScript:
        title = str(data.get("title", "")).strip()
        if not title:
            raise ScriptValidationError("title 不能为空")

        model = str(data.get("model", "speech-2.8-hd"))
        if model not in SUPPORTED_MODELS:
            raise ScriptValidationError("model 必须是 speech-2.8-hd 或 speech-2.8-turbo")

        raw_characters = data.get("characters")
        if not isinstance(raw_characters, dict) or not raw_characters:
            raise ScriptValidationError("characters 必须至少定义一个角色")
        characters = {
            str(key): Character.from_dict(str(key), value)
            for key, value in raw_characters.items()
            if isinstance(value, dict)
        }
        if len(characters) != len(raw_characters):
            raise ScriptValidationError("characters 中的每个角色都必须是对象")

        raw_lines = data.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ScriptValidationError("lines 必须至少包含一句台词")
        if not all(isinstance(item, dict) for item in raw_lines):
            raise ScriptValidationError("lines 中的每句台词都必须是对象")
        lines = tuple(Line.from_dict(item, index) for index, item in enumerate(raw_lines))
        for index, line in enumerate(lines):
            if line.speaker not in characters:
                raise ScriptValidationError(
                    f"lines[{index}].speaker 引用了未定义角色 {line.speaker!r}"
                )
            characters[line.speaker].voice.with_overrides(line).validate(f"lines[{index}]")

        raw_effects = data.get("sound_effects", [])
        if not isinstance(raw_effects, list):
            raise ScriptValidationError("sound_effects 必须是数组")
        if not all(isinstance(item, dict) for item in raw_effects):
            raise ScriptValidationError("sound_effects 中的每个音效都必须是对象")
        sound_effects = tuple(
            SoundEffect.from_dict(item, index) for index, item in enumerate(raw_effects)
        )
        effect_ids = [effect.id for effect in sound_effects]
        if len(set(effect_ids)) != len(effect_ids):
            raise ScriptValidationError("sound_effects.id 不能重复")
        for index, effect in enumerate(sound_effects):
            if effect.start_at_line is not None and effect.start_at_line > len(lines):
                raise ScriptValidationError(
                    f"sound_effects[{index}].start_at_line 超出台词数量"
                )

        return cls(
            title=title,
            model=model,
            characters=characters,
            lines=lines,
            audio=AudioSettings.from_dict(data.get("audio")),
            language_boost=str(data.get("language_boost", "Chinese")),
            sound_effects=sound_effects,
        )

    @classmethod
    def load(cls, path: Path) -> StoryScript:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ScriptValidationError(f"找不到故事脚本: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ScriptValidationError(
                f"故事脚本 JSON 格式错误（第 {exc.lineno} 行，第 {exc.colno} 列）"
            ) from exc
        if not isinstance(data, dict):
            raise ScriptValidationError("故事脚本顶层必须是对象")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
