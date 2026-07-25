#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音逐字稿提取器 — CDP 连接模式

用法:
  第1步：关掉所有 Chrome 窗口
  第2步：在「运行」(Win+R) 粘贴下面这行并回车：
    chrome.exe --remote-debugging-port=9222

  第3步：在打开的 Chrome 中登录抖音（如果没登录）
  第4步：运行本脚本：
    python dytranscript.py "https://www.douyin.com/video/xxxxx"
"""

import asyncio, json, os, re, sys, socket
from datetime import datetime
from playwright.async_api import async_playwright

OUTPUT_DIR = os.path.expanduser("~/.dytranscript_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

def p(msg):
    try: print(msg)
    except UnicodeEncodeError: print(msg.encode("utf-8", errors="replace").decode("gbk", errors="ignore"))

def extract_video_id(text):
    m = re.search(r'douyin\.com/video/(\d+)', text)
    if m: return m.group(1)
    m = re.search(r'v\.douyin\.com/([a-zA-Z0-9_-]+)', text)
    if m: return f"short:{m.group(1)}"
    return None

def fmt_ts(s): m, s = divmod(int(s), 60); return f"{m:02d}:{s:02d}"

def extract(detail):
    r = {"author":(detail.get("author") or {}).get("nickname",""), "desc":detail.get("desc",""),
         "create_time":"", "stats":{}, "hashtags":[], "video_text":[], "has_captions":False}
    s = detail.get("statistics") or {}
    r["stats"] = {"likes":s.get("digg_count",0),"comments":s.get("comment_count",0),"favorites":s.get("collect_count",0)}
    ct = detail.get("create_time",0)
    if ct: r["create_time"] = datetime.fromtimestamp(ct).strftime("%m-%d %H:%M")
    for te in (detail.get("text_extra") or []):
        if te.get("hashtag_name"): r["hashtags"].append(te["hashtag_name"])
    vt = detail.get("video_text") or []
    if vt:
        r["has_captions"] = True
        for seg in vt: r["video_text"].append({"text":seg.get("text",""),"t":fmt_ts(seg.get("start_time",0))})
    return r

def output(result, url):
    p("="*55 + "\n🎬 抖音文案提取完成\n" + "="*55)
    if result["author"]: p(f"👤 {result['author']}")
    if result["create_time"]: p(f"🕐 {result['create_time']}")
    if result.get("stats"):
        s = result["stats"]; p(f"📊 👍{s['likes']}  💬{s['comments']}  ⭐{s['favorites']}")
    if result["hashtags"]: p(f"🏷 {'  '.join('#'+h for h in result['hashtags'])}")
    p(f"🔗 {url}")
    desc = result["desc"].strip()
    if desc: p(f"\n📝 文案描述:\n{'─'*40}\n{desc}")
    vt = result["video_text"]
    if vt:
        p(f"\n🎤 逐字稿 ({len(vt)} 条):\n{'─'*40}")
        ft = []
        for seg in vt: p(f"  [{seg['t']}] {seg['text']}"); ft.append(seg["text"])
        p(f"{'─'*40}\n\n📋 全文:\n{"".join(ft)}")
    elif not result["has_captions"]: p("\n💡 该视频没有自动字幕，只有文案描述。")
    p("="*55)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nm = re.sub(r'[\\/:*?"<>|]', '', result.get("author","dy"))[:16]
    fp = os.path.join(OUTPUT_DIR, f"dy_{nm}_{ts}.txt")
    with open(fp,"w",encoding="utf-8") as f:
        f.write(f"作者: {result['author']}\n链接: {url}\n\n")
        if desc: f.write(f"文案:\n{desc}\n\n")
        if vt:
            f.write("逐字稿:\n")
            for seg in vt: f.write(f"[{seg['t']}] {seg['text']}\n")
    p(f"\n💾 已保存: {fp}")

async def main():
    if len(sys.argv) < 2:
        p("用法:\n  python dytranscript.py <抖音链接>\n\n首次使用:\n  1. 关闭所有 Chrome\n  2. Win+R 输入: chrome.exe --remote-debugging-port=9222\n  3. 登录抖音\n  4. 运行本脚本")
        return
    input_text = " ".join(sys.argv[1:])
    video_id = extract_video_id(input_text)
    if not video_id: p("❌ 未识别到抖音链接"); return

    video_url = f"https://v.douyin.com/{video_id.split(':')[1]}/" if video_id.startswith("short:") else f"https://www.douyin.com/video/{video_id}"

    p("🚀 抖音逐字稿提取器\n" + f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🎯 {video_url}")

    # 检查端口
    port_ok = False
    for i in range(3):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1); r = s.connect_ex(('127.0.0.1', 9222)); s.close()
            if r == 0: port_ok = True; break
        except: pass
        await asyncio.sleep(1)

    if not port_ok:
        p("\n" + "!" * 50)
        p("需要先以调试模式启动 Chrome")
        p("!" * 50)
        p("\n请按以下步骤操作：")
        p("  ① 完全关闭所有 Chrome 窗口")
        p("  ② 按 Win+R，粘贴并回车：")
        p("     chrome.exe --remote-debugging-port=9222")
        p("  ③ 在打开的 Chrome 中登录抖音（如未登录）")
        p("  ④ 重新运行本命令即可")
        p("\n完成后直接重新运行即可，不需要再做其他操作。")
        return

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        p("\n检查登录...")
        await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)

        cookies = await ctx.cookies()
        logged_in = any(c.get("name") in ("sessionid","sid_guard","sid_tt") and c.get("value") for c in cookies)
        if not logged_in:
            p("⚠ 请在 Chrome 中登录抖音，然后重新运行本命令")
            return
        if not logged_in: p("❌ 未登录"); return
        p("✅ 已登录")

        # 短链解析
        if video_id.startswith("short:"):
            np = await ctx.new_page()
            await np.goto(video_url, wait_until="domcontentloaded", timeout=30000)
            m = re.search(r'douyin\.com/video/(\d+)', np.url)
            if m: video_id = m.group(1); video_url = np.url; p(f"  → 完整 ID: {video_id}")
            await np.close()

        # 提取
        detail_data = {}
        async def on_resp(resp):
            try:
                if "aweme/v1/web/aweme/detail/" in resp.url:
                    data = await resp.json()
                    if data.get("aweme_detail"): detail_data["detail"] = data["aweme_detail"]
            except: pass
        page.on("response", on_resp)
        p("\n打开视频页面...")
        await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        for _ in range(20):
            await page.wait_for_timeout(1000)
            if detail_data.get("detail"): break
        await page.wait_for_timeout(3000)

        if detail_data.get("detail"):
            output(extract(detail_data["detail"]), video_url)
        else:
            p("⚠ 未获取到视频数据（可能需要登录或视频不存在）")

        p("\n✅ 完成！Chrome 保持打开即可。")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: p("\n已取消")
    except Exception as e:
        p(f"\n❌ 错误: {e}")
        import traceback; traceback.print_exc()
