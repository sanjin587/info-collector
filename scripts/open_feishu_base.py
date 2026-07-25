"""Open 对标库 and extract data via browser"""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\Administrator\Desktop\信息采集官工具包')
from playwright.sync_api import sync_playwright

base_url = 'https://my.feishu.cn/base/GLnSb40iiaCiB3sHIX8c0ctfnxe'

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
    )
    page = browser.new_page(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36'
    )
    page.goto(base_url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(10000)

    text = page.evaluate("document.body.innerText")
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines[:100]:
        print(line)

    browser.close()
