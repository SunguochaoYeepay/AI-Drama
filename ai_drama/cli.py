from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from ai_drama.audio import AudioToolError
from ai_drama.comfyui import ComfyUIClient, ComfyUIError
from ai_drama.drama_claw import DramaClawClient, DramaClawError
from ai_drama.elevenlabs import ElevenLabsClient, ElevenLabsError
from ai_drama.minimax import DEFAULT_ENDPOINT, MiniMaxClient, MiniMaxError
from ai_drama.models import ScriptValidationError, StoryScript
from ai_drama.pipeline import default_output_dir, generate_elevenlabs_story, generate_story
from ai_drama.video_pipeline import generate_h3_shot, generate_keyframe, load_video_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成带环境音的多角色剧情音频")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="按故事脚本生成逐句音频和完整对话")
    generate.add_argument("script", type=Path, help="故事脚本 JSON 文件")
    generate.add_argument("--output", type=Path, help="输出目录，默认按脚本文件名创建")
    generate.add_argument("--dry-run", action="store_true", help="只检查脚本和生成计划，不调用接口")
    generate.add_argument("--no-merge", action="store_true", help="只生成逐句音频，不合并完整对话")
    generate.add_argument(
        "--speech-provider",
        choices=("minimax", "elevenlabs"),
        default="minimax",
        help="对白生成平台，默认 minimax",
    )
    generate.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help=argparse.SUPPRESS)

    keyframe = subparsers.add_parser("video-keyframe", help="使用 Qwen Image 4 步工作流生成关键帧")
    _add_video_common_arguments(keyframe)
    keyframe.add_argument("keyframe_id", help="视频配置中的 keyframe id")

    h3 = subparsers.add_parser("video-h3", help="使用 MiniMax H3 4 步工作流生成测试镜头")
    _add_video_common_arguments(h3)
    h3.add_argument("shot_id", help="视频配置中的 h3 shot id")
    h3.add_argument("--image", type=Path, required=True, help="H3 使用的首帧图片")

    publish = subparsers.add_parser("publish-canvas", help="把故事、音频、关键帧和视频发布到 DramaClaw 自由画布")
    publish.add_argument("script", type=Path, help="故事脚本 JSON 文件")
    publish.add_argument("video_plan", type=Path, nargs="?", help="视频配置 JSON 文件")
    publish.add_argument("--project", required=True, help="DramaClaw 项目名称或项目 ID")
    publish.add_argument("--canvas", default="ai_drama_assets", help="画布 ID，默认 ai_drama_assets")
    publish.add_argument("--dramaclaws-url", default="http://127.0.0.1:8080", help="DramaClaw 地址")
    publish.add_argument("--output", type=Path, help="生成结果目录，默认 outputs/<脚本名>")
    publish.add_argument("--json", action="store_true", help="以 JSON 输出发布结果")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _load_local_env(Path(".env"))
        if args.command == "publish-canvas":
            client = DramaClawClient(args.dramaclaws_url)
            story = StoryScript.load(args.script)
            project = _resolve_drama_claw_project(client, args.project)
            result = client.publish_story(
                story,
                project_id=str(project["id"]),
                canvas_id=args.canvas,
                script_path=args.script,
                video_plan_path=args.video_plan,
                output_dir=args.output or default_output_dir(args.script),
            )
            if args.json:
                import json

                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"DramaClaw 项目：{project['name']} ({project['id']})")
                print(f"自由画布：{args.canvas}")
                print(f"节点：{len(result['nodes'])}，连线：{len(result['edges'])}，已上传资产：{', '.join(result['assets']) or '无'}")
                from urllib.parse import quote

                project_id = quote(str(project["id"]), safe="")
                canvas_id = quote(args.canvas, safe="")
                print(f"打开地址：{args.dramaclaws_url.rstrip('/')}/projects/{project_id}/freezone?canvas={canvas_id}")
            return 0
        if args.command in {"video-keyframe", "video-h3"}:
            plan = load_video_plan(args.plan)
            output_dir = args.output or Path("outputs") / args.plan.stem / "video"
            comfyui = ComfyUIClient(args.comfyui_url)
            common = {
                "seed": args.seed,
                "validate_nodes": not args.skip_node_validation,
                "timeout": args.timeout,
            }
            if args.command == "video-keyframe":
                generate_keyframe(plan, args.keyframe_id, comfyui, output_dir, **common)
            else:
                generate_h3_shot(plan, args.shot_id, args.image, comfyui, output_dir, **common)
            return 0

        story = StoryScript.load(args.script)
        output_dir = args.output or default_output_dir(args.script, args.speech_provider)
        elevenlabs_key = (
            os.environ.get("ELEVENLABS_API_KEY")
            or os.environ.get("ElevenLabs_API_KEY", "")
        )
        if args.speech_provider == "elevenlabs":
            if args.no_merge:
                raise ValueError("ElevenLabs 多角色对话不支持 --no-merge")
            elevenlabs_client = None
            if not args.dry_run:
                elevenlabs_client = ElevenLabsClient(api_key=elevenlabs_key)
            generate_elevenlabs_story(
                story,
                elevenlabs_client,
                output_dir,
                dry_run=args.dry_run,
            )
        else:
            client = None
            if not args.dry_run:
                client = MiniMaxClient(
                    api_key=os.environ.get("MINIMAX_API_KEY", ""),
                    endpoint=args.endpoint,
                )
            sound_client = None
            if story.sound_effects and not args.dry_run:
                sound_client = ElevenLabsClient(api_key=elevenlabs_key)
            generate_story(
                story,
                client,
                output_dir,
                sound_client=sound_client,
                dry_run=args.dry_run,
                merge=not args.no_merge,
            )
        return 0
    except (
        ScriptValidationError,
        MiniMaxError,
        ElevenLabsError,
        AudioToolError,
        ComfyUIError,
        DramaClawError,
        ValueError,
        OSError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


def _resolve_drama_claw_project(client: DramaClawClient, identifier: str) -> dict[str, object]:
    projects = client.list_projects()
    for project in projects:
        if str(project.get("id")) == identifier or str(project.get("name")) == identifier:
            return project
    return client.get_or_create_project(identifier)


def _load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {
            "MINIMAX_API_KEY",
            "ELEVENLABS_API_KEY",
            "ElevenLabs_API_KEY",
        } or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _add_video_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("plan", type=Path, help="视频阶段 JSON 配置")
    parser.add_argument(
        "--comfyui-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI API 地址，默认 http://127.0.0.1:8188",
    )
    parser.add_argument("--output", type=Path, help="本地输出目录")
    parser.add_argument("--seed", type=int, help="覆盖配置中的随机种")
    parser.add_argument("--timeout", type=float, default=7200, help="等待生成完成的秒数")
    parser.add_argument("--skip-node-validation", action="store_true", help=argparse.SUPPRESS)
