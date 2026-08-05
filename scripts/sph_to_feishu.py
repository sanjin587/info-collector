#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频号视频文案抓取 & 飞书入库 & Obsidian 归档

用法:
  # 单条采集
  python sph_to_feishu.py AH9KmByTvv
  python sph_to_feishu.py "https://weixin.qq.com/sph/AH9KmByTvv"

  # 单条 + 输出标准格式
  python sph_to_feishu.py AH9KmByTvv --output sph_videos.json

  # 单条 + 自动写入 Obsidian
  python sph_to_feishu.py AH9KmByTvv --to-obsidian

  # 批量（多个 ID）
  python sph_to_feishu.py --batch id1 id2 id3 --output sph_batch.json --to-obsidian
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from feishu.client import FeishuClient
from feishu.bitable import BitableManager

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN")


def fetch_sph_video(sph_id: str) -> dict:
    """通过微信视频号 API 获取视频信息"""
    rid = format(int(time.time()*1000), 'x') + '-' + format(int(time.time()*1000000), 'x')[:8]
    url = f'https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info?_rid={rid}&_pageUrl=https://channels.weixin.qq.com/finder-preview/pages/sph'

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Referer': f'https://channels.weixin.qq.com/finder-preview/pages/sph?id={sph_id}',
        'Origin': 'https://channels.weixin.qq.com',
    }

    body = json.dumps({
        'baseReq': {'generalToken': ''},
        'shortUri': sph_id
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode('utf-8'))

    if result.get('errCode') != 0:
        raise RuntimeError(f"API error: {result.get('errMsg', '')}")

    data = result['data']
    fi = data['feedInfo']
    ai = data['authorInfo']

    return {
        "author_name": ai.get('nickname', ''),
        "author_avatar": ai.get('headImgUrl', ''),
        "description": fi.get('description', ''),
        "cover_url": fi.get('coverUrl', ''),
        "like_count": int(fi.get('likeCountFmt', 0)),
        "comment_count": int(fi.get('commentCountFmt', 0)),
        "fav_count": int(fi.get('favCountFmt', 0)),
        "forward_count": int(fi.get('forwardCountFmt', 0)),
        "create_time": fi.get('createtime', 0),
    }


def download_sph_video(sph_id: str, output_dir: str = None) -> str | None:
    """通过 Playwright 拦截视频号页面，获取视频地址并下载

    Returns:
        下载后的视频文件路径，失败返回 None
    """
    if not output_dir:
        output_dir = str(BASE_DIR / "downloads" / "sph")
    os.makedirs(output_dir, exist_ok=True)

    preview_url = f'https://channels.weixin.qq.com/finder-preview/pages/sph?id={sph_id}'

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ 需要安装 playwright: pip install playwright && playwright install chromium")
        return None

    video_url = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36'
        )

        # 拦截视频 URL（区分封面图和视频：封面图 Content-Type 是 image/*，视频是 video/*）
        captured_videos = []
        captured_images = []
        def on_response(response):
            url = response.url
            if 'finder.video.qq.com' not in url:
                return
            content_type = response.headers.get('content-type', '')
            if 'stodownload' in url or '.mp4' in url:
                if 'video/' in content_type:
                    captured_videos.append(url)
                elif 'image/' in content_type:
                    captured_images.append(url)
                else:
                    # content-type 未知时，先记下来
                    captured_videos.append(url)

        page.on('response', on_response)

        page.goto(preview_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(8000)

        browser.close()

        if captured_videos:
            video_url = captured_videos[0]
        else:
            print(f"  🔍 调试: 图片 {len(captured_images)} 个, 视频 0 个")

    if not video_url:
        print(f"  ⚠️ 未捕获到视频地址")
        return None

    # 下载视频
    output_path = os.path.join(output_dir, f"{sph_id}.mp4")
    print(f"  📥 下载视频: {video_url[:80]}...")

    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
            'Referer': f'https://channels.weixin.qq.com/finder-preview/pages/sph?id={sph_id}',
        }
        resp = requests.get(video_url, headers=headers, stream=True, timeout=120)
        total = int(resp.headers.get('content-length', 0))
        downloaded = 0
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    if pct % 20 < 5 and downloaded - len(chunk) <= pct * total // 100 * 8192 < downloaded:
                        print(f"    {pct}% ({downloaded//1024//1024}MB / {total//1024//1024}MB)")
        file_size = os.path.getsize(output_path)
        if file_size < 1024:
            os.remove(output_path)
            print(f"  ⚠️ 下载文件过小 ({file_size}B)，可能失败")
            return None
        print(f"  ✅ 下载完成: {output_path} ({file_size//1024//1024}MB)")
        return output_path
    except Exception as e:
        print(f"  ⚠️ 下载失败: {e}")
        return None


def format_for_feishu(video: dict, sph_url: str) -> dict:
    """格式化为飞书字段"""
    desc = video.get("description", "")
    title = desc.split("\n")[0].split("#")[0].strip()[:100] or "视频号视频"

    keywords = [t.strip() for t in desc.split("#")[1:] if t.strip() and len(t.strip()) < 20]
    publish_ts = int(video.get("create_time", 0)) * 1000 if video.get("create_time") else 0

    likes = video["like_count"]
    comments = video["comment_count"]
    favs = video["fav_count"]
    total = likes + comments + favs
    score = likes + favs * 3 + comments * 2
    now_ts = int(datetime.now().timestamp() * 1000)

    fields = {
        "标题": title,
        "平台": "视频号",
        "作者": video["author_name"],
        "笔记链接": {"link": sph_url, "text": title},
        "发布时间": publish_ts or now_ts,
        "内容摘要": desc[:500] or "",
        "关键词": keywords or "",
        "点赞数": likes,
        "收藏数": favs,
        "评论数": comments,
        "互动总量": total,
        "爆款指数": score,
        "采集时间": now_ts,
        "状态": "待分析",
    }
    return {k: v for k, v in fields.items() if v != "" and v != [] and v != 0}


