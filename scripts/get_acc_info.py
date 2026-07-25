"""Extract account info from Douyin page"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\Administrator\Desktop\信息采集官工具包')
from playwright.sync_api import sync_playwright

account_url = 'https://www.douyin.com/user/MS4wLjABAAAAvKYbJjT5ZUprWELSNQjUxplXQ6CF9BuspkRufMtctFSa5iv-jIjPEWs_bzExERkK'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled','--no-sandbox'])
    page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36')
    page.goto(account_url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)

    text = page.evaluate("document.body.innerText")
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    for i, line in enumerate(lines[:80]):
        print(line)

    browser.close()
