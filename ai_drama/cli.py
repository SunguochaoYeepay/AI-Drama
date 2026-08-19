from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from ai_drama.audio import AudioToolError
from ai_drama.elevenlabs import ElevenLabsClient, ElevenLabsError
from ai_drama.minimax import DEFAULT_ENDPOINT, MiniMaxClient, MiniMaxError
from ai_drama.models import ScriptValidationError, StoryScript
from ai_drama.pipeline import default_output_dir, generate_elevenlabs_story, generate_story


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _load_local_env(Path(".env"))
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
        ValueError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


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
