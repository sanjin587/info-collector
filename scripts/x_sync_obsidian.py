#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X/Twitter 采集结果 → Obsidian 同步脚本

把 x_capture.py 的输出目录同步到 Obsidian 对标账号 X平台 目录。

用法:
  python scripts/x_sync_obsidian.py downloads/2082494156987871642
  python scripts/x_sync_obsidian.py downloads/2082494156987871642 --dry-run
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

TOOLKIT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OBSIDIAN_VAULT = Path("d:/知识库/知识库")
DEFAULT_TARGET_DIR = "05_内容生产库/三金AI实验室_30天万粉作战计划/对标账号/X平台"


def sync_to_obsidian(capture_dir: Path, obsidian_root: Path, dry_run: bool = False):
    """同步采集结果到 Obsidian"""
    tweet_json = capture_dir / "tweet_data.json"
    article_md = capture_dir / "article.md"

    if not tweet_json.exists():
        print(f"❌ 找不到 tweet_data.json: {tweet_json}")
        sys.exit(1)
    if not article_md.exists():
        print(f"❌ 找不到 article.md: {article_md}")
        sys.exit(1)

    with open(tweet_json, "r", encoding="utf-8") as f:
        tweet = json.load(f)

    tweet_id = tweet.get("id", capture_dir.name)
    author = tweet.get("author", {})
    screen_name = author.get("screen_name", "unknown")
    created_ts = tweet.get("created_timestamp", 0)

    # 目标目录: Obsidian/对标账号/X平台/@{screen_name}/
    target_dir = obsidian_root / DEFAULT_TARGET_DIR / f"@{screen_name}"
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Obsidian 目录: {target_dir}")
    print(f"👤 作者: @{screen_name}")
    print(f"🆔 推文: {tweet_id}")
    print()

    # 1. 复制 article.md（重命名为推文ID + 日期）
    try:
        ts = int(created_ts)
        date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        date_str = "unknown"

    md_dest_name = f"{date_str}_{tweet_id}.md"
    md_dest = target_dir / md_dest_name

    if dry_run:
        print(f"  📝 (预览) {md_dest_name}")
    else:
        shutil.copy2(article_md, md_dest)
        print(f"  ✅ {md_dest_name}")

    # 2. 复制媒体文件到 media/ 子目录
    media_dir = target_dir / "media" / tweet_id
    media_copied = 0
    for f in capture_dir.iterdir():
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4"):
            if dry_run:
                print(f"  🖼 (预览) media/{tweet_id}/{f.name}")
            else:
                media_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, media_dir / f.name)
            media_copied += 1

    # 3. 复制校验文件
    for check_file in ("checksums.sha256", "ffprobe_report.json"):
        src = capture_dir / check_file
        if src.exists():
            if dry_run:
                print(f"  🔐 (预览) media/{tweet_id}/{check_file}")
            else:
                shutil.copy2(src, media_dir / check_file)

    print()
    if dry_run:
        print(f"🔍 预览完成（未实际写入）: 1 md, {media_copied} 媒体")
    else:
        print(f"✨ 同步完成: 1 md, {media_copied} 媒体 → {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="X采集 → Obsidian 同步")
    parser.add_argument("capture_dir", help="x_capture.py 输出目录")
    parser.add_argument("--obsidian-root", default=str(DEFAULT_OBSIDIAN_VAULT),
                        help=f"Obsidian Vault 根目录 (默认: {DEFAULT_OBSIDIAN_VAULT})")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    capture_dir = Path(args.capture_dir)
    if not capture_dir.is_absolute():
        capture_dir = TOOLKIT_DIR / capture_dir
    if not capture_dir.exists():
        print(f"❌ 目录不存在: {capture_dir}")
        sys.exit(1)

    obsidian_root = Path(args.obsidian_root)
    if not args.dry_run and not obsidian_root.exists():
        print(f"❌ Obsidian Vault 不存在: {obsidian_root}")
        sys.exit(1)

    sync_to_obsidian(capture_dir, obsidian_root, args.dry_run)


if __name__ == "__main__":
    main()
