from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ai_drama.models import AudioSettings, Voice


DEFAULT_ENDPOINT = "https://api.minimaxi.com/v1/t2a_v2"


class MiniMaxError(RuntimeError):
    """Raised when MiniMax cannot return a usable audio response."""


@dataclass(frozen=True)
class SynthesisResult:
    audio: bytes
    trace_id: str | None
    extra_info: dict[str, Any]


Transport = Callable[[Request, float], tuple[int, bytes]]


class MiniMaxClient:
    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 90,
        max_attempts: int = 3,
        transport: Transport | None = None,
    ) -> None:
        if not api_key.strip():
            raise MiniMaxError("缺少 MINIMAX_API_KEY")
        self.api_key = api_key.strip()
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.transport = transport or _default_transport

    def build_payload(
        self,
        *,
        model: str,
        text: str,
        voice: Voice,
        audio: AudioSettings,
        language_boost: str,
    ) -> dict[str, Any]:
        return build_payload(
            model=model,
            text=text,
            voice=voice,
            audio=audio,
            language_boost=language_boost,
        )

    def synthesize(self, payload: dict[str, Any]) -> SynthesisResult:
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        for attempt in range(1, self.max_attempts + 1):
            try:
                status, body = self.transport(request, self.timeout)
                if status >= 400:
                    raise MiniMaxError(f"MiniMax HTTP {status}: {_short_body(body)}")
                return _parse_response(body)
            except HTTPError as exc:
                body = exc.read()
                retryable = exc.code == 429 or exc.code >= 500
                if retryable and attempt < self.max_attempts:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise MiniMaxError(f"MiniMax HTTP {exc.code}: {_short_body(body)}") from exc
            except (URLError, TimeoutError) as exc:
                if attempt < self.max_attempts:
                    time.sleep(2 ** (attempt - 1))
                    continue
                reason = getattr(exc, "reason", str(exc))
                raise MiniMaxError(f"无法连接 MiniMax: {reason}") from exc
        raise MiniMaxError("MiniMax 请求失败")


def build_payload(
    *,
    model: str,
    text: str,
    voice: Voice,
    audio: AudioSettings,
    language_boost: str,
) -> dict[str, Any]:
    voice_setting = {
        "voice_id": voice.voice_id,
        "speed": voice.speed,
        "vol": voice.vol,
        "pitch": voice.pitch,
        "text_normalization": voice.text_normalization,
    }
    if voice.emotion:
        voice_setting["emotion"] = voice.emotion
    return {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": voice_setting,
        "audio_setting": asdict(audio),
        "language_boost": language_boost,
        "subtitle_enable": False,
        "output_format": "hex",
    }


def save_audio(path: Path, audio: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(audio)
    temporary.replace(path)


def _default_transport(request: Request, timeout: float) -> tuple[int, bytes]:
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def _parse_response(body: bytes) -> SynthesisResult:
    try:
        response = json.loads(body)
    except json.JSONDecodeError as exc:
        raise MiniMaxError(f"MiniMax 返回了无效 JSON: {_short_body(body)}") from exc

    base_response = response.get("base_resp") or {}
    status_code = base_response.get("status_code")
    if status_code != 0:
        message = base_response.get("status_msg", "未知错误")
        raise MiniMaxError(f"MiniMax 生成失败 ({status_code}): {message}")

    data = response.get("data")
    if not isinstance(data, dict) or not data.get("audio"):
        raise MiniMaxError("MiniMax 返回成功，但没有音频数据")
    try:
        audio = bytes.fromhex(data["audio"])
    except (TypeError, ValueError) as exc:
        raise MiniMaxError("MiniMax 返回的音频不是有效的十六进制数据") from exc
    return SynthesisResult(
        audio=audio,
        trace_id=response.get("trace_id"),
        extra_info=response.get("extra_info") or {},
    )


def _short_body(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")[:500]
