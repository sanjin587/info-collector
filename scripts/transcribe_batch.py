#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量转录桥接 — MediaCrawler 下载的视频 → Whisper 转录 → Obsidian 笔记补全

流程:
  1. 扫描 MediaCrawler 下载的视频目录（data/{platform}/videos/）
  2. 按 videos.json 中的映射找到对应 Obsidian 笔记
  3. 逐条调用 Whisper 转录
  4. 用逐字稿替换 Obsidian 笔记中的「📝 待提取逐字稿」

用法:
  # 基于 bridge 输出文件转录
  python scripts/transcribe_batch.py videos.json

  # 指定转录引擎
  python scripts/transcribe_batch.py videos.json --engine whisper --model medium

  # 只转录最新 N 条
  python scripts/transcribe_batch.py videos.json --limit 5

  # 预览模式
  python scripts/transcribe_batch.py videos.json --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

TOOLKIT_DIR = Path(__file__).resolve().parent.parent
MEDIA_CRAWLER_DIR = TOOLKIT_DIR / "media-crawler"
OBSIDIAN_VAULT = Path("d:/知识库/知识库")
OBSIDIAN_TARGET = "05_内容生产库/三金AI实验室_30天万粉作战计划/对标账号"
TRANSCRIBE_SCRIPT = TOOLKIT_DIR / "scripts" / "transcribe_local.py"

# 各平台在 MediaCrawler 中的视频存储路径
PLATFORM_VIDEO_PATHS = {
    "xhs": "data/xhs/videos",
    "douyin": "data/douyin/videos",
    "bilibili": "data/bili/videos",
    "zhihu": "data/zhihu/videos",
}


