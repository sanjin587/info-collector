#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 → 视频链接 → 逐字稿 → Obsidian  全自动流水线

调用信息采集官现有工具:
  dytranscript.py    → 抖音逐字稿 (Chrome CDP, 无需下载视频)
  transcribe_local.py → 本地 Whisper (非抖音平台兜底)
  sync_to_obsidian.py → Obsidian 归档

飞书回复用 lark-cli, 走 cmd.exe /c 包装避免中文编码问题
"""

import json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# === 路径 ===
SCRIPTS  = Path(__file__).resolve().parent.parent / "scripts"
DOWNLOADS = Path(__file__).resolve().parent / "downloads"
TXTS      = Path(__file__).resolve().parent / "transcripts"
OBSIDIAN  = Path("D:/知识库/知识库/05_内容生产库/三金AI实验室_30天万粉作战计划/逐字稿")

for d in [DOWNLOADS, TXTS, OBSIDIAN]:
    d.mkdir(parents=True, exist_ok=True)

# === 链接识别 ===
LINKS = [
    ("抖音",   re.compile(r'https?://(?:www\.)?(?:douyin\.com/video/\d+|v\.douyin\.com/[\w-]+)')),
    ("B站",    re.compile(r'https?://(?:www\.)?bilibili\.com/video/BV[\w]+')),
    ("YouTube",re.compile(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+')),
    ("视频号", re.compile(r'https?://(?:www\.)?weixin\.qq\.com/sph/[\w]+')),
    ("小红书", re.compile(r'https?://(?:www\.)?xiaohongshu\.com/\S+')),
    ("快手",   re.compile(r'https?://(?:www\.)?kuaishou\.com/\S+')),
]

def detect(text):
    for name, pat in LINKS:
        m = pat.search(text)
        if m: return name, m.group(0)
    return None, None

# === 飞书回复 ===
LARK_BIN = r"C:\Program Files\nodejs\lark-cli.cmd"

def lark(*args):
    """调 lark-cli, 用 cmd /c 包装, 返回 (ok, stdout)"""
    cmd = ["cmd.exe", "/c", LARK_BIN] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if r.returncode == 0:
            try: return True, json.loads(r.stdout)
            except: return True, r.stdout.strip()
        return False, r.stderr.strip()
    except Exception as e:
        return False, str(e)

def reply(msg_id, text):
    """回复飞书消息"""
    # 控制长度
    if len(text) > 2000:
        text = text[:1900] + "\n\n...完整内容已保存到 Obsidian"
    ok, out = lark("im", "+messages-reply", "--message-id", msg_id,
                    "--as", "bot", "--text", text, "--json")
    print(f"  reply -> {'OK' if ok else out[:100]}")

def send_file(chat_id, path):
    """发送文件附件"""
    ok, out = lark("im", "+messages-send", "--chat-id", chat_id,
                    "--as", "bot", "--file", str(path), "--json")
    print(f"  send_file -> {'OK' if ok else out[:100]}")

# === 抖音逐字稿 (信息采集官) ===
def douyin_transcript(url):
    """调用 dytranscript.py — Chrome CDP 直取字幕"""
    print(f"  🎯 dytranscript.py {url}")
    r = subprocess.run(
        ["python", str(SCRIPTS / "dytranscript.py"), url],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, cwd=str(SCRIPTS.parent)
    )
    if r.returncode != 0:
        print(f"  dytranscript 失败: {r.stderr[:200]}")
        return None, None

    out = r.stdout
    # 提取逐字稿
    lines = out.split("\n")
    author, desc, full_text = "", "", ""
    in_full = False
    ft = []
    for i, line in enumerate(lines):
        if "👤" in line: author = line.split("👤")[-1].strip()
        if "📝 文案描述" in line and i+2 < len(lines):
            desc = lines[i+2].strip() if lines[i+2].strip() != "─"*40 else ""
        if "📋 全文:" in line:
            ft.append(line.split("📋 全文:", 1)[-1].strip())
            in_full = True
        elif in_full and not line.startswith("=") and line.strip():
            ft.append(line.strip())

    if ft:
        full_text = "".join(ft)
    else:
        # 从逐字稿分段提取
        segs = []
        for line in lines:
            m = re.match(r'\s*\[(\d{2}:\d{2})\]\s+(.+)', line)
            if m: segs.append(m.group(2))
        if segs:
            full_text = "".join(segs)

    # 也读保存的文件
    output_dir = Path.home() / ".dytranscript_output"
    if output_dir.exists():
        files = sorted(output_dir.glob("dy_*.txt"), key=os.path.getmtime, reverse=True)
        if files:
            content = files[0].read_text(encoding="utf-8")
            m = re.search(r'逐字稿:\n([\s\S]+)', content)
            if m: full_text = m.group(1).strip()
            else: full_text = content.strip()

    info = {"author": author, "desc": desc, "platform": "抖音", "url": url}
    return full_text or out, info

# === 本地转写 (非抖音平台) ===
def local_transcript(video_path):
    """调用 transcribe_local.py"""
    print(f"  🎯 transcribe_local.py {video_path}")
    r = subprocess.run(
        ["python", str(SCRIPTS / "transcribe_local.py"),
         str(video_path), "--engine", "whisper", "--model", "base", "--lang", "zh"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600, cwd=str(SCRIPTS.parent)
    )
    # 查找输出文件
    txt_files = sorted(TXTS.glob("*逐字稿*.txt"), key=os.path.getmtime, reverse=True)
    if txt_files:
        return txt_files[0].read_text(encoding="utf-8").strip()
    return r.stdout.strip() or None

# === Obsidian 保存 ===
def save_obsidian(transcript, info):
    """保存逐字稿到 Obsidian"""
    now = datetime.now()
    safe = (info.get("author") or info["platform"])[:30]
    safe = re.sub(r'[\\/:*?"<>|]', '_', safe)
    fname = f"{info['platform']}_{safe}_{now.strftime('%Y%m%d_%H%M')}.md"
    fpath = OBSIDIAN / fname

    title = info.get('desc') or (info['platform'] + '视频逐字稿')
    md = f"""---
