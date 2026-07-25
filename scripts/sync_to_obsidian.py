#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准 videos.json → Obsidian 知识库 同步脚本

把信息采集官的标准 videos.json 输出写入 Obsidian 对标账号目录。
每个作品生成一个 Markdown 文件，包含 YAML frontmatter 元数据。

用法:
  python scripts/sync_to_obsidian.py videos.json

  # 指定目录
  python scripts/sync_to_obsidian.py videos.json --obsidian-root "d:/知识库/知识库"

  # 预览模式（不写文件）
  python scripts/sync_to_obsidian.py videos.json --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

TOOLKIT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OBSIDIAN_VAULT = Path("d:/知识库/知识库")
DEFAULT_TARGET_DIR = "05_内容生产库/三金AI实验室_30天万粉作战计划/对标账号"


def load_json(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_filename(name: str) -> str:
    """去除文件名中的非法字符"""
    return name.replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")


def build_frontmatter(video: dict, platform: str) -> str:
    """构建 YAML frontmatter"""
    lines = ["---"]
    lines.append(f"创建日期: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("采集方式: MediaCrawler 批量采集")
    lines.append(f"来源链接: {video.get('videoUrl', '')}")

    # tags
    tags = ["对标作品", platform]
    if video.get("contentType"):
        tags.append(video["contentType"])
    if video.get("title"):
        # 从标题提取关键词作为 tag
        pass
    lines.append("tags:")
    for t in tags:
        lines.append(f"  - {t}")

    lines.append("---")
    return "\n".join(lines)


def build_metadata_table(video: dict, platform: str) -> str:
    """构建视频元数据表格"""
    lines = ["## 作品信息", "", "| 字段 | 值 |", "|:---|:---|"]
    lines.append(f"| 平台 | {platform} |")
    lines.append(f"| 链接 | {video.get('videoUrl', '')} |")

    title = video.get("title", "")
    if title:
        lines.append(f"| 标题 | {title} |")

    likes = video.get("likes", 0)
    if likes:
        lines.append(f"| 点赞 | {likes} |")

    comments = video.get("comments", 0)
    if comments:
        lines.append(f"| 评论 | {comments} |")

    pub_time = video.get("publishTime", "")
    if pub_time:
        lines.append(f"| 发布时间 | {pub_time} |")

    # 知乎特有
    if video.get("contentType"):
        lines.append(f"| 内容类型 | {video['contentType']} |")
    if video.get("desc"):
        lines.append(f"| 描述 | {video['desc']} |")
    if video.get("questionId"):
        lines.append(f"| 问题ID | {video['questionId']} |")

    # 小红书特有
    if video.get("noteType"):
        lines.append(f"| 笔记类型 | {video['noteType']} |")

    lines.append("")
    lines.append("> 📝 待提取逐字稿")
    lines.append("")
    return "\n".join(lines)


def build_title(video: dict, platform: str) -> str:
    """构建笔记标题"""
    title = video.get("title", "") or video.get("videoUrl", "无标题")
    # 截取前 40 字作为文件名
    short_title = sanitize_filename(title)[:40]
    return f"{platform}_{short_title}"


def sync_to_obsidian(videos_json: Path, obsidian_root: Path, dry_run: bool = False, platform_override: str = ""):
    """主同步逻辑"""
    data = load_json(videos_json)
    platform = platform_override or data.get("platform", "unknown")
    videos = data.get("videos", [])

    if not videos:
        print("⚠️ 没有待同步的作品")
        return

    target_dir = obsidian_root / DEFAULT_TARGET_DIR
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Obsidian 目录: {target_dir}")
    print(f"📋 平台: {platform}")
    print(f"📄 共 {len(videos)} 条作品")
    print()

    created = 0
    skipped = 0

    for i, video in enumerate(videos):
        url = video.get("videoUrl", "")
        if not url:
            continue

        # 生成文件名
        title = build_title(video, platform)
        filename = f"{title}.md"
        filepath = target_dir / filename

        # 检查是否已存在（按URL去重）
        if filepath.exists():
            existing = filepath.read_text(encoding="utf-8")
            if url in existing:
                skipped += 1
                print(f"  ⏭ [{i+1}/{len(videos)}] 已存在，跳过: {filename}")
                continue

        # 构建内容
        frontmatter = build_frontmatter(video, platform)
        metadata = build_metadata_table(video, platform)
        content = f"{frontmatter}\n\n# {video.get('title', url)}\n\n{metadata}\n"

        if dry_run:
            print(f"  📝 [{i+1}/{len(videos)}] (预览) {filename}")
        else:
            filepath.write_text(content, encoding="utf-8")
            print(f"  ✅ [{i+1}/{len(videos)}] {filename}")

        created += 1

    print()
    print(f"✨ 完成: {created} 条新建, {skipped} 条跳过")
    if dry_run:
        print("🔍 预览模式 — 未实际写入文件")


def main():
    parser = argparse.ArgumentParser(description="标准 videos.json → Obsidian 知识库")
    parser.add_argument("input", help="标准 videos.json 文件路径")
    parser.add_argument("--obsidian-root", default=str(DEFAULT_OBSIDIAN_VAULT),
                        help=f"Obsidian Vault 根目录 (默认: {DEFAULT_OBSIDIAN_VAULT})")
    parser.add_argument("--platform", "-p",
                        choices=["zhihu", "douyin", "xhs", "bilibili", "kuaishou", "weibo", "tieba", "sph"],
                        help="平台标识（覆盖 JSON 中的 platform 字段）")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览模式，不实际写文件")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = TOOLKIT_DIR / input_path

    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_path}")
        sys.exit(1)

    obsidian_root = Path(args.obsidian_root)
    if not args.dry_run and not obsidian_root.exists():
        print(f"❌ Obsidian Vault 不存在: {obsidian_root}")
        sys.exit(1)

    sync_to_obsidian(input_path, obsidian_root, args.dry_run, args.platform or "")


if __name__ == "__main__":
    main()
