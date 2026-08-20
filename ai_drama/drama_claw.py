"""Publish AI Drama artifacts to a DramaClaw Freezone canvas.

The client intentionally uses only Python's standard library so the audio/video
pipeline remains usable on a clean Python 3.11 installation.
"""

from __future__ import annotations

import json
import mimetypes
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from ai_drama.models import StoryScript
from ai_drama.video_pipeline import load_video_plan


class DramaClawError(RuntimeError):
    """Raised when DramaClaw rejects a request or is unreachable."""


class DramaClawClient:
    def __init__(self, base_url: str, *, timeout: float = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def list_projects(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/projects")

    def get_or_create_project(self, name: str) -> dict[str, Any]:
        for project in self.list_projects():
            if project.get("name") == name:
                return project
        return self._request("POST", "/api/v1/projects", {"name": name})

    def upload(self, path: Path, project_id: str) -> dict[str, Any]:
        if not path.is_file():
            raise DramaClawError(f"找不到要上传的文件：{path}")
        boundary = f"----AI-D drama-{secrets.token_hex(12)}"
        body = _multipart_file(boundary, "file", path.name, path.read_bytes())
        request = urllib.request.Request(
            self._url(f"/api/v1/projects/{urllib.parse.quote(project_id, safe='')}/freezone/upload"),
            data=body,
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
            },
        )
        return self._send(request)

    def get_canvas(self, project_id: str, canvas_id: str) -> dict[str, Any]:
        return self._request("GET", self._canvas_path(project_id, canvas_id))

    def list_canvases(self, project_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET", f"/api/v1/projects/{urllib.parse.quote(project_id, safe='')}/freezone/canvases"
        )

    def save_canvas(self, project_id: str, canvas_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", self._canvas_path(project_id, canvas_id), payload)

    def publish_story(
        self,
        story: StoryScript,
        *,
        project_id: str,
        canvas_id: str,
        script_path: Path,
        video_plan_path: Path | None = None,
        output_dir: Path | None = None,
        save_source: str = "import",
    ) -> dict[str, Any]:
        """Upload available artifacts and save a complete, readable canvas."""
        video_plan = load_video_plan(video_plan_path) if video_plan_path else None
        root = output_dir or Path("outputs") / script_path.stem
        assets: dict[str, dict[str, Any]] = {}
        candidates = _artifact_candidates(story, video_plan, root)
        for key, path in candidates.items():
            if path and path.is_file():
                assets[key] = self.upload(path, project_id)

        nodes, edges = build_canvas_nodes(story, video_plan, assets, root)
        current = self.get_canvas(project_id, canvas_id)
        payload = {
            "schema_version": 2,
            "canvas_id": canvas_id,
            "project_id": project_id,
            "nodes": nodes,
            "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 0.72},
            "metadata": {
                "source": "ai-drama",
                "story_file": str(script_path),
                "video_plan_file": str(video_plan_path) if video_plan_path else None,
                "artifact_keys": sorted(assets),
            },
            "base_revision": current.get("revision"),
            "client_save_id": str(uuid.uuid4()),
            "save_source": save_source,
            "allow_empty_overwrite": False,
        }
        result = self.save_canvas(project_id, canvas_id, payload)
        return {"project_id": project_id, "canvas_id": canvas_id, "assets": assets, "nodes": nodes, "edges": edges, "save": result}

    def _canvas_path(self, project_id: str, canvas_id: str) -> str:
        project = urllib.parse.quote(project_id, safe="")
        canvas = urllib.parse.quote(canvas_id, safe="")
        return f"/api/v1/projects/{project}/freezone/canvases/{canvas}"

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        return self._send(urllib.request.Request(self._url(path), data=data, method=method, headers=headers))

    def _send(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            detail = ""
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:1000]
                except OSError:
                    pass
            raise DramaClawError(f"DramaClaw 请求失败：{exc} {detail}".strip()) from exc
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DramaClawError("DramaClaw 返回了无法解析的响应") from exc
        if isinstance(envelope, dict) and envelope.get("ok") is False:
            raise DramaClawError(str(envelope.get("error") or envelope.get("detail") or envelope))
        return envelope.get("data", envelope) if isinstance(envelope, dict) else envelope

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"


def build_canvas_nodes(
    story: StoryScript,
    video_plan: dict[str, Any] | None,
    assets: dict[str, dict[str, Any]],
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build deterministic node IDs so rerunning the command updates one canvas."""
    nodes: list[dict[str, Any]] = []

    def add(node_id: str, node_type: str, x: int, y: int, width: int, height: int, data: dict[str, Any]) -> None:
        nodes.append({"id": node_id, "type": node_type, "position": {"x": x, "y": y}, "width": width, "height": height, "data": data})

    add("story-overview", "textAnnotationNode", 0, 0, 430, 260, {
        "displayName": "项目说明",
        "content": _overview(story, video_plan),
        "mode": "writing",
        "model": "gvlm-3.1",
        "extraParams": {},
        "isGenerating": False,
    })
    rows = _script_rows(story)
    add("story-script", "scriptNode", 0, 310, 700, 620, {
        "displayName": f"{story.title} · 剧本",
        "prompt": story.title,
        "model": "gvlm-3.1",
        "lastAction": None,
        "scriptTitle": story.title,
        "scriptResult": {"title": story.title, "rows": rows},
        "isGenerating": False,
        "generationStartedAt": None,
        "generationDurationMs": 60000,
    })
    audio_url = _asset_url(assets.get("audio"))
    if audio_url:
        audio_path = _artifact_candidates(story, video_plan, root).get("audio")
        add("story-audio", "audioNode", 0, 980, 430, 230, {
            "displayName": "最终剧情音频",
            "audioUrl": audio_url,
            "sourceFileName": audio_path.name if audio_path else "final_mix.mp3",
            "durationMs": _duration_ms(audio_path),
            "isUploading": False,
            "text": "",
            "emotionPrompt": "",
            "voiceLanguage": "Chinese",
            "isGenerating": False,
            "generationStartedAt": None,
        })
    keyframe_keys = [str(item.get("id")) for item in (video_plan or {}).get("keyframes", []) if item.get("id")]
    if not keyframe_keys:
        keyframe_keys = ["character_lineup", "opening_conflict", "argument_peak", "mother_intervenes", "reconciliation"]
    for index, key in enumerate(keyframe_keys):
        url = _asset_url(assets.get(key))
        if not url:
            continue
        path = _artifact_candidates(story, video_plan, root).get(key)
        add(f"keyframe-{key}", "uploadNode", 760 + (index % 2) * 430, 0 + (index // 2) * 310, 380, 260, {
            "displayName": f"关键帧 · {key}", "imageUrl": url, "previewImageUrl": url,
            "aspectRatio": "16:9", "isSizeManuallyAdjusted": False,
            "sourceFileName": path.name if path else f"{key}.png",
        })
    shot_keys = [str(item.get("id")) for item in (video_plan or {}).get("h3_shots", []) if item.get("id")]
    if not shot_keys:
        shot_keys = ["opening_conflict_test"]
    shot_key = next((key for key in shot_keys if assets.get(key)), None)
    video_url = _asset_url(assets.get(shot_key)) if shot_key else None
    if video_url:
        path = _artifact_candidates(story, video_plan, root).get(shot_key)
        shot_config = next((item for item in (video_plan or {}).get("h3_shots", []) if item.get("id") == shot_key), {})
        add("h3-opening-test", "videoNode", 1200, 700, 560, 390, {
            "displayName": f"镜头 01 · MiniMax H3 4 步测试{f' · {shot_key}' if shot_key != 'opening_conflict_test' else ''}",
            "videoUrl": video_url, "previewImageUrl": None, "aspectRatio": "16:9",
            "sourceFileName": path.name if path else "opening_conflict_test.mp4",
            "widthPx": int(shot_config.get("width", 1344)), "heightPx": int(shot_config.get("height", 768)), "durationMs": _duration_ms(path),
            "isUploading": False, "isAnalyzing": False, "analysisResult": None, "analysisError": None,
            "prompt": _shot_prompt(video_plan, shot_key), "genMode": "imageToVideo",
            "model": "minimax_h3", "quality": "720P", "durationSec": round(int(shot_config.get("length", 120)) / int(shot_config.get("fps", 24))), "generateAudio": True,
            "h3Profile": "draft", "count": 1, "isGenerating": False,
        })
    if video_plan:
        add("video-plan", "textAnnotationNode", 760, 980, 760, 310, {
            "displayName": "视频制作计划",
            "content": _video_plan_text(video_plan), "mode": "writing", "model": "gvlm-3.1",
            "extraParams": {}, "isGenerating": False,
        })
    edges = _edges(nodes)
    return nodes, edges


def _artifact_candidates(story: StoryScript, plan: dict[str, Any] | None, root: Path) -> dict[str, Path | None]:
    video_root = root.parent / f"{root.name}_video" / "video"
    candidates: dict[str, Path | None] = {
        "audio": next((root / name for name in ("final_mix_v2.mp3", "final_mix.mp3", "dialogue.mp3") if (root / name).is_file()), None),
        "character_lineup": video_root / "keyframes" / "character_lineup.png",
        "opening_conflict": video_root / "keyframes" / "opening_conflict.png",
        "argument_peak": video_root / "keyframes" / "argument_peak.png",
        "mother_intervenes": video_root / "keyframes" / "mother_intervenes.png",
        "reconciliation": video_root / "keyframes" / "reconciliation.png",
        "opening_conflict_test": video_root / "shots" / "opening_conflict_test.mp4",
    }
    if plan:
        for item in plan.get("keyframes", []):
            key = str(item.get("id", ""))
            if key and candidates.get(key) is None:
                candidates[key] = video_root / "keyframes" / f"{key}.png"
        for item in plan.get("h3_shots", []):
            key = str(item.get("id", ""))
            if key and candidates.get(key) is None:
                candidates[key] = video_root / "shots" / f"{key}.mp4"
    return candidates


def _script_rows(story: StoryScript) -> list[dict[str, Any]]:
    rows = []
    elapsed = 0
    for index, line in enumerate(story.lines, 1):
        duration = max(1, len(line.text) * 220)
        start, end = elapsed, elapsed + duration
        rows.append({
            "shot_number": index, "start_time": _timecode(start), "end_time": _timecode(end),
            "duration": f"{max(1, round(duration / 1000))}s", "visual_description": "根据台词和情绪匹配角色表演",
            "narrative": f"{story.characters[line.speaker].name}：{line.text}", "shot_size": "中景",
            "camera_angle": "平视", "camera_movement": "自然微动", "focal_and_dof": "35mm，中等景深",
            "lighting": "夜晚暖色室内顶灯", "background_music": "N/A",
            "voice_and_sfx": "对白、室内底噪和对应环境音", "image_prompt": "",
            "video_motion_prompt": "保留人物身份，克制自然表演，连续镜头",
        })
        elapsed = end + line.pause_after_ms
    return rows


def _overview(story: StoryScript, plan: dict[str, Any] | None) -> str:
    characters = "、".join(character.name for character in story.characters.values())
    return f"故事：{story.title}\n角色：{characters}\n对白：{len(story.lines)} 句\n环境音：{len(story.sound_effects)} 条\n\n流程：MiniMax Speech 2.8 生成人声 → ElevenLabs 生成环境音 → Qwen 关键帧定人物 → MiniMax H3 4 步测试镜头。\n\n本画布用于集中审核剧本、音频、人物关键帧和视频镜头。"


def _video_plan_text(plan: dict[str, Any]) -> str:
    lines = [f"视频配置：{plan.get('title', '')}", f"视觉风格：{plan.get('visual_style', '')}", "", "关键帧："]
    lines.extend(f"- {item.get('id')}: {item.get('purpose', '')}" for item in plan.get("keyframes", []))
    lines.append("\nH3 镜头：")
    lines.extend(f"- {item.get('id')}（首帧：{item.get('keyframe_id')}，{item.get('length', 0)} 帧，{item.get('steps', 0)} 步）" for item in plan.get("h3_shots", []))
    return "\n".join(lines)


def _shot_prompt(plan: dict[str, Any] | None, shot_id: str) -> str:
    if not plan:
        return ""
    for item in plan.get("h3_shots", []):
        if item.get("id") == shot_id:
            return str(item.get("prompt", ""))
    return ""


def _edges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {node["id"] for node in nodes}
    edges = []
    for source, target in (("story-overview", "story-script"), ("story-script", "story-audio"), ("story-script", "h3-opening-test")):
        if source in ids and target in ids:
            edges.append({"id": f"edge-{source}-{target}", "source": source, "target": target, "type": "default"})
    return edges


def _asset_url(upload: dict[str, Any] | None) -> str | None:
    return str(upload["url"]) if upload and upload.get("url") else None


def _duration_ms(path: Path | None) -> int | None:
    if not path or not path.is_file():
        return None
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
        return round(float(result.stdout.strip()) * 1000)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _timecode(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    return f"{minutes:02d}:{remainder / 1000:05.2f}"


def _multipart_file(boundary: str, field: str, filename: str, contents: bytes) -> bytes:
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    prefix = f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode()
    return prefix + contents + f"\r\n--{boundary}--\r\n".encode()
