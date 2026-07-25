#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect verified Zhihu search results through the bundled MediaCrawler."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLKIT_DIR = Path(__file__).resolve().parent.parent
CRAWLER_DIR = TOOLKIT_DIR / "media-crawler"
CRAWLER_PYTHON = CRAWLER_DIR / ".venv" / "Scripts" / "python.exe"
BRIDGE = TOOLKIT_DIR / "scripts" / "media_crawler_bridge.py"


def run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="知乎关键词采集（MediaCrawler → 标准 JSON）")
    parser.add_argument("keywords", help="关键词；多个词用英文逗号分隔")
    parser.add_argument("--limit", type=int, default=20, help="最多采集条数，默认 20")
    parser.add_argument("--login", choices=("qrcode", "cookie"), default="qrcode", help="登录方式，默认二维码")
    parser.add_argument("--output", default="zhihu_results.json", help="标准化 JSON 输出文件")
    parser.add_argument("--to-obsidian", action="store_true", help="转换后同步到 Obsidian")
    args = parser.parse_args()

    if not CRAWLER_PYTHON.exists():
        raise SystemExit(f"MediaCrawler Python environment not found: {CRAWLER_PYTHON}")

    print(f"[知乎] 采集关键词：{args.keywords}")
    run([
        str(CRAWLER_PYTHON), "main.py", "--platform", "zhihu", "--type", "search",
        "--keywords", args.keywords, "--crawler_max_notes_count", str(args.limit),
        "--lt", args.login, "--save_data_option", "jsonl",
    ], CRAWLER_DIR)

    bridge_command = [sys.executable, str(BRIDGE), "--platform", "zhihu", "--auto", "--output", args.output]
    if args.to_obsidian:
        bridge_command.append("--to-obsidian")
    run(bridge_command, TOOLKIT_DIR)
    print(f"[完成] 已生成 {TOOLKIT_DIR / args.output}")


if __name__ == "__main__":
    main()
