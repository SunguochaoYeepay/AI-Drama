#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ENDPOINT = "https://api.minimaxi.com/v1/get_voice"


def main() -> int:
    parser = argparse.ArgumentParser(description="List MiniMax system voices safely")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="path to the local env file")
    parser.add_argument("--match", help="case-insensitive regex applied to ID, name, and description")
    args = parser.parse_args()

    _load_api_key(args.env)
    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("Missing MINIMAX_API_KEY", file=sys.stderr)
        return 1

    request = Request(
        ENDPOINT,
        data=b'{"voice_type":"system"}',
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        print(f"MiniMax returned HTTP {exc.code}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Unable to query MiniMax voices: {exc}", file=sys.stderr)
        return 1

    base_response = payload.get("base_resp") or {}
    if base_response.get("status_code") != 0:
        print(
            f"MiniMax error: {base_response.get('status_msg', 'unknown error')}",
            file=sys.stderr,
        )
        return 1

    pattern = re.compile(args.match, re.IGNORECASE) if args.match else None
    for voice in payload.get("system_voice") or []:
        voice_id = str(voice.get("voice_id", ""))
        name = str(voice.get("voice_name", ""))
        description = "；".join(str(item) for item in voice.get("description") or [])
        searchable = "\t".join((voice_id, name, description))
        if pattern and not pattern.search(searchable):
            continue
        print(searchable)
    return 0


def _load_api_key(path: Path) -> None:
    if "MINIMAX_API_KEY" in os.environ or not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "MINIMAX_API_KEY":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ["MINIMAX_API_KEY"] = value
        return


if __name__ == "__main__":
    raise SystemExit(main())
