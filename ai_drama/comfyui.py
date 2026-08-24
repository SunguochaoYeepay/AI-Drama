from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid


class ComfyUIError(RuntimeError):
    pass


@dataclass(frozen=True)
class ComfyUIOutput:
    filename: str
    subfolder: str = ""
    type: str = "output"
    media_type: str = "file"


Progress = Callable[[str], None]


class ComfyUIClient:
    def __init__(self, base_url: str, *, timeout: float = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def object_info(self) -> dict[str, Any]:
        return self._request_json("GET", "/object_info")

    def validate_workflow(self, workflow: dict[str, Any]) -> None:
        object_info = self.object_info()
        missing = sorted(
            {
                str(node.get("class_type"))
                for node in workflow.values()
                if node.get("class_type") not in object_info
            }
        )
        if missing:
            raise ComfyUIError(f"ComfyUI 缺少工作流节点：{', '.join(missing)}")

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        response = self._request_json(
            "POST",
            "/prompt",
            {"prompt": workflow, "client_id": str(uuid.uuid4())},
        )
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            error = response.get("error") or response
            raise ComfyUIError(f"ComfyUI 未返回 prompt_id：{error}")
        return str(prompt_id)

    def wait_for_prompt(
        self,
        prompt_id: str,
        *,
        timeout: float = 3600,
        poll_interval: float = 3,
        progress: Progress = print,
    ) -> list[ComfyUIOutput]:
        deadline = time.monotonic() + timeout
        announced = False
        while time.monotonic() < deadline:
            history = self._request_json("GET", f"/history/{prompt_id}")
            record = history.get(prompt_id)
            if record:
                status = record.get("status") or {}
                if status.get("status_str") == "error":
                    messages = status.get("messages") or []
                    raise ComfyUIError(f"ComfyUI 生成失败：{messages[-1] if messages else status}")
                outputs = _collect_outputs(record.get("outputs") or {})
                if outputs:
                    return outputs
            if not announced:
                progress(f"ComfyUI 已排队：{prompt_id}")
                announced = True
            time.sleep(poll_interval)
        raise ComfyUIError(f"等待 ComfyUI 超时：{prompt_id}")

    def upload_image(self, image_path: Path, *, overwrite: bool = True) -> str:
        boundary = f"----AIDrama{uuid.uuid4().hex}"
        fields = {"type": "input", "overwrite": str(overwrite).lower()}
        body = bytearray()
        for name, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(str(value).encode())
            body.extend(b"\r\n")
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="image"; '
                f'filename="{image_path.name}"\r\n'
            ).encode()
        )
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(image_path.read_bytes())
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        response = self._request_json(
            "POST",
            "/upload/image",
            bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        name = response.get("name")
        if not name:
            raise ComfyUIError(f"ComfyUI 上传图片失败：{response}")
        subfolder = str(response.get("subfolder") or "").strip("/\\")
        return f"{subfolder}/{name}" if subfolder else str(name)

    def download(self, output: ComfyUIOutput, destination: Path) -> Path:
        query = urlencode(
            {
                "filename": output.filename,
                "subfolder": output.subfolder,
                "type": output.type,
            }
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self._request_bytes("GET", f"/view?{query}"))
        return destination

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | bytes | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = dict(headers or {})
        data: bytes | None
        if isinstance(payload, dict):
            data = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        else:
            data = payload
        raw = self._request_bytes(method, path, data=data, headers=request_headers)
        try:
            decoded = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ComfyUIError(f"ComfyUI 返回了无效 JSON：{path}") from exc
        if not isinstance(decoded, dict):
            raise ComfyUIError(f"ComfyUI 返回格式异常：{path}")
        return decoded

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers or {},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ComfyUIError(f"ComfyUI HTTP {exc.code}：{detail[:1200]}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ComfyUIError(f"无法连接 ComfyUI：{exc}") from exc


def _collect_outputs(outputs: dict[str, Any]) -> list[ComfyUIOutput]:
    found: list[ComfyUIOutput] = []
    keys = (("images", "image"), ("videos", "video"), ("audio", "audio"), ("gifs", "video"))
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for key, media_type in keys:
            values = node_output.get(key) or []
            if isinstance(values, dict):
                values = [values]
            for value in values:
                if not isinstance(value, dict) or not value.get("filename"):
                    continue
                resolved_media_type = _media_type_from_filename(str(value["filename"]), media_type)
                found.append(
                    ComfyUIOutput(
                        filename=str(value["filename"]),
                        subfolder=str(value.get("subfolder") or ""),
                        type=str(value.get("type") or "output"),
                        media_type=resolved_media_type,
                    )
                )
    return found


def _media_type_from_filename(filename: str, fallback: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".mp4", ".webm", ".mov", ".mkv", ".gif"}:
        return "video"
    if suffix in {".mp3", ".wav", ".flac", ".m4a", ".ogg"}:
        return "audio"
    return fallback
