# -*- coding: utf-8 -*-
"""Capture public Douyin video/audio media URLs for a saved profile dataset."""
import argparse
import json
import os
from datetime import datetime

from playwright.sync_api import sync_playwright


def choose_track(urls, marker):
    matches = [u for u in urls if "douyinvod.com" in u and marker in u]
    return matches[0] if matches else None


def choose_media(urls):
    usable = [u for u in urls if "douyinvod.com" in u or "/aweme/v1/play/" in u]
    preferred = [u for u in usable if "media-video" in u or "/aweme/v1/play/" in u]
    return (preferred or usable or [None])[0]


def collect(profile_path, output_path, wait_ms=7000, limit=None):
    profile = json.load(open(profile_path, encoding="utf-8-sig"))
    videos = profile.get("videos", [])
    if limit is not None:
        videos = videos[:limit]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    rows = []
    with sync_playwright() as p:
        launch = {"headless": True, "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]}
        bundled_path = r"C:\Users\Administrator\AppData\Local\ms-playwright\chromium-1228\chrome-win64\chrome.exe"
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(bundled_path):
            launch["executable_path"] = bundled_path
        elif os.path.exists(chrome_path):
            launch["executable_path"] = chrome_path
        browser = p.chromium.launch(**launch)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        for index, item in enumerate(videos, 1):
            video_id = item["video_id"]
            hits = []
            row = {
                "video_id": video_id,
                "url": item.get("url", f"https://www.douyin.com/video/{video_id}"),
                "title": item.get("card_text", item.get("title", "")),
                "media_url": None,
                "media_video_url": None,
                "media_audio_url": None,
                "collected_at": datetime.now().isoformat(timespec="seconds"),
            }
            handler = lambda response, hits=hits: hits.append(response.url)
            try:
                page.on("response", handler)
                page.goto(row["url"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(wait_ms)
                row["page_title"] = page.title()
                row["media_video_url"] = choose_track(hits, "media-video")
                row["media_audio_url"] = choose_track(hits, "media-audio")
                row["media_url"] = row["media_video_url"] or choose_media(hits)
                if not row["media_url"]:
                    row["error"] = "未捕获到 douyinvod 媒体流"
            except Exception as exc:
                row["error"] = str(exc)[:500]
            finally:
                page.remove_listener("response", handler)
            rows.append(row)
            ok = sum(bool(x.get("media_url")) for x in rows)
            print(f"[{index:02d}/{len(videos)}] {video_id} media={'ok' if row.get('media_url') else 'miss'} total_ok={ok}", flush=True)
        browser.close()
    payload = {
        "account": profile.get("account"),
        "profile_url": profile.get("profile_url"),
        "source_count_displayed": profile.get("works_displayed"),
        "source_count_collected": len(videos),
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "videos": rows,
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output_path, "total": len(rows), "media_ok": sum(bool(x.get("media_url")) for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wait-ms", type=int, default=7000)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    collect(args.profile, args.output, args.wait_ms, args.limit)
