#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MediaCrawler 输出 → 信息采集官标准格式 桥接脚本

把 MediaCrawler 的 JSONL/CSV/JSON 输出转换为标准 videos.json，
供 sync-to-feishu.js 直接消费入库。

用法:
  # 知乎搜索结果转换
  python scripts/media_crawler_bridge.py \
    --input media-crawler/Data/ZhiHu/search_xxx.jsonl \
    --platform zhihu \
    --output videos.json

  # 自动扫描 MediaCrawler Data 目录下的最新输出
  python scripts/media_crawler_bridge.py --platform zhihu --auto

  # 列出支持平台
  python scripts/media_crawler_bridge.py --list-platforms

支持的平台:
  zhihu, douyin, xhs, bilibili, kuaishou, weibo, tieba
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

TOOLKIT_DIR = Path(__file__).resolve().parent.parent
MEDIA_CRAWLER_DIR = TOOLKIT_DIR / "media-crawler"
DEFAULT_DATA_DIR = MEDIA_CRAWLER_DIR / "Data"

PLATFORM_MAP = {
    "zhihu": {
        "data_dir": "ZhiHu",
        "platform_name": "知乎",
        "url_field": "content_url",
        "title_field": "title",
        "account_url_field": None,  # 知乎内容不关联固定账号，用 source_keyword
    },
    "douyin": {
        "data_dir": "DouYin",
        "platform_name": "抖音",
        "url_field": "video_url",
        "title_field": "title",
        "account_url_field": "creator_url",
    },
    "xhs": {
        "data_dir": "XiaoHongShu",
        "platform_name": "小红书",
        "url_field": "note_url",
        "title_field": "title",
        "account_url_field": "creator_url",
    },
    "bilibili": {
        "data_dir": "BiliBili",
        "platform_name": "B站",
        "url_field": "video_url",
        "title_field": "title",
        "account_url_field": "creator_url",
    },
    "kuaishou": {
        "data_dir": "KuaiShou",
        "platform_name": "快手",
        "url_field": "video_url",
        "title_field": "title",
        "account_url_field": "creator_url",
    },
    "weibo": {
        "data_dir": "WeiBo",
        "platform_name": "微博",
        "url_field": "note_url",
        "title_field": "content",
        "account_url_field": "creator_url",
    },
    "tieba": {
        "data_dir": "TieBa",
        "platform_name": "贴吧",
        "url_field": "note_url",
        "title_field": "title",
        "account_url_field": None,
    },
}


def find_latest_data(platform: str) -> Path | None:
    """自动找到 MediaCrawler Data 目录下的最新输出文件"""
    plat = PLATFORM_MAP[platform]
    data_dir = DEFAULT_DATA_DIR / plat["data_dir"]

    if not data_dir.exists():
        print(f"⚠️ 数据目录不存在: {data_dir}")
        return None

    # 优先找 jsonl，再 json，再 csv
    for ext in ["jsonl", "json", "csv"]:
        files = sorted(data_dir.glob(f"*.{ext}"), key=os.path.getmtime, reverse=True)
        if files:
            return files[0]

    return None


