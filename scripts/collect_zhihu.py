#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect verified Zhihu search results through the bundled MediaCrawler."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

TOOLKIT_DIR = Path(__file__).resolve().parent.parent
CRAWLER_DIR = TOOLKIT_DIR / "media-crawler"
CRAWLER_PYTHON = CRAWLER_DIR / ".venv" / "Scripts" / "python.exe"
BRIDGE = TOOLKIT_DIR / "scripts" / "media_crawler_bridge.py"


def latest_content_file() -> Path | None:
    """Return the newest Zhihu content file, never a comment file."""
    data_dir = CRAWLER_DIR / "data" / "zhihu"
    candidates = [
        path for path in data_dir.glob("**/*")
        if path.is_file() and "content" in path.stem.lower()
        and path.suffix.lower() in {".jsonl", ".json", ".csv"}
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def run(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, timeout=timeout)


def main() -> None:
    parser = argparse.ArgumentParser(description="知乎关键词采集（MediaCrawler → 标准 JSON）")
    parser.add_argument("keywords", help="关键词；多个词用英文逗号分隔")
    parser.add_argument("--limit", type=int, default=20, help="最多采集条数，默认 20")
    parser.add_argument("--login", choices=("qrcode", "cookie"), default="cookie", help="登录方式，默认 cookie（CDP 模式下浏览器已登录直接用 cookie；若扫码需手动传 --login qrcode）")
    parser.add_argument("--output", default="zhihu_results.json", help="标准化 JSON 输出文件")
    parser.add_argument("--to-obsidian", action="store_true", help="转换后同步到 Obsidian")
    parser.add_argument("--timeout", type=int, default=90, help="主爬虫最长运行秒数（默认 90）")
    args = parser.parse_args()

    if not CRAWLER_PYTHON.exists():
        raise SystemExit(f"MediaCrawler Python environment not found: {CRAWLER_PYTHON}")

    print(f"[知乎] 采集关键词：{args.keywords}（不抓评论，最长 {args.timeout} 秒）")
    started_at = time.time()
    crawl_completed = False
    try:
        completed = run([
            str(CRAWLER_PYTHON), "main.py", "--platform", "zhihu", "--type", "search",
            "--keywords", args.keywords, "--crawler_max_notes_count", str(args.limit),
            "--lt", args.login, "--save_data_option", "jsonl",
            "--get_comment", "no", "--get_sub_comment", "no",
        ], CRAWLER_DIR, args.timeout)
        crawl_completed = completed.returncode == 0
        if not crawl_completed:
            print(f"[知乎] 主爬虫退出码 {completed.returncode}，检查本轮已写入内容。", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("[知乎] 主爬虫超时，检查本轮已写入内容并尝试桥接。", file=sys.stderr)

    content_file = latest_content_file()
    if not content_file or content_file.stat().st_mtime < started_at:
        if crawl_completed:
            raise SystemExit("知乎主爬虫完成但未找到本轮内容文件")
        raise SystemExit("知乎主爬虫未完成且没有本轮可桥接内容")

    bridge_command = [sys.executable, str(BRIDGE), "--platform", "zhihu", "--input", str(content_file), "--output", args.output]
    if args.to_obsidian:
        bridge_command.append("--to-obsidian")
    bridge_completed = run(bridge_command, TOOLKIT_DIR, 30)
    if bridge_completed.returncode:
        raise SystemExit(bridge_completed.returncode)
    print(f"[完成] 已生成 {TOOLKIT_DIR / args.output}")


if __name__ == "__main__":
    main()
