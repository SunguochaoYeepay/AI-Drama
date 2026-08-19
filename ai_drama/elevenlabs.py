from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ai_drama.models import SoundEffect


DEFAULT_ENDPOINT = "https://api.elevenlabs.io/v1/sound-generation"


class ElevenLabsError(RuntimeError):
    """Raised when ElevenLabs cannot return a usable sound effect."""


@dataclass(frozen=True)
class SoundEffectResult:
    audio: bytes


Transport = Callable[[Request, float], tuple[int, bytes]]


class ElevenLabsClient:
    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 90,
        max_attempts: int = 3,
        transport: Transport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ElevenLabsError("缺少 ELEVENLABS_API_KEY")
        self.api_key = api_key.strip()
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.transport = transport or _default_transport

    def generate(self, payload: dict[str, Any]) -> SoundEffectResult:
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        for attempt in range(1, self.max_attempts + 1):
            try:
                status, body = self.transport(request, self.timeout)
                if status == 429 or status >= 500:
                    if attempt < self.max_attempts:
                        time.sleep(2 ** (attempt - 1))
                        continue
                if status >= 400:
                    raise ElevenLabsError(_error_message(status, body))
                if not body:
                    raise ElevenLabsError("ElevenLabs 返回成功，但没有音频数据")
                return SoundEffectResult(audio=body)
            except HTTPError as exc:
                body = exc.read()
                retryable = exc.code == 429 or exc.code >= 500
                if retryable and attempt < self.max_attempts:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise ElevenLabsError(_error_message(exc.code, body)) from exc
            except (URLError, TimeoutError) as exc:
                if attempt < self.max_attempts:
                    time.sleep(2 ** (attempt - 1))
                    continue
                reason = getattr(exc, "reason", str(exc))
                raise ElevenLabsError(f"无法连接 ElevenLabs: {reason}") from exc
        raise ElevenLabsError("ElevenLabs 请求失败")


def build_sound_effect_payload(effect: SoundEffect) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": effect.prompt,
        "loop": effect.loop,
        "prompt_influence": effect.prompt_influence,
        "model_id": effect.model_id,
    }
    if effect.duration_seconds is not None:
        payload["duration_seconds"] = effect.duration_seconds
    return payload


def _default_transport(request: Request, timeout: float) -> tuple[int, bytes]:
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def _short_body(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")[:500]


def _error_message(status: int, body: bytes) -> str:
    try:
        response = json.loads(body)
    except json.JSONDecodeError:
        response = None
    if isinstance(response, dict) and isinstance(response.get("detail"), dict):
        detail = response["detail"]
        if detail.get("status") == "missing_permissions":
            return (
                "ElevenLabs API Key 缺少 sound_generation 权限；"
                "请在 ElevenLabs API Key 设置中启用 Sound Generation"
            )
        message = detail.get("message")
        if message:
            return f"ElevenLabs HTTP {status}: {message}"
    return f"ElevenLabs HTTP {status}: {_short_body(body)}"
