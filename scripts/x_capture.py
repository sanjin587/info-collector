#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X/Twitter 推文内容采集脚本

输入推文链接或 ID，自动：
  1. 调 FxTwitter API 获取结构化数据
  2. 下载图片（原图）和视频（最高码率 MP4）
  3. 按 entityMap / blocks 原始顺序重组 article.md
  4. ffprobe + SHA-256 校验所有媒体文件
  5. 输出完整采集目录

用法:
  python scripts/x_capture.py "https://x.com/user/status/123456789"
  python scripts/x_capture.py 123456789
  python scripts/x_capture.py "https://x.com/user/status/123456789" -o ./my_output
  python scripts/x_capture.py "https://x.com/user/status/123456789" --no-download  # 只拿数据不下载媒体
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ── 路径配置 ──────────────────────────────────────────────
TOOLKIT_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = TOOLKIT_DIR / "downloads"
FX_API_BASE = "https://api.fxtwitter.com"

# Obsidian 配置（与 sync_to_obsidian.py 保持一致）
OBSIDIAN_VAULT = Path("d:/知识库/知识库")
OBSIDIAN_TARGET = "05_内容生产库/三金AI实验室_30天万粉作战计划/对标账号/X平台"

# ── 推文 ID 提取 ──────────────────────────────────────────

def extract_tweet_id(raw: str) -> str:
    """从各种格式的输入中提取纯数字推文 ID"""
    raw = raw.strip()
    # 纯数字
    if raw.isdigit():
        return raw
    # URL 格式: x.com/user/status/ID, twitter.com/user/status/ID,
    #          fxtwitter.com/user/status/ID, fixupx.com/user/status/ID
    m = re.search(r'/status(?:es)?/(\d{15,25})', raw)
    if m:
        return m.group(1)
    # 末尾是数字的情况（如 /photo/1 这种也要跳过）
    m = re.search(r'/(\d{15,25})(?:/|\?|$)', raw)
    if m:
        return m.group(1)
    raise ValueError(f"无法从输入中提取推文 ID: {raw}")

def normalize_url(tweet_id: str, screen_name: str = "i") -> str:
    """生成标准推文 URL"""
    return f"https://x.com/{screen_name}/status/{tweet_id}"

# ── API 数据获取 ──────────────────────────────────────────

