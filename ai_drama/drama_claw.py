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
    rows = _script_rows(story, video_plan, assets)
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


def _script_rows(
    story: StoryScript,
    video_plan: dict[str, Any] | None = None,
    assets: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    assets = assets or {}
    character_descriptions = _character_descriptions(story, video_plan)
    lineup_url = _asset_url(assets.get("character_lineup"))
    keyframes = [item for item in (video_plan or {}).get("keyframes", []) if item.get("id")]
    rows = []
    elapsed = 0
    for index, line in enumerate(story.lines, 1):
        duration = max(2, round(len(line.text) * 0.22))
        start, end = elapsed, elapsed + duration
        speaker = story.characters[line.speaker]
        speaker_name = speaker.name
        other = _other_speaker(story, index - 1, line.speaker)
        other_name = story.characters[other].name if other else ""
        emotion = line.emotion or speaker.voice.emotion or "自然"
        reference_url = _reference_for_line(index - 1, len(story.lines), keyframes, assets)
        scene = _scene_description(video_plan)
        action = _action_for_line(line.text, line.speaker, emotion, index, len(story.lines))
        shot = _shot_for_line(line.text, index, len(story.lines))
        sound = _sound_for_line(story, index, line.text)
        character_1_desc = character_descriptions.get(line.speaker, f"{speaker_name}，保持既定年龄、发型与服装")
        character_2_desc = character_descriptions.get(other, "") if other else ""
        visual = f"{scene}。{speaker_name}{action}"
        if other_name:
            visual += f"，与{other_name}保持清晰的视线和空间关系"
        shot_prompt = (
            f"写实中国家庭短剧，{shot}，{scene}。{speaker_name}（{character_1_desc}）{action}。"
            f"{('画面同时包含' + other_name + '（' + character_2_desc + '）。') if other_name else ''}"
            f"{emotion}，真实皮肤纹理，低饱和生活化布景，人物身份和服装连续，无字幕无文字无水印。"
        )
        motion_prompt = (
            f"镜头{shot}，镜头轻微{_camera_move_for_line(index, emotion)}；{speaker_name}{action}，"
            f"表演{emotion}但克制自然，保持人物面孔、服装和场景连续；{('不要遮挡' + other_name + '的脸。') if other_name else '保留环境空间关系。'}"
        )
        rows.append({
            # Keys match DramaClaw's ScriptNode table. The *_1 aliases keep the
            # payload compatible with the backend story-script schema as well.
            "shot_no": index,
            "shot_number": index,
            "start_time": _timecode(start * 1000),
            "end_time": _timecode(end * 1000),
            "duration": duration,
            "visual_description": visual,
            "character": speaker_name,
            "character_1": speaker_name,
            "character_desc_1": character_1_desc,
            "character_description_1": character_1_desc,
            "character_image_1": lineup_url or "",
            "character_2": other_name,
            "character_desc_2": character_2_desc,
            "character_description_2": character_2_desc,
            "character_image_2": lineup_url or "",
            "reference": reference_url or "",
            "shot": shot,
            "shot_size": shot,
            "action": action,
            "character_action": action,
            "emotion": emotion,
            "scene_tags": "夜晚公寓、客餐厅、家庭关系、连续性场景",
            "lighting_mood": "暖色顶灯，低饱和，冲突时阴影略加深",
            "lighting": "暖色顶灯，低饱和，冲突时阴影略加深",
            "sound": sound,
            "voice_and_sfx": sound,
            "dialogue": f"{speaker_name}：{line.text}",
            "shot_prompt": shot_prompt,
            "image_prompt": shot_prompt,
            "video_motion_prompt": motion_prompt,
        })
        elapsed = end + round(line.pause_after_ms / 1000)
    return rows


def _character_descriptions(story: StoryScript, plan: dict[str, Any] | None) -> dict[str, str]:
    plan_characters = (plan or {}).get("characters", {})
    aliases = {
        "narrator": ("narrator", "旁白"),
        "husband": ("chen_hao", "丈夫", "陈浩"),
        "wife": ("lin_yue", "妻子", "林悦", "林月"),
        "child": ("xiaoyu", "儿子", "小宇"),
        "mother": ("mother_in_law", "婆婆", "岳母"),
    }
    descriptions: dict[str, str] = {}
    for key, character in story.characters.items():
        name = character.name
        tokens = (name, *aliases.get(key, (key,)))
        matches = [
            str(value)
            for plan_key, value in plan_characters.items()
            if any(token and (token in str(value) or token in str(plan_key)) for token in tokens)
        ]
        descriptions[key] = matches[0] if matches else f"{name}，普通中国家庭自然长相，服装和年龄保持连续"
    return descriptions


def _other_speaker(story: StoryScript, index: int, speaker: str) -> str | None:
    for line in story.lines[index + 1 :]:
        if line.speaker != speaker:
            return line.speaker
    for line in reversed(story.lines[:index]):
        if line.speaker != speaker:
            return line.speaker
    return None


def _scene_description(plan: dict[str, Any] | None) -> str:
    location = str((plan or {}).get("location", "夜晚普通中国家庭客餐厅"))
    return location.rstrip("。")


def _reference_for_line(index: int, total: int, keyframes: list[dict[str, Any]], assets: dict[str, dict[str, Any]]) -> str:
    if not keyframes:
        return _asset_url(assets.get("opening_conflict")) or _asset_url(assets.get("character_lineup")) or ""
    if index < max(1, total // 5):
        preferred = "character_lineup"
    elif index < total // 2:
        preferred = "opening_conflict"
    elif index < total * 3 // 4:
        preferred = "argument_peak"
    elif index < total * 9 // 10:
        preferred = "mother_intervenes"
    else:
        preferred = "reconciliation"
    return _asset_url(assets.get(preferred)) or _asset_url(assets.get(str(keyframes[min(index, len(keyframes) - 1)].get("id")))) or ""


def _action_for_line(text: str, speaker: str, emotion: str, index: int, total: int) -> str:
    if "哭" in text or "害怕" in text:
        return "眼含泪水，肩膀收紧，声音发抖"
    if "对不起" in text or "抱" in text:
        return "放下防备，身体微微前倾，试图安抚对方"
    if speaker == "narrator":
        return "以旁白视角交代现场，画面关注正在发生的动作"
    if emotion in {"angry", "生气", "愤怒"}:
        return "身体前倾，手势克制但有力度，直视对方"
    if emotion in {"sad", "悲伤"}:
        return "停顿后低头或移开视线，手指无意识地摩挲衣角"
    if emotion in {"surprised", "惊讶"}:
        return "动作停住，抬眼确认信息，表情短暂失控"
    if index >= total - 4:
        return "语气放缓，与家人交换眼神，逐渐恢复平静"
    return "保持生活化动作，根据对白自然转身、停顿或看向对方"


def _shot_for_line(text: str, index: int, total: int) -> str:
    if "哭" in text or "害怕" in text:
        return "近景"
    if index == 1 or index >= total - 2:
        return "中远景"
    if "你" in text or "妈" in text:
        return "双人中景"
    return "中景"


def _sound_for_line(story: StoryScript, index: int, text: str) -> str:
    effects = [effect.prompt for effect in story.sound_effects if effect.start_at_line == index or effect.start_at_line == index + 1]
    effect_text = "；".join(effects[:2])
    return f"对白清晰；室内底噪、衣料和餐桌细微声{('；' + effect_text) if effect_text else ''}"


def _camera_move_for_line(index: int, emotion: str) -> str:
    if emotion in {"angry", "愤怒"}:
        return "缓慢推近"
    if emotion in {"sad", "悲伤", "fearful"}:
        return "轻微下摇"
    return "平稳横移"


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
