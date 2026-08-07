#!/usr/bin/env python3
"""生成软著源代码文档 — 前30页 + 后30页"""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent

LINES_PER_PAGE = 50

# 前30页：核心创新代码（入口 + 降级链 + 平台路由 + 飞书模块）
FRONT_FILES = [
    "scripts/collector.py",
    "feishu/client.py",
    "feishu/bitable.py",
    "feishu/schema.py",
]

# 后30页：其余核心代码（采集 + 转录 + 同步 + pipeline + 工具）
BACK_FILES = [
    "scripts/x_capture.py",
    "scripts/transcribe_douyin_fast.py",
    "scripts/transcribe_local.py",
    "scripts/media_crawler_bridge.py",
    "scripts/sync_douyin_to_obsidian.py",
    "scripts/sync-to-feishu.js",
    "scripts/collect_douyin_profile_opencli.py",
    "scripts/download_douyin_tracks.py",
    "pipeline/run.js",
    "pipeline/auto_transcribe.py",
    "utils/gpu_config.py",
    "utils/helpers.py",
]

def generate(section_name, files, max_pages=30):
    """拼接文件，每50行一页"""
    pages = []
    current_page = []
    for fname in files:
        fpath = ROOT / fname
        if not fpath.exists():
            print(f"  WARN: {fname} not found")
            continue
        lines = fpath.read_text(encoding="utf-8", errors="replace").split("\n")
        for line in lines:
            current_page.append(line)
            if len(current_page) >= LINES_PER_PAGE:
                pages.append("\n".join(current_page))
                current_page = []
    if current_page:
        pages.append("\n".join(current_page))

    out_path = OUT / f"源代码_{section_name}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        for i, page in enumerate(pages[:max_pages], 1):
            f.write(f"第 {i} 页\n")
            f.write("-" * 60 + "\n")
            f.write(page)
            f.write("\n\n")
    print(f"✅ {section_name}: {len(pages[:max_pages])} 页 → {out_path}")
    return out_path

if __name__ == "__main__":
    print("生成软著源代码文档...\n")
    generate("前30页", FRONT_FILES, 30)
    generate("后30页", BACK_FILES, 30)
    print("\n完成！")