title: "{title}"
platform: {info['platform']}
source: {info['url']}
date: {now.strftime('%Y-%m-%d')}
tags:
  - 逐字稿
  - {info['platform']}
---

# {title}

> **来源**: {info['url']}
> **平台**: {info['platform']}

---

## 逐字稿

{transcript}
"""
    fpath.write_text(md, encoding="utf-8")
    print(f"  📝 Obsidian: {fname}")
    return fpath

# === 主处理 ===
def handle(msg_id, chat_id, text):
    platform, url = detect(text)
    if not url:
        return  # 不是视频链接

    print(f"\n{'='*50}")
    print(f"🎬 {platform}: {url}")
    reply(msg_id, f"🔍 收到{platform}链接，开始提取逐字稿...")

    transcript = None
    info = {"platform": platform, "url": url, "author": "", "desc": ""}

    if platform == "抖音":
        transcript, dinfo = douyin_transcript(url)
        if dinfo: info.update(dinfo)
    else:
        # yt-dlp 下载 → 本地转写
        print(f"  📥 yt-dlp {url}")
        r = subprocess.run(
            ["yt-dlp", "-f", "best", "-o",
             str(DOWNLOADS / f"%(id)s.%(ext)s"),
             "--no-playlist", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300
        )
        # 找最新下载文件
        videos = sorted(DOWNLOADS.glob("*.*"), key=os.path.getmtime, reverse=True)
        if videos:
            transcript = local_transcript(videos[0])
            try: videos[0].unlink()
            except: pass

    if not transcript:
        reply(msg_id, "❌ 逐字稿提取失败，请检查链接是否有效")
        return

    # 保存 Obsidian
    save_obsidian(transcript, info)

    # 回复结果
    preview = transcript[:300]
    reply(msg_id, f"✅ 逐字稿已生成 ({len(transcript)}字)\n\n{preview}...")

    # 长文本发文件
    if len(transcript) > 2000:
        txt_path = TXTS / f"{platform}_逐字稿_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        txt_path.write_text(transcript, encoding="utf-8")
        send_file(chat_id, txt_path)

# === 事件监听 ===
def listen():
    print("🚀 飞书 → 逐字稿 → Obsidian 流水线启动")
    print("   等待消息... Ctrl+C 停止\n")

    LARK_BIN = r"C:\Program Files\nodejs\lark-cli.cmd"
    proc = subprocess.Popen(
        [LARK_BIN, "event", "consume", "im.message.receive_v1", "--as", "bot"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace"
    )

    for line in proc.stdout:
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            evt = json.loads(line)
        except:
            continue

        if evt.get("message_type") != "text":
            continue

        msg_id = evt.get("message_id", "")
        chat_id = evt.get("chat_id", "")
        text = evt.get("content", "")
        if isinstance(text, str):
            try: text = json.loads(text).get("text", text)
            except: pass

        print(f"\n📩 [{evt.get('chat_type','?')}] {text[:80]}...")
        try:
            handle(msg_id, chat_id, text)
        except Exception as e:
            print(f"  ❌ 处理异常: {e}")
            reply(msg_id, f"❌ 处理出错: {e}")

if __name__ == "__main__":
    try: listen()
    except KeyboardInterrupt: print("\n已停止")
