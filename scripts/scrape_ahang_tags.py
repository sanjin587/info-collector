"""Scrape 阿杭's douyin account for video tags via Playwright"""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\Administrator\Desktop\信息采集官工具包')
from playwright.sync_api import sync_playwright

# 阿杭的抖音号: 82862448782
# 使用 sec_uid 方式访问
ahang_url = 'https://www.douyin.com/user/MS4wLjABAAAAvKYbJjT5ZUprWELSNQjUxplXQ6CF9BuspkRufMtctFSa5iv-jIjPEWs_bzExERkK'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled','--no-sandbox'])
    page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36')

    # Try visiting a single video page first to see tags structure
    # From the vault: https://www.douyin.com/video/7655286079506945935 (闲鱼倒卖)

    video_urls = [
        'https://www.douyin.com/video/7655286079506945935',  # 闲鱼倒卖
        'https://www.douyin.com/video/7652233012264758464',  # 二道贩
        'https://www.douyin.com/video/7647484654794396879',  # 30秒揭秘
    ]

    results = []
    for vurl in video_urls:
        print(f'\n=== Visiting: {vurl} ===')
        page.goto(vurl, wait_until='domcontentloaded', timeout=20000)
        page.wait_for_timeout(4000)

        # Get all text on the page
        text = page.evaluate("document.body.innerText")
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # Look for tags/hashtags in the description area
        for line in lines[:50]:
            if any(kw in line for kw in ['#', '标签', '话题', 'tag', '描述', '简介']):
                print(f'TAG_LINE: {line[:150]}')

        # Try to extract hashtags from the full text
        hashtags = set()
        for line in lines[:80]:
            # Extract all #xxx patterns
            import re
            tags_found = re.findall(r'#[^\s#]+', line)
            for t in tags_found:
                hashtags.add(t)

        if hashtags:
            print(f'FOUND TAGS: {", ".join(hashtags)}')

        results.append({'url': vurl, 'tags': list(hashtags), 'first_lines': lines[:30]})

    browser.close()

# Save results
with open(r'C:\Users\Administrator\Desktop\ahang_tags.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print('\nSaved to ahang_tags.json')
