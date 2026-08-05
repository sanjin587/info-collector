# -*- coding: utf-8 -*-
"""Scrape a public Douyin profile's work links until the displayed count is reached."""
import argparse
import json
import os
import re
import time
from datetime import datetime

from playwright.sync_api import sync_playwright


def scrape(profile_url, output_path):
    with sync_playwright() as p:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        launch_kwargs = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        }
        if os.path.exists(chrome_path):
            launch_kwargs["executable_path"] = chrome_path
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36", viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        rows = {}
        body_text = ""
        for _ in range(80):
            body_text = page.locator("body").inner_text()
            links = page.eval_on_selector_all("a[href*='/video/']", "els => els.map(a => ({href:a.href.split('?')[0], text:(a.innerText||'').trim()}))") or []
            for link in links:
                m = re.search(r"/video/(\d{19})$", link.get("href", ""))
                if m and m.group(1) not in rows:
                    text = re.sub(r"^.*?：", "", link.get("text", ""), count=1).strip()
                    rows[m.group(1)] = {"video_id": m.group(1), "url": f"https://www.douyin.com/video/{m.group(1)}", "card_text": text}
            work_match = re.search(r"作品\s*([\d.万]+)", body_text)
            expected = work_match.group(1) if work_match else None
            if expected and expected.isdigit() and len(rows) >= int(expected):
                break
            page.evaluate("""()=>{const candidates=[...document.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+300); const e=candidates[candidates.length-1]||document.scrollingElement; e.scrollTop=e.scrollHeight;}""")
            page.wait_for_timeout(2500)
        title = page.title()
        h1 = page.eval_on_selector_all("h1", "els => els.map(e => (e.innerText||'').trim()).filter(Boolean)") or []
        result = {
            "profile_url": profile_url,
            "account": h1[0] if h1 else title.replace("的抖音 - 抖音", "").strip(),
            "page_title": title,
            "works_displayed": (re.search(r"作品\s*([\d.万]+)", body_text) or [None, None])[1],
            "followers_displayed": (re.search(r"粉丝\s*([\d.万]+)", body_text) or [None, None])[1],
            "likes_displayed": (re.search(r"获赞\s*([\d.万]+)", body_text) or [None, None])[1],
            "ip_displayed": (re.search(r"IP属地：?([^\n]+)", body_text) or [None, None])[1],
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "videos": list(rows.values()),
        }
        browser.close()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output_path, "account": result["account"], "displayed": result["works_displayed"], "collected": len(result["videos"])}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    scrape(args.profile_url, args.output)
