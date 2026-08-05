# -*- coding: utf-8 -*-
"""Collect per-video Douyin metadata and real media URLs from a profile list."""
import argparse
import json
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright


def first(pattern, text):
    match = re.search(pattern, text or "")
    return match.group(1).strip() if match else None


def detail_fields(detail):
    if not isinstance(detail, dict):
        return {}
    stats = detail.get("statistics") or {}
    author = detail.get("author") or {}
    video = detail.get("video") or {}
    music = detail.get("music") or {}
    return {
        "title": detail.get("desc") or "",
        "create_time": detail.get("create_time"),
        "author_nickname": author.get("nickname"),
        "author_uid": author.get("uid"),
        "author_sec_uid": author.get("sec_uid"),
        "digg_count": stats.get("digg_count"),
        "comment_count": stats.get("comment_count"),
        "share_count": stats.get("share_count"),
        "collect_count": stats.get("collect_count"),
        "play_count": stats.get("play_count"),
        "duration_ms": video.get("duration"),
        "music_title": music.get("title"),
        "cover_url": ((video.get("cover") or {}).get("url_list") or [None])[0],
    }


def main(profile_path, output_path, wait_ms):
    profile = json.loads(open(profile_path, encoding="utf-8-sig").read())
    rows = []
    raw_details = {}
    with sync_playwright() as p:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        kwargs = {"headless": True, "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]}
        if os.path.exists(chrome_path):
            kwargs["executable_path"] = chrome_path
        browser = p.chromium.launch(**kwargs)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        current = {"detail": None, "raw": None}

        def on_response(response):
            if "/aweme/detail" not in response.url:
                return
            try:
                payload = response.json()
                detail = payload.get("aweme_detail") if isinstance(payload, dict) else None
                if detail:
                    current["detail"] = detail
                    current["raw"] = payload
            except Exception:
                pass

        page.on("response", on_response)
        total = len(profile.get("videos", []))
        for index, item in enumerate(profile.get("videos", []), 1):
            video_id = item["video_id"]
            current["detail"] = None
            current["raw"] = None
            row = {"video_id": video_id, "url": item["url"], "card_text": item.get("card_text", "")}
            try:
                page.goto(item["url"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(wait_ms)
                media = page.eval_on_selector_all("video", "els => els.map(v => v.currentSrc || v.src).filter(Boolean)") or []
                body = page.locator("body").inner_text()
                fields = detail_fields(current["detail"])
                row.update(fields)
                row["publish_time_text"] = first(r"发布时间：([^\n]+)", body)
                row["media_url"] = media[0] if media else None
                row["status"] = "ok" if row["media_url"] else "media_missing"
                if current["raw"] is not None:
                    raw_details[video_id] = current["raw"]
            except Exception as exc:
                row.update({"status": "error", "error": str(exc)[:500]})
            rows.append(row)
            print(f"[{index:02d}/{total}] {video_id} {row['status']}", flush=True)
        browser.close()
    output = {
        "account": profile.get("account"),
        "profile_url": profile.get("profile_url"),
        "display_count": profile.get("works_displayed"),
        "collected_count": len(rows),
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "videos": rows,
        "raw_details": raw_details,
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output_path, "total": len(rows), "media_ok": sum(x.get("status") == "ok" for x in rows), "errors": sum(x.get("status") != "ok" for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wait-ms", type=int, default=4000)
    args = parser.parse_args()
    main(args.profile, args.output, args.wait_ms)
