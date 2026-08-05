# -*- coding: utf-8 -*-
"""Capture public Douyin profile cards and observed works API responses."""
import argparse
import json
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright


def main(profile_url, output):
    responses = []
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

        def on_response(response):
            if "/aweme/post" not in response.url:
                return
            row = {"url": response.url, "status": response.status}
            try:
                row["body"] = response.json()
            except Exception as exc:
                row["body_error"] = str(exc)[:200]
            responses.append(row)

        page.on("response", on_response)
        page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        for _ in range(30):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
        body = page.locator("body").inner_text()
        links = page.eval_on_selector_all(
            "a[href*='/video/']",
            "els => els.map(a => ({href:a.href.split('?')[0], text:(a.innerText||'').trim()}))",
        ) or []
        rows = {}
        for link in links:
            match = re.search(r"/video/(\d{19})$", link.get("href", ""))
            if match:
                rows[match.group(1)] = {
                    "video_id": match.group(1),
                    "url": f"https://www.douyin.com/video/{match.group(1)}",
                    "card_text": link.get("text", ""),
                }
        result = {
            "profile_url": profile_url,
            "works_displayed_text": re.search(r"作品\s*([^\n]+)", body).group(1) if re.search(r"作品\s*([^\n]+)", body) else None,
            "followers_displayed_text": re.search(r"粉丝\s*([^\n]+)", body).group(1) if re.search(r"粉丝\s*([^\n]+)", body) else None,
            "likes_displayed_text": re.search(r"获赞\s*([^\n]+)", body).group(1) if re.search(r"获赞\s*([^\n]+)", body) else None,
            "account": "老林说",
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "videos": list(rows.values()),
            "post_responses": responses,
        }
        browser.close()
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output, "cards": len(result["videos"]), "post_responses": len(responses), "displayed": result["works_displayed_text"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-url", required=True)
    parser.add_argument("--output", required=True)
    main(parser.parse_args().profile_url, parser.parse_args().output)