def fetch_tweet(tweet_id: str) -> dict:
    """调 FxTwitter API 获取推文完整结构化数据"""
    url = f"{FX_API_BASE}/status/{tweet_id}"
    import urllib.request
    import urllib.error

    print(f"📡 请求 FxTwitter API: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "x-capture/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 返回 {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"API 请求失败: {e}")

    if data.get("code") != 200:
        raise RuntimeError(f"API 错误: {data.get('message', 'UNKNOWN')}")

    tweet = data.get("tweet")
    if not tweet:
        raise RuntimeError("API 返回数据中无 tweet 字段")

    return tweet

# ── 媒体分析 ──────────────────────────────────────────────

def pick_best_video_url(video: dict) -> tuple[str, int, str, str]:
    """
    从视频对象的 formats[] 中选出最高码率的 MP4。
    返回 (url, bitrate, resolution, codec)。
    """
    formats = video.get("formats", [])
    if not formats:
        # 回退：用顶层 url
        return video.get("url", ""), 0, f"{video.get('width',0)}x{video.get('height',0)}", "unknown"

    best = None
    best_bitrate = -1
    for fmt in formats:
        # 跳过 m3u8 流
        if fmt.get("container") == "m3u8":
            continue
        # 只要 mp4 容器
        container = fmt.get("container", "").lower()
        if container and container != "mp4":
            continue
        bitrate = fmt.get("bitrate", 0) or 0
        if bitrate > best_bitrate:
            best_bitrate = bitrate
            best = fmt

    if best is None:
        # 全被过滤了，用第一个非 m3u8 的
        for fmt in formats:
            if fmt.get("container") != "m3u8":
                best = fmt
                best_bitrate = fmt.get("bitrate", 0) or 0
                break

    if best is None:
        return video.get("url", ""), 0, f"{video.get('width',0)}x{video.get('height',0)}", "unknown"

    resolution = f"{best.get('width', video.get('width', '?'))}x{best.get('height', video.get('height', '?'))}"
    return best["url"], best_bitrate, resolution, best.get("codec", "unknown")

def collect_media(tweet: dict) -> list[dict]:
    """
    收集全部媒体，保持 media.all[] 的原始顺序。
    每条记录：{index, type, kind, url, width, height, duration, best_url, bitrate, codec}
    """
    media_all = list((tweet.get("media") or {}).get("all", []) or [])
    # Article 类型的媒体不在 tweet.media.all[]，而是在 article.media_entities[]。
    # FxTwitter 对长文章返回的 entityMap 也是列表而不是字典，需兼容两种结构。
    if not media_all:
        article = tweet.get("article") or {}
        for entity in article.get("media_entities", []) or []:
            info = entity.get("media_info") or {}
            url = info.get("original_img_url", "")
            if not url:
                continue
            media_all.append({
                "type": "photo",
                "id": entity.get("media_id", ""),
                "url": url,
                "width": info.get("original_img_width", 0),
                "height": info.get("original_img_height", 0),
                "altText": "",
                "format": Path(urlparse(url).path).suffix.lstrip(".") or "jpg",
            })
    photos = {p.get("id"): p for p in tweet.get("media", {}).get("photos", [])}
    videos = {v.get("id"): v for v in tweet.get("media", {}).get("videos", [])}

    result = []
    for i, m in enumerate(media_all):
        mtype = m.get("type", "")
        mid = m.get("id", "")
        if mtype in ("photo", "gif"):
            url = m.get("url", "")
            item = {
                "index": i,
                "type": "photo",
                "format": m.get("format", "jpg"),
                "url": url,
                "orig_url": url.split("?")[0] + "?name=orig" if "?" not in url else url + "&name=orig",
                "width": m.get("width", 0),
                "height": m.get("height", 0),
                "alt_text": m.get("altText", ""),
                "id": mid,
            }
            result.append(item)
        elif mtype in ("video", "gif"):
            best_url, bitrate, resolution, codec = pick_best_video_url(m)
            item = {
                "index": i,
                "type": "video",
                "format": m.get("format", "mp4"),
                "url": m.get("url", ""),
                "best_url": best_url,
                "bitrate": bitrate,
                "resolution": resolution,
                "codec": codec,
                "thumbnail_url": m.get("thumbnail_url", ""),
                "duration": m.get("duration", 0),
                "width": m.get("width", 0),
                "height": m.get("height", 0),
                "id": mid,
            }
            result.append(item)
    return result

# ── 文件下载 ──────────────────────────────────────────────

def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    """下载文件到目标路径，支持重试"""
    import urllib.request

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if len(data) == 0:
                raise RuntimeError("下载内容为空")
            dest.write_bytes(data)
            return True
        except Exception as e:
            print(f"  ⚠ 第 {attempt+1}/{retries} 次下载失败: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    return False

def download_media(media_list: list[dict], output_dir: Path) -> list[dict]:
    """下载所有媒体文件，更新本地路径"""
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for m in media_list:
        if m["type"] == "photo":
            ext = m.get("format", "jpg") or "jpg"
            fname = f"image_{m['index']+1:02d}.{ext}"
            dest = output_dir / fname
            url = m["orig_url"]
            print(f"  🖼 下载图片 {m['width']}x{m['height']}: {fname}")
            if download_file(url, dest):
                m["local_path"] = str(dest)
                m["local_name"] = fname
                m["sha256"] = sha256_file(dest)
                m["file_size"] = dest.stat().st_size
            else:
                # 回退到非 orig URL
                print(f"  ⚠ orig 失败，回退到普通 URL")
                if download_file(m["url"], dest):
                    m["local_path"] = str(dest)
                    m["local_name"] = fname
                    m["sha256"] = sha256_file(dest)
                    m["file_size"] = dest.stat().st_size
                else:
                    print(f"  ❌ 图片下载失败: {fname}")
                    m["local_path"] = None
            downloaded.append(m)

        elif m["type"] == "video":
            ext = m.get("format", "mp4") or "mp4"
            fname = f"video_{m['index']+1:02d}.{ext}"
            dest = output_dir / fname
            url = m.get("best_url") or m["url"]
            print(f"  🎬 下载视频 {m['resolution']} {m.get('bitrate',0)//1000}kbps: {fname}")
            if download_file(url, dest):
                m["local_path"] = str(dest)
                m["local_name"] = fname
                m["sha256"] = sha256_file(dest)
                m["file_size"] = dest.stat().st_size
            else:
                print(f"  ❌ 视频下载失败: {fname}")
                m["local_path"] = None
            downloaded.append(m)

    return downloaded

# ── 文件校验 ──────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    """计算文件 SHA-256"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def ffprobe_check(path: Path) -> dict:
    """用 ffprobe 检查媒体文件"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "valid": False}
        info = json.loads(result.stdout)
        streams = info.get("streams", [])
        fmt = info.get("format", {})

        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        return {
            "valid": True,
            "format_name": fmt.get("format_name", ""),
            "duration": float(fmt.get("duration", 0) or 0),
            "size": int(fmt.get("size", 0) or 0),
            "bit_rate": int(fmt.get("bit_rate", 0) or 0),
            "video_streams": len(video_streams),
            "audio_streams": len(audio_streams),
            "video_codec": video_streams[0].get("codec_name", "") if video_streams else "",
            "width": video_streams[0].get("width", 0) if video_streams else 0,
            "height": video_streams[0].get("height", 0) if video_streams else 0,
            "audio_codec": audio_streams[0].get("codec_name", "") if audio_streams else "",
        }
    except FileNotFoundError:
        return {"error": "ffprobe 未安装", "valid": None}
    except Exception as e:
        return {"error": str(e), "valid": False}

def validate_all(downloaded_media: list[dict]) -> list[dict]:
    """对所有已下载媒体执行 ffprobe 校验"""
    print("\n🔍 文件完整性校验")
    results = []
    for m in downloaded_media:
        path = m.get("local_path")
        if not path or not Path(path).exists():
            results.append({**m, "valid": False, "error": "文件不存在"})
            print(f"  ❌ {m.get('local_name', '?'):20s} 文件不存在")
            continue

        info = ffprobe_check(Path(path))
        info["local_name"] = m.get("local_name", "")
        info["type"] = m.get("type", "")
        info["sha256"] = m.get("sha256", "")
        info["file_size_disk"] = Path(path).stat().st_size

        if info.get("valid"):
            status = "✅"
            detail = f"{info.get('width',0)}x{info.get('height',0)}, {info.get('duration',0):.1f}s"
            if info.get("video_codec"):
                detail += f", {info['video_codec']}"
            if info.get("audio_streams", 0) > 0:
                detail += f", 音频:{info['audio_codec']}"
        else:
            status = "⚠️" if info.get("valid") is None else "❌"
            detail = info.get("error", "未知错误")

        print(f"  {status} {m.get('local_name', '?'):20s} {detail}")
        results.append(info)

    return results

# ── article.md 生成 ───────────────────────────────────────

def format_count(n) -> str:
    """数字格式化：超过 10000 用万"""
    if n is None:
        return "—"
    n = int(n)
    if n >= 10000:
        return f"{n/10000:.1f}万"
    return f"{n:,}"

def format_time(ts) -> str:
    """Unix 时间戳 → 可读日期"""
    if not ts:
        return ""
    try:
        ts = int(ts)
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)

def generate_article_md(tweet: dict, media_list: list[dict], output_dir: Path) -> str:
    """按原始顺序生成 article.md"""
    lines = []

    # ── 标题 ──
    title = ""
    if tweet.get("article"):
        title = tweet["article"].get("title", "") or tweet["article"].get("preview_text", "")
    if not title:
        text = tweet.get("text", "")
        title = text.split("\n")[0][:80]

    lines.append(f"# {title}")
    lines.append("")

    # ── 元数据表 ──
    author = tweet.get("author", {})
    lines.append("| 字段 | 值 |")
    lines.append("|:---|---|")
    lines.append(f"| 作者 | @{author.get('screen_name', '?')} ({author.get('name', '?')}) |")
    lines.append(f"| 推文链接 | {tweet.get('url', '')} |")
    lines.append(f"| 发布时间 | {format_time(tweet.get('created_timestamp'))} |")
    lines.append(f"| 点赞 | {format_count(tweet.get('likes'))} |")
    lines.append(f"| 转发 | {format_count(tweet.get('retweets'))} |")
    lines.append(f"| 回复 | {format_count(tweet.get('replies'))} |")
    lines.append(f"| 查看 | {format_count(tweet.get('views'))} |")
    lines.append(f"| 收藏 | {format_count(tweet.get('bookmarks'))} |")
    lines.append(f"| 引用 | {format_count(tweet.get('quotes'))} |")
    lines.append(f"| 语言 | {tweet.get('lang', '')} |")
    lines.append(f"| 来源 | {tweet.get('source', '')} |")
    if tweet.get("is_note_tweet"):
        lines.append(f"| 类型 | 长推文 (Note Tweet) |")
    if tweet.get("possibly_sensitive"):
        lines.append(f"| ⚠️ | 可能包含敏感内容 |")
    lines.append(f"| 采集时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |")
    lines.append(f"| 推文 ID | {tweet.get('id', '')} |")
    lines.append("")

    # ── 正文 ──
    lines.append("---")
    lines.append("")
    lines.append("## 正文")
    lines.append("")

    article = tweet.get("article")
    if article:
        blocks = article.get("content", {}).get("blocks", [])
        entity_map = article.get("content", {}).get("entityMap", {})
        media_entities = article.get("media_entities", [])

        # 构建实体索引
        if isinstance(entity_map, list):
            entity_by_key = {
                str(item.get("key")): item.get("value", {})
                for item in entity_map
                if isinstance(item, dict)
            }
        else:
            entity_by_key = {str(key): entity for key, entity in entity_map.items()}

        media_by_id = {str(m.get("id")): m for m in media_list if m.get("id")}

        def render_media_entity(entity: dict) -> str:
            """将 Article 的媒体或 Markdown 实体映射为本地 Markdown。"""
            data = entity.get("data", {}) if isinstance(entity, dict) else {}
            # X Article 的代码块不是 block.type=code-block，而是
            # entityMap 中的 type=MARKDOWN；如果只处理媒体，会静默丢失
            # API 调用和安装命令等关键证据。
            markdown = data.get("markdown")
            if markdown:
                return f"\n\n{str(markdown).strip()}\n\n"
            media_items = data.get("mediaItems", []) or []
            for media_item in media_items:
                media_id = str(media_item.get("mediaId", ""))
                media = media_by_id.get(media_id)
                if not media:
                    continue
                if media.get("type") == "photo":
                    return f"\n\n![{media.get('alt_text', '图片')}]({media.get('local_name', media.get('url', ''))})\n\n"
                if media.get("type") == "video":
                    return f"\n\n<video src=\"{media.get('local_name', media.get('url', ''))}\" controls width=\"{media.get('width',0)}\" height=\"{media.get('height',0)}\"></video>\n\n"
            return ""

        # 遍历 blocks 按 entityMap 组装
        media_idx = 0
        for block in blocks:
            btype = block.get("type", "")
            text = block.get("text", "")

            if btype == "unstyled":
                # 检查 entityRanges 中是否有媒体引用
                entity_ranges = block.get("entityRanges", [])
                if entity_ranges:
                    parts = []
                    last_end = 0
                    for er in entity_ranges:
                        # 插入前面的文本
                        parts.append(text[last_end:er.get("offset", 0)])
                        ekey = str(er.get("key", ""))
                        entity = entity_by_key.get(ekey, {})
                        etype = entity.get("type", "")

                        if etype == "MEDIA":
                            rendered = render_media_entity(entity)
                            if rendered:
                                parts.append(rendered)
                                media_idx += 1
                        elif etype == "IMAGE" and media_idx < len([m for m in media_list if m["type"] == "photo"]):
                            photos = [m for m in media_list if m["type"] == "photo"]
                            if media_idx < len(photos):
                                img = photos[media_idx]
                                parts.append(f"\n\n![{img.get('alt_text', '图片')}]({img.get('local_name', img.get('url', ''))})\n\n")
                                media_idx += 1
                        elif etype == "VIDEO" and media_idx < len([m for m in media_list if m["type"] == "video"]):
                            videos = [m for m in media_list if m["type"] == "video"]
                            vid_idx = sum(1 for m in media_list[:media_idx] if m["type"] == "video")
                            videos_only = [m for m in media_list if m["type"] == "video"]
                            if vid_idx < len(videos_only):
                                vid = videos_only[vid_idx]
                                parts.append(f"\n\n<video src=\"{vid.get('local_name', vid.get('url', ''))}\" controls width=\"{vid.get('width',0)}\" height=\"{vid.get('height',0)}\"></video>\n\n")
                                media_idx += 1
                        else:
                            # 链接等其他实体，保留文本
                            parts.append(text[er.get("offset", 0):er.get("offset", 0) + er.get("length", 0)])

                        last_end = er.get("offset", 0) + er.get("length", 0)
                    parts.append(text[last_end:])
                    lines.append("".join(parts))
                else:
                    if text.strip():
                        lines.append(text)
                        lines.append("")
            elif btype == "header-one":
                lines.append(f"## {text}")
                lines.append("")
            elif btype == "header-two":
                lines.append(f"### {text}")
                lines.append("")
            elif btype == "header-three":
                lines.append(f"#### {text}")
                lines.append("")
            elif btype == "blockquote":
                lines.append(f"> {text}")
                lines.append("")
            elif btype == "code-block":
                lines.append(f"```")
                lines.append(text)
                lines.append(f"```")
                lines.append("")
            elif btype == "atomic":
                # 原子块通常是内嵌媒体；Article 的媒体引用位于 entityRanges。
                rendered = ""
                for er in block.get("entityRanges", []) or []:
                    entity = entity_by_key.get(str(er.get("key", "")), {})
                    rendered = render_media_entity(entity)
                    if rendered:
                        break
                if rendered:
                    lines.append(rendered.strip())
                    lines.append("")
            else:
                if text.strip():
                    lines.append(text)
                    lines.append("")
    else:
        # 普通推文：直接输出 text
        text = tweet.get("text", "")
        lines.append(text)
        lines.append("")

    # ── 媒体区 ──
    photos = [m for m in media_list if m["type"] == "photo"]
    videos = [m for m in media_list if m["type"] == "video"]

    if photos or videos:
        lines.append("---")
        lines.append("")
        lines.append("## 媒体文件")
        lines.append("")

        if photos:
            lines.append("### 图片")
            lines.append("")
            for p in photos:
                name = p.get("local_name", p.get("url", "?"))
                alt = p.get("alt_text", "") or name
                size = f"{p.get('width',0)}x{p.get('height',0)}"
                sha = p.get("sha256", "")
                lines.append(f"![{alt}]({name})")
                lines.append(f"*{size} · SHA256: `{sha[:16]}...`*")
                lines.append("")

        if videos:
            lines.append("### 视频")
            lines.append("")
            for v in videos:
                name = v.get("local_name", v.get("url", "?"))
                duration = v.get("duration", 0)
                mins = int(duration // 60)
                secs = int(duration % 60)
                lines.append(f"<video src=\"{name}\" controls width=\"{v.get('width',0)}\" height=\"{v.get('height',0)}\"></video>")
                lines.append(f"*{v.get('resolution','')} · {v.get('codec','')} · {mins}:{secs:02d} · {v.get('bitrate',0)//1000}kbps · SHA256: `{v.get('sha256','')[:16]}...`*")
                lines.append("")

    # ── 投票 ──
    poll = tweet.get("poll")
    if poll:
        lines.append("---")
        lines.append("")
        lines.append("## 投票")
        lines.append(f"总票数: {poll.get('total_votes',0)} · 截止: {poll.get('ends_at','')} ({poll.get('time_left_en','')})")
        lines.append("")
        lines.append("| 选项 | 票数 | 占比 |")
        lines.append("|:---|---:|---:|")
        for c in poll.get("choices", []):
            lines.append(f"| {c.get('label','')} | {c.get('count',0)} | {c.get('percentage',0):.1f}% |")
        lines.append("")

    # ── 引用推文 ──
    quote = tweet.get("quote")
    if quote:
        lines.append("---")
        lines.append("")
        lines.append("## 引用推文")
        q_author = quote.get("author", {})
        lines.append(f"**@{q_author.get('screen_name', '?')}** ({q_author.get('name', '?')})")
        lines.append("")
        lines.append(quote.get("text", ""))
        lines.append("")
        lines.append(f"🔗 {quote.get('url', '')}")
        lines.append(f"❤️ {format_count(quote.get('likes'))} 🔄 {format_count(quote.get('retweets'))} 💬 {format_count(quote.get('replies'))}")
        lines.append("")

        # 引用推文的媒体（如有）
        q_media = quote.get("media", {})
        q_photos = q_media.get("photos", [])
        q_videos = q_media.get("videos", [])
        if q_photos or q_videos:
            lines.append("### 引用推文媒体")
            for i, p in enumerate(q_photos):
                lines.append(f"![引用图片 {i+1}]({p.get('url','')})")
            lines.append("")

    # ── 外部链接预览 (Twitter Card) ──
    card = tweet.get("card")
    if card and card.get("url"):
        lines.append("---")
        lines.append("")
        lines.append("## 链接预览")
        if card.get("image"):
            lines.append(f"![]({card['image'].get('url','')})")
            lines.append("")
        lines.append(f"**[{card.get('title', card.get('description', card['url']))}]({card['url']})**")
        if card.get("description"):
            lines.append(f"> {card['description']}")
        if card.get("domain"):
            lines.append(f"🔗 {card['domain']}")
        lines.append("")

    # ── 社区笔记 ──
    note = tweet.get("community_note")
    if note and note.get("text"):
        lines.append("---")
        lines.append("")
        lines.append("## 📝 社区笔记")
        lines.append(f"> {note['text']}")
        lines.append("")

    return "\n".join(lines)

# ── 输出结构 ──────────────────────────────────────────────

def save_output(tweet: dict, media_list: list[dict], article_md: str, output_dir: Path) -> dict:
    """保存所有输出文件"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 推文原始数据
    tweet_json_path = output_dir / "tweet_data.json"
    tweet_json_path.write_text(json.dumps(tweet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  📄 tweet_data.json")

    # article.md
    md_path = output_dir / "article.md"
    md_path.write_text(article_md, encoding="utf-8")
    print(f"  📝 article.md")

    # checksums.sha256
    checksum_path = output_dir / "checksums.sha256"
    checksum_lines = []
    for m in media_list:
        name = m.get("local_name", "")
        sha = m.get("sha256", "")
        if name and sha:
            checksum_lines.append(f"{sha}  {name}")
    if checksum_lines:
        checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        print(f"  🔐 checksums.sha256")

    return {
        "tweet_json": str(tweet_json_path),
        "article_md": str(md_path),
        "checksums": str(checksum_path) if checksum_lines else None,
        "media_count": len(media_list),
        "output_dir": str(output_dir),
    }

# ── 主流程 ────────────────────────────────────────────────

def capture(url_or_id: str, output_dir: Optional[Path] = None, download: bool = True) -> dict:
    """主采集流程"""
    tweet_id = extract_tweet_id(url_or_id)
    print(f"🎯 推文 ID: {tweet_id}")

    if output_dir is None:
        output_dir = DOWNLOADS_DIR / tweet_id

    # Step 1: 获取 API 数据
    tweet = fetch_tweet(tweet_id)
    author = tweet.get("author", {})
    screen_name = author.get("screen_name", "unknown")
    print(f"👤 作者: @{screen_name} ({author.get('name', '?')})")
    print(f"📅 时间: {format_time(tweet.get('created_timestamp'))}")
    print(f"📊 互动: ❤️{format_count(tweet.get('likes'))} 🔄{format_count(tweet.get('retweets'))}")
    print(f"📝 类型: {'长推文' if tweet.get('is_note_tweet') else '普通推文'}{' + Article' if tweet.get('article') else ''}")

    # Step 2: 收集媒体
    media_list = collect_media(tweet)
    print(f"🖼 媒体: {len([m for m in media_list if m['type']=='photo'])} 图片, "
          f"{len([m for m in media_list if m['type']=='video'])} 视频")

    # Step 3: 下载媒体
    if download and media_list:
        print(f"\n📥 下载媒体文件到: {output_dir}")
        media_list = download_media(media_list, output_dir)
        downloaded_count = sum(1 for m in media_list if m.get("local_path"))
        print(f"  下载完成: {downloaded_count}/{len(media_list)}")

    # Step 4: 校验
    if download:
        validate_all(media_list)

    # Step 5: 生成 article.md
    print(f"\n📝 生成 article.md ...")
    article_md = generate_article_md(tweet, media_list, output_dir)

    # Step 6: 保存
    print(f"\n💾 保存到: {output_dir}")
    result = save_output(tweet, media_list, article_md, output_dir)

    print(f"\n✨ 采集完成!")
    print(f"   输出目录: {output_dir}")
    print(f"   推文数据: tweet_data.json")
    print(f"   重组文档: article.md")
    print(f"   媒体文件: {result['media_count']} 个")

    return result

# ── CLI ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="X/Twitter 推文内容采集",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python x_capture.py "https://x.com/user/status/123456789"
  python x_capture.py 123456789
  python x_capture.py "https://x.com/user/status/123456789" --no-download
        """
    )
    parser.add_argument("url", help="推文链接或纯数字 ID")
    parser.add_argument("-o", "--output", help="输出目录 (默认: downloads/<tweet_id>)")
    parser.add_argument("--no-download", action="store_true", help="只获取数据，不下载媒体")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    args = parser.parse_args()

    try:
        output_dir = Path(args.output) if args.output else None
        result = capture(args.url, output_dir=output_dir, download=not args.no_download)

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except ValueError as e:
        print(f"❌ 输入错误: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"❌ 未预期错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(3)

if __name__ == "__main__":
    main()
