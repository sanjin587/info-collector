# -*- coding: utf-8 -*-
"""Retry failed Douyin media URLs from fresh authoritative video pages."""
import argparse
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright


def choose(urls, marker=None):
    usable = [u for u in urls if "douyinvod.com" in u or "/aweme/v1/play/" in u]
    if marker:
        marked = [u for u in usable if marker in u]
        if marked:
            return marked[0]
    preferred = [u for u in usable if "media-video" in u or "/aweme/v1/play/" in u]
    return (preferred or usable or [None])[0]


def main(dataset_path, output_path, wait_ms):
    dataset = json.loads(open(dataset_path, encoding="utf-8-sig").read())
    failed = [x for x in dataset.get("videos", []) if x.get("status") != "ok"]
    rows = []
    with sync_playwright() as p:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        launch = {"headless": True, "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]}
        if os.path.exists(chrome_path):
            launch["executable_path"] = chrome_path
        browser = p.chromium.launch(**launch)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        for index, item in enumerate(failed, 1):
            hits = []
            handler = lambda response, hits=hits: hits.append(response.url)
            row = {"video_id": item["video_id"], "url": item.get("url"), "retried_at": datetime.now().isoformat(timespec="seconds")}
            try:
                page.on("response", handler)
                page.goto(row["url"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(wait_ms)
                row["media_video_url"] = choose(hits, "media-video")
                row["media_audio_url"] = choose(hits, "media-audio")
                row["media_url"] = row["media_video_url"] or row["media_audio_url"] or choose(hits)
                row["status"] = "ok" if row["media_url"] else "media_missing"
            except Exception as exc:
                row.update({"status": "error", "error": str(exc)[:500]})
            finally:
                page.remove_listener("response", handler)
            rows.append(row)
            print(f"[{index:02d}/{len(failed)}] {row['video_id']} {row['status']}", flush=True)
        browser.close()
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump({"source_dataset": dataset_path, "videos": rows}, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output_path, "total": len(rows), "ok": sum(x.get("status") == "ok" for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wait-ms", type=int, default=7000)
    args = parser.parse_args()
    main(args.dataset, args.output, args.wait_ms)