def format_for_json(video: dict, sph_url: str, sph_id: str) -> dict:
    """格式化为标准 videos.json 条目"""
    desc = video.get("description", "")
    title = desc.split("\n")[0].split("#")[0].strip()[:100] or "视频号视频"
    pub_ts = video.get("create_time", 0)

    return {
        "videoUrl": sph_url,
        "noteId": sph_id,
        "title": title,
        "description": desc,
        "likes": video["like_count"],
        "comments": video["comment_count"],
        "favorites": video["fav_count"],
        "forwards": video["forward_count"],
        "author": video["author_name"],
        "coverUrl": video["cover_url"],
        "publishTime": datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d %H:%M") if pub_ts else "",
    }


def write_to_feishu(video: dict, sph_url: str) -> bool:
    """写入飞书文章采集表"""
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN]):
        print("  ⚠️ 飞书未配置，跳过")
        return False

    try:
        client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
        bitable = BitableManager(client, FEISHU_APP_TOKEN)
        bitable.ensure_tables()

        existing = bitable.get_existing_urls("文章采集")
        if sph_url in existing:
            print(f"  ⏭ 飞书: 已存在")
            return True

        fields = format_for_feishu(video, sph_url)
        record_id = bitable.create_record("文章采集", fields)
        if record_id:
            print(f"  ✅ 飞书: 写入成功")
            return True
        else:
            print(f"  ⚠️ 飞书: 写入失败")
            return False
    except Exception as e:
        print(f"  ⚠️ 飞书: {e}")
        return False


def parse_sph_input(raw: str) -> str:
    """解析输入，提取 sph ID"""
    if "sph/" in raw:
        return raw.split("sph/")[-1].split("?")[0]
    return raw.strip()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="视频号视频抓取 → 飞书 + Obsidian")
    parser.add_argument("inputs", nargs="*", help="sph 链接或 ID（可多个）")
    parser.add_argument("--batch", nargs="+", help="批量 ID 列表")
    parser.add_argument("--output", "-o", default="", help="输出标准 videos.json 路径")
    parser.add_argument("--to-obsidian", action="store_true", help="自动同步到 Obsidian")
    parser.add_argument("--download", action="store_true", help="下载视频到本地")
    parser.add_argument("--download-dir", default="", help="视频下载目录 (默认: downloads/sph)")
    parser.add_argument("--no-feishu", action="store_true", help="跳过飞书入库")
    args = parser.parse_args()

    # 合并输入
    ids_raw = args.batch or args.inputs
    if not ids_raw:
        ids_raw = [input("输入 sph 链接或 ID: ").strip()]

    sph_ids = [parse_sph_input(raw) for raw in ids_raw if raw.strip()]

    if not sph_ids:
        print("❌ 未提供有效的视频号 ID")
        sys.exit(1)

    print(f"📡 视频号采集: {len(sph_ids)} 条")
    print()

    videos = []
    success = 0

    for i, sph_id in enumerate(sph_ids):
        sph_url = f"https://weixin.qq.com/sph/{sph_id}"
        print(f"[{i+1}/{len(sph_ids)}] {sph_url}")

        try:
            video = fetch_sph_video(sph_id)
            print(f"  作者: {video['author_name']}")
            print(f"  赞赏收藏转: {video['like_count']}/{video['fav_count']}/{video['forward_count']}")
            desc = video['description'][:80].replace('\n', ' ')
            print(f"  文案: {desc}...")
        except Exception as e:
            print(f"  ❌ 抓取失败: {e}")
            continue

        # 飞书入库
        if not args.no_feishu:
            write_to_feishu(video, sph_url)

        # 视频下载
        if args.download:
            dl_dir = args.download_dir or None
            video_path = download_sph_video(sph_id, output_dir=dl_dir)
            if video_path:
                video["_local_path"] = video_path
                print(f"  💡 转录命令: python scripts/transcribe_local.py \"{video_path}\" --engine whisper")

        # 标准化数据
        videos.append(format_for_json(video, sph_url, sph_id))
        success += 1
        print()

    # 输出标准 videos.json
    output_path = ""
    if args.output:
        result = {
            "accountUrl": "",
            "fetchedAt": datetime.now().isoformat(),
            "count": len(videos),
            "platform": "sph",
            "videos": videos,
        }
        output_path = args.output
        if not Path(output_path).is_absolute():
            output_path = str(BASE_DIR / output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"📄 已保存: {output_path}")

    # 同步到 Obsidian
    if args.to_obsidian and output_path:
        obs_script = str(BASE_DIR / "scripts" / "sync_to_obsidian.py")
        print()
        print("🔄 同步到 Obsidian...")
        result = subprocess.run(
            [sys.executable, obs_script, output_path, "-p", "sph"],
            capture_output=False
        )
        if result.returncode == 0:
            print("✅ Obsidian 同步完成")
        else:
            print(f"⚠️ Obsidian 同步出错")

    print()
    print(f"✨ 完成: {success}/{len(sph_ids)} 条采集成功")

    if not args.output and not args.to_obsidian:
        print()
        print("💡 提示: 加 --output videos.json 保存标准格式")
        print("💡 加 --to-obsidian 自动写入 Obsidian")


if __name__ == "__main__":
    main()
