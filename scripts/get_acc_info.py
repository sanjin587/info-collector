#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从抖音账号页面提取公开信息（昵称、粉丝、获赞、作品数等）。

用法:
  python get_acc_info.py <账号主页URL>
  python get_acc_info.py https://www.douyin.com/user/MS4wLjAB...
  python get_acc_info.py --headless <URL>   无头模式（不显示浏览器窗口）

依赖: playwright（pip install playwright && python -m playwright install chromium）
"""
import argparse
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def main(account_url: str, headless: bool = True):
    from playwright.sync_api import sync_playwright

    print(f"🌐 目标: {account_url}")
    print(f"🔍 模式: {'无头' if headless else '有头'}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
        )
        page.goto(account_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        text = page.evaluate("document.body.innerText")
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        print(f"\n{'='*50}")
        print("📋 页面文本（前 80 行）:")
        print(f"{'='*50}\n")
        for i, line in enumerate(lines[:80]):
            print(line)

        browser.close()

        print(f"\n{'='*50}")
        print(f"✅ 共提取 {min(len(lines), 80)} 行文本")
        print(f"💡 如需更多行，可修改 max_lines 参数")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="抖音账号页面信息提取",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python get_acc_info.py https://www.douyin.com/user/MS4wLjAB...
  python get_acc_info.py --headless https://www.douyin.com/user/XXX
  python get_acc_info.py --no-headless https://www.douyin.com/user/XXX
        """,
    )
    parser.add_argument("url", help="抖音账号主页 URL")
    parser.add_argument(
        "--headless", dest="headless", action="store_true", default=True,
        help="无头模式（默认）",
    )
    parser.add_argument(
        "--no-headless", dest="headless", action="store_false",
        help="显示浏览器窗口",
    )
    args = parser.parse_args()
    main(args.url, headless=args.headless)
