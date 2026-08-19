from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ai_drama.comfyui import ComfyUIClient, ComfyUIError, ComfyUIOutput, Progress


ROOT = Path(__file__).resolve().parent.parent
QWEN_WORKFLOW = ROOT / "workflows" / "qwen_image_4step_api.json"
H3_WORKFLOW = ROOT / "workflows" / "minimax_h3_i2v_4step_api.json"


def load_video_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取视频配置：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("视频配置根节点必须是对象")
    for key in ("title", "keyframes", "h3_shots"):
        if not payload.get(key):
            raise ValueError(f"视频配置缺少 {key}")
    _validate_unique_ids(payload["keyframes"], "keyframes")
    _validate_unique_ids(payload["h3_shots"], "h3_shots")
    return payload


def generate_keyframe(
    plan: dict[str, Any],
    keyframe_id: str,
    client: ComfyUIClient,
    output_dir: Path,
    *,
    seed: int | None = None,
    validate_nodes: bool = True,
    timeout: float = 1800,
    progress: Progress = print,
) -> Path:
    item = _find_by_id(plan["keyframes"], keyframe_id)
    width = int(item.get("width", 1344))
    height = int(item.get("height", 768))
    workflow = render_workflow(
        QWEN_WORKFLOW,
        {
            "__PROMPT__": str(item["prompt"]),
            "__SEED__": int(seed if seed is not None else item.get("seed", 1)),
            "__WIDTH__": width,
            "__HEIGHT__": height,
            "__OUTPUT_PREFIX__": f"ai_drama/{_safe_id(plan['title'])}/{keyframe_id}",
        },
    )
    if validate_nodes:
        client.validate_workflow(workflow)
    prompt_id = client.queue_prompt(workflow)
    outputs = client.wait_for_prompt(prompt_id, timeout=timeout, progress=progress)
    image = _first_output(outputs, "image")
    suffix = Path(image.filename).suffix or ".png"
    path = output_dir / "keyframes" / f"{keyframe_id}{suffix}"
    client.download(image, path)
    _write_manifest(output_dir / "keyframes" / f"{keyframe_id}.json", prompt_id, image, path)
    progress(f"关键帧已下载：{path}")
    return path


def generate_h3_shot(
    plan: dict[str, Any],
    shot_id: str,
    image_path: Path,
    client: ComfyUIClient,
    output_dir: Path,
    *,
    seed: int | None = None,
    validate_nodes: bool = True,
    timeout: float = 7200,
    progress: Progress = print,
) -> Path:
    item = _find_by_id(plan["h3_shots"], shot_id)
    uploaded_name = client.upload_image(image_path)
    workflow = render_workflow(
        H3_WORKFLOW,
        {
            "__INPUT_IMAGE__": uploaded_name,
            "__PROMPT__": str(item["prompt"]),
            "__SEED__": int(seed if seed is not None else item.get("seed", 1)),
            "__WIDTH__": int(item.get("width", 1344)),
            "__HEIGHT__": int(item.get("height", 768)),
            "__LENGTH__": int(item.get("length", 124)),
            "__OUTPUT_PREFIX__": f"video/ai_drama/{_safe_id(plan['title'])}/{shot_id}",
        },
    )
    if validate_nodes:
        client.validate_workflow(workflow)
    prompt_id = client.queue_prompt(workflow)
    outputs = client.wait_for_prompt(prompt_id, timeout=timeout, progress=progress)
    video = _first_output(outputs, "video")
    suffix = Path(video.filename).suffix or ".mp4"
    path = output_dir / "shots" / f"{shot_id}{suffix}"
    client.download(video, path)
    _write_manifest(output_dir / "shots" / f"{shot_id}.json", prompt_id, video, path)
    progress(f"H3 测试片已下载：{path}")
    return path


def render_workflow(path: Path, replacements: dict[str, Any]) -> dict[str, Any]:
    try:
        template = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取工作流模板 {path}：{exc}") from exc
    workflow = _replace(copy.deepcopy(template), replacements)
    unresolved = _find_tokens(workflow)
    if unresolved:
        raise ValueError(f"工作流仍有未替换变量：{', '.join(sorted(unresolved))}")
    return workflow


def _replace(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _replace(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item, replacements) for item in value]
    if isinstance(value, str):
        if value in replacements:
            return replacements[value]
        for token, replacement in replacements.items():
            value = value.replace(token, str(replacement))
    return value


def _find_tokens(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_find_tokens(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_find_tokens(item) for item in value), set())
    if isinstance(value, str) and "__" in value:
        return {part for part in value.split() if part.startswith("__") and part.endswith("__")}
    return set()


def _find_by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise ValueError(f"配置中找不到 ID：{item_id}")


def _validate_unique_ids(items: Any, field: str) -> None:
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ValueError(f"{field} 必须是对象数组")
    ids = [item.get("id") for item in items]
    if any(not item_id for item_id in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{field} 中的 id 必须存在且不能重复")


def _first_output(outputs: list[ComfyUIOutput], media_type: str) -> ComfyUIOutput:
    for output in outputs:
        if output.media_type == media_type:
            return output
    raise ComfyUIError(f"ComfyUI 已完成，但没有返回 {media_type} 文件")


def _safe_id(value: str) -> str:
    safe = "".join(character if character.isascii() and character.isalnum() else "_" for character in value)
    return safe.strip("_") or "story"


def _write_manifest(path: Path, prompt_id: str, output: ComfyUIOutput, local_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "prompt_id": prompt_id,
                "remote_output": {
                    "filename": output.filename,
                    "subfolder": output.subfolder,
                    "type": output.type,
                    "media_type": output.media_type,
                },
                "local_file": str(local_path),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