def load_json(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_obsidian_notes() -> dict[str, Path]:
    """扫描 Obsidian 对标账号目录，建立 URL → 文件路径 的索引"""
    target = OBSIDIAN_VAULT / OBSIDIAN_TARGET
    if not target.exists():
        print(f"⚠️ Obsidian 目录不存在: {target}")
        return {}

    url_to_path = {}
    for md_file in target.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            # 从 frontmatter 提取来源链接
            m = re.search(r'来源链接:\s*(https?://[^\s\n]+)', content)
            if m:
                url = m.group(1).strip()
                url_to_path[url] = md_file
        except Exception:
            continue

    return url_to_path


def find_video_files(platform: str) -> dict[str, Path]:
    """扫描 MediaCrawler 视频目录，返回 note_id → 视频文件路径 的映射"""
    data_dir = MEDIA_CRAWLER_DIR / PLATFORM_VIDEO_PATHS.get(platform, f"data/{platform}/videos")
    if not data_dir.exists():
        return {}

    video_map = {}
    for note_dir in data_dir.iterdir():
        if not note_dir.is_dir():
            continue
        note_id = note_dir.name
        # 找目录下的 mp4 文件
        mp4_files = sorted(note_dir.glob("*.mp4"))
        if mp4_files:
            video_map[note_id] = mp4_files[0]  # 取第一个视频
    return video_map


def transcribe_video(video_path: Path, engine: str = "whisper", model: str = "medium", lang: str = "zh") -> str | None:
    """调用 transcribe_local.py 转录单个视频，返回逐字稿文本"""
    cmd = [
        sys.executable, str(TRANSCRIBE_SCRIPT),
        str(video_path),
        "--engine", engine,
    ]
    if engine == "whisper":
        cmd += ["--model", model]
    if lang:
        cmd += ["--lang", lang]

    print(f"    🎤 转录中 ({engine}/{model})...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            # 从 stdout 提取转录文本
            return result.stdout.strip()
        else:
            print(f"    ⚠️ 转录失败: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"    ⚠️ 转录超时")
        return None
    except Exception as e:
        print(f"    ⚠️ 转录出错: {e}")
        return None


def update_obsidian_note(note_path: Path, transcript: str, video_url: str) -> bool:
    """将逐字稿写入 Obsidian 笔记，替换占位符"""
    try:
        content = note_path.read_text(encoding="utf-8")

        # 构建逐字稿段落
        transcript_section = f"""---

## 逐字稿

> 转录引擎: Whisper
> 转录时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{transcript}
"""

        # 替换占位符
        if "📝 待提取逐字稿" in content:
            content = content.replace("> 📝 待提取逐字稿", transcript_section)
        elif "## 逐字稿" not in content:
            # 没有占位符也没有逐字稿，追加到末尾
            content += transcript_section

        note_path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"    ⚠️ 写入 Obsidian 失败: {e}")
        return False


def batch_transcribe(videos_json: Path, engine: str = "whisper", model: str = "medium",
                     lang: str = "zh", limit: int = 0, dry_run: bool = False):
    """主批量转录逻辑"""
    data = load_json(videos_json)
    platform = data.get("platform", "unknown")
    videos = data.get("videos", [])

    if not videos:
        print("⚠️ 没有待转录的作品")
        return

    if limit > 0:
        videos = videos[:limit]

    # 建立索引
    obsidian_notes = find_obsidian_notes()
    video_files = find_video_files(platform)

    print(f"📂 平台: {platform}")
    print(f"🎬 本地视频: {len(video_files)} 个")
    print(f"📝 Obsidian 笔记: {len(obsidian_notes)} 篇")
    print(f"📋 待转录: {len(videos)} 条")
    print()

    done = 0
    skipped = 0
    failed = 0

    for i, video in enumerate(videos):
        url = video.get("videoUrl", "")
        title = video.get("title", "无标题")
        note_id = video.get("noteId", "")

        print(f"[{i+1}/{len(videos)}] {title[:50]}")

        # 1. 找到 Obsidian 笔记
        note_path = obsidian_notes.get(url)
        if not note_path:
            print(f"    ⏭ 未找到对应 Obsidian 笔记")
            skipped += 1
            continue

        # 检查是否已转录
        existing = note_path.read_text(encoding="utf-8")
        if "## 逐字稿" in existing and "📝 待提取逐字稿" not in existing:
            print(f"    ⏭ 已有逐字稿")
            skipped += 1
            continue

        # 2. 找到本地视频
        # 先按 note_id 找，再遍历匹配
        video_path = None
        if note_id and note_id in video_files:
            video_path = video_files[note_id]
        else:
            # 遍历找最新或任意的
            for vid in video_files.values():
                video_path = vid
                break

        if not video_path:
            print(f"    ⚠️ 未找到下载的视频文件")
            print(f"    💡 请先在 MediaCrawler 配置中设置 ENABLE_GET_MEIDAS = True")
            failed += 1
            continue

        if dry_run:
            print(f"    📝 (预览) 将转录: {video_path.name}")
            done += 1
            continue

        # 3. 转录
        print(f"    📹 视频: {video_path}")
        transcript = transcribe_video(video_path, engine, model, lang)

        if not transcript:
            failed += 1
            continue

        # 4. 写入 Obsidian
        if update_obsidian_note(note_path, transcript, url):
            print(f"    ✅ 已写入逐字稿")
            done += 1
        else:
            failed += 1

    print()
    print(f"✨ 完成: {done} 条转录, {skipped} 条跳过, {failed} 条失败")
    if dry_run:
        print("🔍 预览模式 — 未实际转录")


def main():
    parser = argparse.ArgumentParser(description="批量转录 — MediaCrawler 视频 → Obsidian 逐字稿")
    parser.add_argument("input", help="bridge 输出的 videos.json 文件路径")
    parser.add_argument("--engine", default="whisper",
                        choices=["whisper", "paraformer"],
                        help="转录引擎 (默认: whisper)")
    parser.add_argument("--model", default="medium",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper 模型大小 (默认: medium)")
    parser.add_argument("--lang", default="zh", help="语言 (默认: zh)")
    parser.add_argument("--limit", type=int, default=0, help="最多转录几条 (0=全部)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = TOOLKIT_DIR / input_path

    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    batch_transcribe(input_path, args.engine, args.model, args.lang, args.limit, args.dry_run)


if __name__ == "__main__":
    main()
