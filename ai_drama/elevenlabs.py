from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ai_drama.models import SoundEffect


DEFAULT_ENDPOINT = "https://api.elevenlabs.io/v1/sound-generation"
DIALOGUE_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-dialogue/with-timestamps"


class ElevenLabsError(RuntimeError):
    """Raised when ElevenLabs cannot return a usable sound effect."""


@dataclass(frozen=True)
class SoundEffectResult:
    audio: bytes


@dataclass(frozen=True)
class DialogueResult:
    audio: bytes
    voice_segments: list[dict[str, Any]]
    alignment: dict[str, Any] | None
    normalized_alignment: dict[str, Any] | None


Transport = Callable[[Request, float], tuple[int, bytes]]


class ElevenLabsClient:
    def __init__(
        self,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        dialogue_endpoint: str = DIALOGUE_ENDPOINT,
        timeout: float = 90,
        max_attempts: int = 3,
        transport: Transport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ElevenLabsError("缺少 ELEVENLABS_API_KEY")
        self.api_key = api_key.strip()
        self.endpoint = endpoint
        self.dialogue_endpoint = dialogue_endpoint
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.transport = transport or _default_transport

    def generate(self, payload: dict[str, Any]) -> SoundEffectResult:
        body = self._post(self.endpoint, payload, "audio/mpeg")
        return SoundEffectResult(audio=body)

    def generate_dialogue(self, payload: dict[str, Any]) -> DialogueResult:
        body = self._post(self.dialogue_endpoint, payload, "application/json")
        try:
            response = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ElevenLabsError("ElevenLabs 对话接口返回了无效 JSON") from exc
        try:
            audio = base64.b64decode(response["audio_base64"], validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise ElevenLabsError("ElevenLabs 对话接口没有返回有效音频") from exc
        voice_segments = response.get("voice_segments")
        if not isinstance(voice_segments, list):
            raise ElevenLabsError("ElevenLabs 对话接口没有返回角色时间戳")
        return DialogueResult(
            audio=audio,
            voice_segments=voice_segments,
            alignment=response.get("alignment"),
            normalized_alignment=response.get("normalized_alignment"),
        )

    def _post(self, endpoint: str, payload: dict[str, Any], accept: str) -> bytes:
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": accept,
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
                return body
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


def build_dialogue_payload(
    inputs: list[dict[str, str]],
    *,
    model_id: str = "eleven_v3",
    language_code: str = "zh",
) -> dict[str, Any]:
    return {
        "inputs": inputs,
        "model_id": model_id,
        "language_code": language_code,
        "apply_text_normalization": "auto",
    }


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
            message = detail.get("message", "缺少所需权限")
            return f"ElevenLabs API Key 权限不足：{message}"
        message = detail.get("message")
        if message:
            return f"ElevenLabs HTTP {status}: {message}"
    return f"ElevenLabs HTTP {status}: {_short_body(body)}"