def parse_jsonl(file_path: Path) -> list[dict]:
    """解析 JSONL 文件"""
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def parse_json(file_path: Path) -> list[dict]:
    """解析 JSON 文件（可能是数组或单个对象）"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return [data]


def parse_csv(file_path: Path) -> list[dict]:
    """解析 CSV 文件"""
    import csv
    records = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    return records


def parse_input(file_path: Path) -> list[dict]:
    """根据扩展名自动选择解析器"""
    ext = file_path.suffix.lower()
    if ext == ".jsonl":
        return parse_jsonl(file_path)
    elif ext == ".json":
        return parse_json(file_path)
    elif ext == ".csv":
        return parse_csv(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def convert_to_standard(records: list[dict], platform: str, account_url: str = "") -> dict:
    """
    将 MediaCrawler 记录转换为信息采集官标准格式

    输出格式:
    {
      "accountUrl": "...",
      "fetchedAt": "2026-07-25T12:00:00",
      "count": N,
      "platform": "zhihu",
      "videos": [
        {"videoUrl": "...", "title": "...", "likes": 0, "comments": 0, "publishTime": ""}
      ]
    }
    """
    plat = PLATFORM_MAP[platform]
    url_field = plat["url_field"]
    title_field = plat["title_field"]

    videos = []
    seen_urls = set()

    for record in records:
        url = record.get(url_field, "")
        if not url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Preserve the generic field names expected by the Feishu synchronizer.
        likes = record.get("voteup_count", 0) or record.get("like_count", 0) or record.get("liked_count", 0)
        comments = record.get("comment_count", 0)
        video = {
            "videoUrl": url,
            "noteId": record.get("note_id", ""),
            "title": record.get(title_field, ""),
            "likeCount": likes,
            "commentCount": comments,
            "likes": likes,
            "comments": comments,
            "publishTime": _format_time(record.get("created_time", 0) or record.get("create_time", 0)),
        }

        # 附加平台特定字段
        if platform == "zhihu":
            video["contentType"] = record.get("content_type", "")  # answer/article/zvideo
            video["questionId"] = record.get("question_id", "")
            video["desc"] = record.get("desc", "")
        elif platform == "xhs":
            video["noteType"] = record.get("note_type", "")
            video["collected_count"] = record.get("collected_count", 0)

        videos.append(video)

    return {
        "accountUrl": account_url or "",
        "fetchedAt": datetime.now().isoformat(),
        "count": len(videos),
        "platform": platform,
        "videos": videos,
    }


def _format_time(ts) -> str:
    """将时间戳转换为可读字符串"""
    if not ts or ts == 0:
        return ""
    try:
        ts = int(ts)
        if ts > 10_000_000_000:  # 毫秒级
            ts = ts // 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return str(ts)


def main():
    parser = argparse.ArgumentParser(description="MediaCrawler → 信息采集官 桥接脚本")
    parser.add_argument("--platform", "-p",
                        choices=list(PLATFORM_MAP.keys()),
                        help="平台标识")
    parser.add_argument("--input", "-i",
                        help="MediaCrawler 输出文件路径（JSONL/JSON/CSV）")
    parser.add_argument("--output", "-o", default="videos.json",
                        help="输出文件路径（默认: videos.json）")
    parser.add_argument("--account-url", "-a", default="",
                        help="关联的账号链接（可选）")
    parser.add_argument("--auto", action="store_true",
                        help="自动扫描 MediaCrawler Data 目录找最新输出")
    parser.add_argument("--list-platforms", action="store_true",
                        help="列出支持平台")
    parser.add_argument("--to-obsidian", action="store_true",
                        help="转换后自动同步到 Obsidian 对标账号目录")

    args = parser.parse_args()

    if args.list_platforms:
        print("支持的平台:")
        for key, info in PLATFORM_MAP.items():
            print(f"  {key:12s} → {info['platform_name']}  (数据目录: {info['data_dir']})")
        return

    if not args.platform:
        print("❌ 请指定 --platform 或使用 --list-platforms 查看支持平台")
        sys.exit(1)

    # 确定输入文件
    if args.auto:
        input_file = find_latest_data(args.platform)
        if input_file is None:
            print(f"❌ 未找到 {PLATFORM_MAP[args.platform]['platform_name']} 的采集数据")
            print(f"   请先运行 MediaCrawler 采集: cd media-crawler && uv run main.py --platform {args.platform} --type search --keywords \"关键词\"")
            sys.exit(1)
        print(f"🔍 自动选择最新数据: {input_file}")
    elif args.input:
        input_file = Path(args.input)
        if not input_file.exists():
            print(f"❌ 输入文件不存在: {input_file}")
            sys.exit(1)
    else:
        print("❌ 请指定 --input <文件> 或使用 --auto 自动寻找")
        sys.exit(1)

    # 解析
    print(f"📄 解析文件: {input_file}")
    records = parse_input(input_file)
    print(f"   共 {len(records)} 条原始记录")

    # 转换
    result = convert_to_standard(records, args.platform, args.account_url)
    print(f"✨ 转换完成: {result['count']} 条有效记录 → {args.output}")

    # 输出
    output_path = args.output
    if not Path(output_path).is_absolute():
        output_path = str(TOOLKIT_DIR / output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 已保存到: {output_path}")
    print()
    print(f"📌 下一步: node scripts/sync-to-feishu.js --account-file={output_path}")

    # 自动同步到 Obsidian
    if args.to_obsidian:
        from subprocess import run as sub_run
        obsidian_script = str(TOOLKIT_DIR / "scripts" / "sync_to_obsidian.py")
        print()
        print("🔄 同步到 Obsidian...")
        result = sub_run(
            [sys.executable, obsidian_script, output_path],
            capture_output=False
        )
        if result.returncode == 0:
            print(f"✅ Obsidian 同步完成")
        else:
            print(f"⚠️ Obsidian 同步出错 (exit code: {result.returncode})")


if __name__ == "__main__":
    main()
