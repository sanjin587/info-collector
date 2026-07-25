# -*- coding: utf-8 -*-
"""
抖音账号视频列表抓取脚本
主力方案：Playwright 打开账号主页 → 滚动加载 → 提取视频链接+数据
兜底方案：yt-dlp --flat-playlist

用法：
  python douyin_account_videos.py "https://www.douyin.com/user/XXX" [--max 50] [--output videos.json]
"""
import sys, json, os, re, time, argparse

# ============================================================
# 主力方案：Playwright
# ============================================================
def scrape_with_playwright(account_url, max_videos=50):
    """用 Playwright 打开抖音账号主页，滚动加载提取视频列表"""
    from playwright.sync_api import sync_playwright

    videos = []
    seen_urls = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
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

        print(f"[Playwright] 打开账号页面: {account_url}", file=sys.stderr)
        page.goto(account_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        # 尝试关掉可能的登录弹窗
        try:
            close_btn = page.query_selector('[class*="close"]')
            if close_btn:
                close_btn.click()
                page.wait_for_timeout(1000)
        except:
            pass

        # 切换到「作品」tab（抖音个人主页有 作品/喜欢/收藏 等tab）
        try:
            profile_tab = page.query_selector('[class*="profile"]')
            if not profile_tab:
                # 尝试文字匹配「作品」
                for tab_text in ["作品", "投稿", "视频"]:
                    tab = page.query_selector(f"text={tab_text}")
                    if tab:
                        tab.click()
                        page.wait_for_timeout(2000)
                        print(f"[Playwright] 已切换到「{tab_text}」tab", file=sys.stderr)
                        break
        except Exception as e:
            print(f"[Playwright] 切换tab失败（可能已经在作品tab）: {e}", file=sys.stderr)

        # 滚动加载
        prev_count = -1
        scroll_attempts = 0
        max_scrolls = 30  # 安全上限

        while len(videos) < max_videos and scroll_attempts < max_scrolls:
            # 提取当前页面的视频链接
            links = page.eval_on_selector_all(
                "a[href*='/video/']",
                "els => els.map(el => el.href)"
            ) or []

            for link in links:
                if link not in seen_urls and "/video/" in link:
                    seen_urls.add(link)
                    title_el = page.query_selector(f'a[href="{link.replace(page.url.split(".com")[0], "")}"]')
                    title = ""
                    if title_el:
                        title = title_el.inner_text()[:100]

                    videos.append({
                        "videoUrl": link.split("?")[0],  # 去掉跟踪参数
                        "title": title.strip(),
                    })

            current_count = len(videos)
            if current_count == prev_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            prev_count = current_count

            if current_count >= max_videos:
                break

            # 滚动
            page.evaluate("window.scrollBy(0, 1500)")
            page.wait_for_timeout(2000)
            print(f"  [Playwright] 已发现 {current_count} 条视频，继续滚动...", file=sys.stderr)

        browser.close()

    print(f"[Playwright] 共发现 {len(videos)} 条视频", file=sys.stderr)
    return videos


# ============================================================
# 兜底方案：yt-dlp
# ============================================================
def scrape_with_ytdlp(account_url, max_videos=50):
    """用 yt-dlp 尝试 playlist 解析"""
    import subprocess

    print(f"[yt-dlp] 尝试解析账号: {account_url}", file=sys.stderr)

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--no-download",
        "--dump-json",
        "--no-warnings",
        "--extractor-args", "douyin:webpage;",
        account_url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            video_url = data.get("webpage_url") or data.get("url") or ""
            if video_url:
                videos.append({
                    "videoUrl": video_url,
                    "title": data.get("title", ""),
                })
        except json.JSONDecodeError:
            continue

    print(f"[yt-dlp] 共发现 {len(videos)} 条视频", file=sys.stderr)
    return videos[:max_videos]


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="抓取抖音账号全部视频列表")
    parser.add_argument("account_url", help="抖音账号主页链接")
    parser.add_argument("--max", type=int, default=50, help="最大抓取数量（默认50）")
    parser.add_argument("--output", "-o", default=None, help="输出文件路径")
    parser.add_argument("--fallback-only", action="store_true", help="仅用兜底方案(yt-dlp)")
    args = parser.parse_args()

    account_url = args.account_url
    max_videos = args.max

    videos = []

    if not args.fallback_only:
        # 主力：Playwright
        try:
            videos = scrape_with_playwright(account_url, max_videos)
        except Exception as e:
            print(f"[WARN] Playwright 方案失败: {e}", file=sys.stderr)
            print("[INFO] 尝试兜底方案 yt-dlp...", file=sys.stderr)

    if not videos:
        # 兜底：yt-dlp
        try:
            videos = scrape_with_ytdlp(account_url, max_videos)
        except Exception as e:
            print(f"[ERROR] yt-dlp 方案也失败了: {e}", file=sys.stderr)
            sys.exit(1)

    if not videos:
        print("[ERROR] 未能获取到任何视频", file=sys.stderr)
        sys.exit(1)

    result = {
        "accountUrl": account_url,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(videos),
        "videos": videos,
    }

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"[OK] 已保存到 {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
