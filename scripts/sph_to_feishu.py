"""
视频号视频文案抓取 & 飞书入库

用法:
  python sph_to_feishu.py <sph_url_or_id>

示例:
  python sph_to_feishu.py https://weixin.qq.com/sph/AH9KmByTvv
  python sph_to_feishu.py AH9KmByTvv
"""
import json
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# 添加项目根路径（与 feishu/ utils/ 同级）
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from feishu.client import FeishuClient
from feishu.bitable import BitableManager

# ===== 配置（优先从环境变量读取，否则用默认值） =====
import os
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN")

if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN]):
    raise RuntimeError("请在 .env 中配置 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_APP_TOKEN")


def fetch_sph_video(sph_id: str) -> dict:
    """通过 API 获取视频号视频信息"""
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


def format_fields(video: dict, sph_url: str) -> dict:
    """格式化为飞书文章采集表字段"""
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


def main():
    # 解析输入
    raw = sys.argv[1] if len(sys.argv) > 1 else input("输入 sph 链接或 ID: ").strip()
    if "sph/" in raw:
        sph_id = raw.split("sph/")[-1].split("?")[0]
    else:
        sph_id = raw.strip()
    sph_url = f"https://weixin.qq.com/sph/{sph_id}"

    print(f"[抓取] {sph_url}")

    # 1. 调 API 拿数据
    video = fetch_sph_video(sph_id)
    print(f"  作者: {video['author_name']}")
    print(f"  点赞/评论/收藏: {video['like_count']}/{video['comment_count']}/{video['fav_count']}")
    print(f"  文案: {video['description'][:100]}...")

    # 2. 格式化
    fields = format_fields(video, sph_url)
    print(f"  标题: {fields.get('标题', '')}")
    print(f"  关键词: {fields.get('关键词', '')}")

    # 3. 飞书入库
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
    bitable = BitableManager(client, FEISHU_APP_TOKEN)
    bitable.ensure_tables()

    existing = bitable.get_existing_urls("文章采集")
    if sph_url in existing:
        print(f"  [跳过] 该视频已在表中")
        return

    record_id = bitable.create_record("文章采集", fields)
    if record_id:
        print(f"  [OK] 写入成功! record_id: {record_id}")
    else:
        print(f"  [ERR] 写入失败")


if __name__ == "__main__":
    main()
