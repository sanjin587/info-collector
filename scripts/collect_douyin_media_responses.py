# -*- coding: utf-8 -*-
"""Collect Douyin public video media URLs by observing the page's media responses."""
import argparse
import json
import os
import time
from datetime import datetime

from playwright.sync_api import sync_playwright


VIDEO_IDS = [
    "7668536797386886438", "7665998700216421638", "7663743829635321131",
    "7663011098144165139", "7660075742058908991", "7657851624437665070",
    "7656760570267340041", "7656670000811461894", "7655539775025302794",
    "7654876397420203306", "7654488479883136296", "7652581451782704435",
    "7651942738878893362", "7648871494637997318", "7647383784245005622",
    "7646270311234620723", "7644052294165712179", "7642926255028866345",
    "7642223687617350921", "7637851467512139046", "7637842086586256650",
    "7637062114623950106", "7634900840415990618", "7631456787039849762",
    "7628929172488936155", "7624077651002576155", "7616237675493788971",
    "7615497810141613353", "7613284049108438287", "7612977318516084003",
    "7606730350472387657", "7605143490791476514", "7602211836473347368",
]


def choose_media(urls):
    usable = [u for u in urls if "douyinvod.com" in u or "/aweme/v1/play/" in u]
    preferred = [u for u in usable if "media-video" in u or "/aweme/v1/play/" in u]
    return (preferred or usable or [None])[0]


def choose_track(urls, marker):
    matches = [u for u in urls if "douyinvod.com" in u and marker in u]
    return matches[0] if matches else None


def collect(output_path, wait_ms=9000):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        for index, video_id in enumerate(VIDEO_IDS, 1):
            url = f"https://www.douyin.com/video/{video_id}"
            hits = []
            item = {
                "video_id": video_id,
                "url": url,
                "title": "",
                "media_url": None,
                "media_video_url": None,
                "media_audio_url": None,
                "collected_at": datetime.now().isoformat(timespec="seconds"),
            }
            handler = lambda response, hits=hits: hits.append(response.url)
            try:
                page.on("response", handler)
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(wait_ms)
                item["title"] = page.title()
                item["media_video_url"] = choose_track(hits, "media-video")
                item["media_audio_url"] = choose_track(hits, "media-audio")
                item["media_url"] = item["media_video_url"] or choose_media(hits)
                if not item["media_url"]:
                    item["error"] = "未捕获到 douyinvod 媒体流"
            except Exception as exc:
                item["error"] = str(exc)[:300]
            results.append(item)
            ok = sum(1 for row in results if row.get("media_url"))
            print(f"[{index:02d}/{len(VIDEO_IDS)}] {video_id} media={'ok' if item.get('media_url') else 'miss'} total_ok={ok}", flush=True)
            page.remove_listener("response", handler)
        browser.close()
    payload = {
        "account": "宅不住的AI",
        "account_url": "https://www.douyin.com/user/MS4wLjABAAAAdSEZrolOwkMaR7gVOFFWOTlDxMhdibtEV3m41a4YrWo",
        "source_video_url": "https://www.douyin.com/jingxuan?modal_id=7648871494637997318",
        "source_count_verified": len(VIDEO_IDS),
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "videos": results,
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output_path, "count": len(results), "media_ok": sum(bool(x.get("media_url")) for x in results)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--wait-ms", type=int, default=9000)
    args = parser.parse_args()
    collect(args.output, args.wait_ms)
