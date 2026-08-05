#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信息采集官 · 统一流水线入口（含多级兜底降级）
============================================
一条命令完成: 链接 → 识别平台 → 抓取 → 转录 → Obsidian
每步失败/超时自动降级到兜底方案。

用法:
  python scripts/collector.py pipeline <链接>              全自动流水线
  python scripts/collector.py pipeline <链接> --no-fallback 禁用兜底
  python scripts/collector.py pipeline <链接> --dry-run     预览降级链
  python scripts/collector.py pipeline <文件路径>           本地文件直接转录
  python scripts/collector.py transcribe <文件>             单文件转录
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# 路径配置
# ============================================================
TOOLKIT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = TOOLKIT_DIR / "scripts"
DOWNLOADS_DIR = TOOLKIT_DIR / "downloads"
OBSIDIAN_VAULT = Path("D:/知识库/知识库")
OBSIDIAN_TARGET = OBSIDIAN_VAULT / "05_内容生产库/三金AI实验室_30天万粉作战计划/逐字稿"

for d in [DOWNLOADS_DIR, OBSIDIAN_TARGET]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# 日志
# ============================================================
def log(icon, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {icon} {msg}", flush=True)

# ============================================================
# 链接识别
# ============================================================
LINK_PATTERNS = [
    ("抖音",   re.compile(r'https?://(?:www\.)?(?:douyin\.com/video/\d+|v\.douyin\.com/[\w\-]+)')),
    ("B站",    re.compile(r'https?://(?:www\.)?bilibili\.com/video/BV[\w]+')),
    ("YouTube",re.compile(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w\-]+')),
    ("小红书", re.compile(r'https?://(?:www\.)?xiaohongshu\.com/\S+')),
    ("快手",   re.compile(r'https?://(?:www\.)?kuaishou\.com/\S+')),
    ("视频号", re.compile(r'https?://(?:www\.)?weixin\.qq\.com/sph/[\w]+')),
]

MEDIA_EXTENSIONS = {".mp4", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
                    ".mov", ".avi", ".mkv", ".webm", ".amr", ".opus", ".wmv"}

def detect(input_text: str):
    p = Path(input_text.strip().strip('"'))
    if p.exists() and p.suffix.lower() in MEDIA_EXTENSIONS:
        return "本地文件", input_text.strip().strip('"')
    for name, pat in LINK_PATTERNS:
        m = pat.search(input_text)
        if m:
            return name, m.group(0)
    return None, None

# ============================================================
# 子进程执行
# ============================================================
def run_py(script_name, *args, timeout=120):
    cmd = [sys.executable, str(SCRIPTS_DIR / script_name)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=str(TOOLKIT_DIR))

def run_cmd(*args, timeout=120):
    return subprocess.run(list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=str(TOOLKIT_DIR))

# ============================================================
# 兜底降级引擎
# ============================================================

class StepFailed(Exception):
    """单步失败（非致命，触发降级）"""
    pass

class StepTimeout(Exception):
    """单步超时（非致命，触发降级）"""
    pass

def try_step(label: str, fn: Callable[[], Any], timeout: int) -> Any:
    """
    执行单个步骤，带独立超时。
    成功返回结果，失败/超时抛 StepFailed/StepTimeout → 触发降级。
    """
    import threading

    result_holder = {"value": None, "error": None, "done": False}

    def _run():
        try:
            result_holder["value"] = fn()
            result_holder["done"] = True
        except Exception as e:
            result_holder["error"] = e
            result_holder["done"] = True

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if not result_holder["done"]:
        # 超时 — 线程可能还在跑，但我们已经不关心了
        log("⏰", f"[{label}] 超时 ({timeout}秒) → 触发降级")
        raise StepTimeout(f"{label} 超时 ({timeout}s)")

    if result_holder["error"]:
        err_msg = str(result_holder["error"])[:200]
        log("⚠️", f"[{label}] 失败: {err_msg} → 触发降级")
        raise StepFailed(f"{label}: {err_msg}")

    result = result_holder["value"]
    if result is None or (isinstance(result, dict) and not result.get("transcript")):
        log("⚠️", f"[{label}] 返回空结果 → 触发降级")
        raise StepFailed(f"{label}: 空结果")

    log("✅", f"[{label}] 成功")
    return result

def run_fallback_chain(chain_name: str, steps: list[dict]) -> dict:
    """
    按顺序执行降级链，任意一步成功即返回。

    steps = [
        {"label": "Chrome CDP 直取", "fn": lambda: ..., "timeout": 60},
        {"label": "yt-dlp + Whisper", "fn": lambda: ..., "timeout": 600},
        ...
    ]

    全部失败 → 返回 {"transcript": None, "error": "...", "tried": [...]}
    """
    tried = []
    total = len(steps)

    for i, step in enumerate(steps):
        label = step["label"]
        timeout = step.get("timeout", 300)
        is_last = (i == total - 1)

        log("🔄", f"策略 {i+1}/{total}: {label}" + (" [最后兜底]" if is_last else ""))
        tried.append(label)

        try:
            result = try_step(label, step["fn"], timeout)
            result["_strategy"] = label
            result["_chain"] = chain_name
            result["_tried"] = tried
            result["_step_index"] = i + 1
            return result
        except (StepFailed, StepTimeout):
            continue

    # 全部失败
    return {
        "transcript": None,
        "platform": "",
        "url": "",
        "engine": "全部策略失败",
        "_strategy": "无",
        "_chain": chain_name,
        "_tried": tried,
        "_step_index": -1,
    }

# ============================================================
# 底层操作函数（每个都是独立可重试的单元）
# ============================================================

# ── 逐字稿质量校验 ──

# CDP 从抖音播放器读到的是「字幕」，不一定是真正的逐字稿。
# 以下情况判定为"不合格"，应立即触发降级到下载+本地转录：
#   · 字数太少（< 50 个中文字符）→ 可能只有标题/简介
#   · 全是时间戳无正文 → 字幕解析失败
#   · 中文占比过低 → 可能是乱码或纯符号
#   · 像视频文案描述而非对话内容 → 没有实际字幕数据

def _validate_transcript_quality(text: str, source: str = "CDP") -> tuple[bool, str]:
    """
    校验转录文本质量。返回 (合格, 原因)。
    source: "CDP" | "whisper" | "paraformer"
    """
    if not text or not text.strip():
        return False, "文本为空"

    text = text.strip()

    # 1. 统计有意义的中文字符
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    total_chars = len(text)

    # CDP 字幕：至少需要 50 个汉字才算合格逐字稿
    if source == "CDP" and chinese_chars < 50:
        return False, f"中文字符过少 ({chinese_chars}字)，可能不是逐字稿而是视频简介"

    # 所有来源：至少 20 个汉字
    if chinese_chars < 20:
        return False, f"中文字符过少 ({chinese_chars}字)"

    # 2. 中文占比：至少 30% 是中文（排除纯符号/乱码）
    if total_chars > 0 and chinese_chars / total_chars < 0.15:
        return False, f"中文占比过低 ({chinese_chars}/{total_chars})"

    # 3. CDP 特殊检查：是否像"视频文案"而非"对话字幕"
    if source == "CDP":
        # 真正的字幕通常比较口语化，有多行
        lines = [l for l in text.split('\n') if l.strip()]
        # 如果只有1-2行，可能是视频描述被误读为字幕
        if len(lines) <= 2 and chinese_chars < 100:
            return False, f"行数过少 ({len(lines)}行)，疑似视频简介而非逐字稿"

        # 如果内容看起来像 hashtag 堆砌
        hashtag_count = len(re.findall(r'#\w+', text))
        if hashtag_count > 5 and chinese_chars < 200:
            return False, f"包含大量话题标签 ({hashtag_count}个)，疑似视频简介"

    return True, "ok"

# ── 抖音 CDP ──

def _douyin_cdp_extract(url: str) -> dict | None:
    """
    Chrome CDP → dytranscript.py → 返回 {transcript, author, desc}
    提取后自动校验质量，不合格立即抛异常触发降级到 Whisper。
    """
    log("🎯", "  Chrome CDP 读取抖音字幕...")
    r = run_py("dytranscript.py", url, timeout=90)
    if r.returncode != 0:
        raise RuntimeError(f"dytranscript 返回非零: {r.stderr[:200]}")

    stdout = r.stdout
    author, desc, full_text = "", "", ""

    for line in stdout.split("\n"):
        if "👤" in line:
            author = line.split("👤")[-1].strip()

    out_dir = Path.home() / ".dytranscript_output"
    if out_dir.exists():
        files = sorted(out_dir.glob("dy_*.txt"), key=os.path.getmtime, reverse=True)
        if files:
            content = files[0].read_text(encoding="utf-8")
            m = re.search(r'逐字稿:\n([\s\S]+)', content)
            if m:
                full_text = m.group(1).strip()
            dm = re.search(r'文案:\n([\s\S]*?)(?:\n\n逐字稿|$)', content)
            if dm:
                desc = dm.group(1).strip()

    if not full_text:
        segs = re.findall(r'\[\d{2}:\d{2}\]\s+(.+)', stdout)
        full_text = "".join(segs) if segs else stdout.strip()

    if not full_text or len(full_text.strip()) < 10:
        raise RuntimeError("CDP 提取的文本过短或为空")

    # ★ 质量校验：不合格 → 抛异常触发降级到 yt-dlp + Whisper
    ok, reason = _validate_transcript_quality(full_text, source="CDP")
    if not ok:
        log("🚨", f"CDP 字幕质量不合格: {reason}")
        log("🔄", "  → 自动降级到 下载视频 + 本地 Whisper 转录")
        raise StepFailed(f"CDP 字幕质量不合格: {reason}")

    log("📋", f"  CDP 字幕质量合格: {len(re.findall(r'[一-鿿]', full_text))}个汉字 / {len(full_text)}字符")
    return {
        "transcript": full_text, "author": author, "desc": desc,
        "platform": "抖音", "url": url, "engine": "Chrome CDP (抖音字幕)",
    }

def _douyin_cdp_with_launch(url: str) -> dict | None:
    """自动启动 Chrome CDP 再重试"""
    log("🔧", "  尝试自动启动 Chrome 远程调试...")
    # 尝试启动 Chrome
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for cp in chrome_paths:
        if Path(cp).exists():
            subprocess.Popen(
                [cp, "--remote-debugging-port=9222",
                 "--user-data-dir=" + str(TOOLKIT_DIR / ".chrome_cdp_profile")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(3)  # 等待 Chrome 启动
            log("🔧", f"  Chrome 已启动，重试 CDP...")
            break
    return _douyin_cdp_extract(url)

# ── yt-dlp 下载 ──

def _ytdlp_download(url: str, cookie_source: str | None = None,
                    audio_only: bool = False) -> Path:
    """下载视频，返回本地文件路径"""
    ts = int(time.time() * 1000)
    out_tmpl = str(DOWNLOADS_DIR / f"%(id)s_{ts}.%(ext)s")

    fmt = "bestaudio/best" if audio_only else "bestvideo*+bestaudio/best"
    args = ["yt-dlp", "-f", fmt, "-o", out_tmpl, "--no-playlist",
            "--socket-timeout", "30", "--retries", "3"]
    if audio_only:
        args += ["--extract-audio", "--audio-format", "mp3"]
    else:
        args += ["--merge-output-format", "mp4"]
    if cookie_source:
        args += ["--cookies-from-browser", cookie_source]
    args.append(url)

    r = run_cmd(*args, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp 返回非零: {r.stderr[:200]}")

    files = sorted(DOWNLOADS_DIR.glob(f"*_{ts}*"), key=os.path.getmtime, reverse=True)
    if not files:
        raise RuntimeError("yt-dlp 运行完成但未找到下载文件")
    return files[0]

# ── Whisper 转录 ──

def _whisper_transcribe(video_path: Path, model: str = "base") -> str:
    """调用 transcribe_local.py"""
    r = run_py("transcribe_local.py", str(video_path),
               "--engine", "whisper", "--model", model, "--lang", "zh",
               timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"Whisper 返回非零: {r.stderr[:200]}")

    # 从 stdout 提取文本
    text = r.stdout.strip()
    if text:
        return text

    # 兜底：读默认输出文件
    txt_file = TOOLKIT_DIR / "transcript.txt"
    if txt_file.exists():
        text = txt_file.read_text(encoding="utf-8").strip()
        if text:
            return text

    raise RuntimeError("Whisper 转录结果为空")

# ── Paraformer 在线 API ──

def _paraformer_transcribe(video_or_audio: Path) -> str:
    """调用 Paraformer 在线 API（阿里百炼，中文最准）"""
    import dashscope
    from dotenv import load_dotenv
    load_dotenv(TOOLKIT_DIR / ".env")

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY 未配置")

    dashscope.api_key = api_key
    api_base = os.environ.get("DASHSCOPE_API_BASE")
    if api_base:
        dashscope.base_http_api_url = api_base

    # 如果是视频，先提取音频
    audio_path = str(video_or_audio)
    if video_or_audio.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"}:
        temp_wav = video_or_audio.with_suffix(".temp_para.wav")
        r = subprocess.run(
            ["ffmpeg", "-i", str(video_or_audio), "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", "-y", str(temp_wav)],
            capture_output=True, timeout=120,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg 提取音频失败: {r.stderr[:200]}")
        audio_path = str(temp_wav)

    file_size_mb = Path(audio_path).stat().st_size / (1024 * 1024)
    if file_size_mb > 50:
        raise RuntimeError(f"文件过大 ({file_size_mb:.1f}MB)，Paraformer 不支持")

    from dashscope.audio.asr import Recognition
    recognition = Recognition(
        model='paraformer-v2', format='wav',
        sample_rate=16000, language='zh-CN',
    )
    result = recognition.call(open(audio_path, 'rb').read())

    if hasattr(result, 'output') and result.output:
        text = result.output.text if hasattr(result.output, 'text') else str(result.output)
        if text:
            return text

    raise RuntimeError("Paraformer 返回空结果")

# ============================================================
# 降级链定义（每个平台一条链）
# ============================================================

def build_douyin_chain(url: str, model: str = "base") -> list[dict]:
    """抖音降级链：CDP + 质量校验 → 自动启动Chrome → yt-dlp+Whisper → 仅音频+tiny → Paraformer"""
    return [
        {
            "label": "Chrome CDP 直取 + 质量校验 (最快~20秒，但字幕≠逐字稿需验证)",
            "timeout": 90,
            "fn": lambda: _douyin_cdp_extract(url),
        },
        {
            "label": "自动启动 Chrome + CDP 重试 + 质量校验",
            "timeout": 120,
            "fn": lambda: _douyin_cdp_with_launch(url),
        },
        {
            "label": f"yt-dlp 下载完整视频 → Whisper/{model} GPU 转录 (真正的逐字稿)",
            "timeout": 600,
            "fn": lambda: _handle_download_then_whisper(url, "抖音", model),
        },
        {
            "label": "yt-dlp 仅下载音频 → Whisper/tiny 快速转录",
            "timeout": 300,
            "fn": lambda: _handle_download_then_whisper(url, "抖音", "tiny", audio_only=True),
        },
        {
            "label": "yt-dlp 下载 → Paraformer 在线 API (阿里百炼，最后兜底)",
            "timeout": 300,
            "fn": lambda: _handle_download_then_paraformer(url, "抖音"),
        },
    ]

def build_generic_chain(url: str, platform: str, model: str = "base") -> list[dict]:
    """通用平台降级链：yt-dlp+Whisper → cookie重试 → 仅音频+tiny → Paraformer"""
    return [
        {
            "label": f"yt-dlp 下载完整视频 → Whisper/{model} GPU 转录",
            "timeout": 600,
            "fn": lambda: _handle_download_then_whisper(url, platform, model),
        },
        {
            "label": f"yt-dlp (Chrome cookie) → Whisper/{model}",
            "timeout": 600,
            "fn": lambda: _handle_download_then_whisper(url, platform, model, cookie="chrome"),
        },
        {
            "label": "yt-dlp 仅下载音频 → Whisper/tiny 快速转录",
            "timeout": 300,
            "fn": lambda: _handle_download_then_whisper(url, platform, "tiny", audio_only=True),
        },
        {
            "label": "yt-dlp 下载 → Paraformer 在线 API (最后兜底)",
            "timeout": 300,
            "fn": lambda: _handle_download_then_paraformer(url, platform),
        },
    ]

def build_local_chain(file_path: str, model: str = "base") -> list[dict]:
    """本地文件降级链：Whisper GPU → Whisper tiny → Paraformer 在线"""
    fp = Path(file_path)
    return [
        {
            "label": f"Whisper/{model} GPU 本地转录 (离线，首选)",
            "timeout": 600,
            "fn": lambda: {
                "transcript": _whisper_transcribe(fp, model),
                "platform": "本地文件", "url": file_path,
                "engine": f"faster-whisper/{model}",
            },
        },
        {
            "label": "Whisper/tiny 快速转录 (离线，轻量兜底)",
            "timeout": 300,
            "fn": lambda: {
                "transcript": _whisper_transcribe(fp, "tiny"),
                "platform": "本地文件", "url": file_path,
                "engine": "faster-whisper/tiny",
            },
        },
        {
            "label": "Paraformer 在线 API (阿里百炼，中文最准，需联网)",
            "timeout": 180,
            "fn": lambda: {
                "transcript": _paraformer_transcribe(fp),
                "platform": "本地文件", "url": file_path,
                "engine": "Paraformer (在线API)",
            },
        },
    ]

# ── 下载+转录的组合包装函数（供降级链 lambda 调用）──

def _handle_download_then_whisper(url: str, platform: str, model: str,
                                  cookie: str | None = None,
                                  audio_only: bool = False) -> dict:
    """下载视频 + Whisper 转录"""
    video_file = _ytdlp_download(url, cookie_source=cookie, audio_only=audio_only)
    engine_label = f"faster-whisper/{model}"
    if audio_only:
        engine_label += " (仅音频)"
    if cookie:
        engine_label += f" (cookie={cookie})"
    transcript = _whisper_transcribe(video_file, model)
    try:
        video_file.unlink()
    except Exception:
        pass
    return {
        "transcript": transcript, "author": "", "desc": "",
        "platform": platform, "url": url, "engine": engine_label,
    }

def _handle_download_then_paraformer(url: str, platform: str) -> dict:
    """下载视频 + Paraformer 在线转录"""
    video_file = _ytdlp_download(url, audio_only=True)
    transcript = _paraformer_transcribe(video_file)
    try:
        video_file.unlink()
    except Exception:
        pass
    return {
        "transcript": transcript, "author": "", "desc": "",
        "platform": platform, "url": url, "engine": "Paraformer (在线API)",
    }

# ============================================================
# Obsidian 保存
# ============================================================
def save_to_obsidian(result: dict) -> Path:
    now = datetime.now()
    platform = result.get("platform", "未知")
    author = result.get("author", "").strip()
    url = result.get("url", "")
    title = result.get("desc", "").strip() or f"{platform}视频逐字稿"

    safe = (author or platform).replace("/", "_").replace("\\", "_")[:30]
    safe = re.sub(r'[\\/:*?"<>|]', '_', safe)
    fname = f"{platform}_{safe}_{now.strftime('%Y%m%d_%H%M')}.md"
    fpath = OBSIDIAN_TARGET / fname

    transcript_label = "字幕逐字稿" if "CDP" in result.get("engine", "") else "逐字稿"

    strategy_info = ""
    if result.get("_tried") and len(result["_tried"]) > 1:
        tried_list = " → ".join(result["_tried"])
        strategy_info = f"fallback_chain: {tried_list}\n"

    md = f"""---
title: "{title}"
platform: {platform}
source: {url}
date: {now.strftime('%Y-%m-%d')}
created: {now.strftime('%Y-%m-%d %H:%M')}
engine: {result.get('engine', '?')}
{strategy_info}tags:
  - 逐字稿
  - {platform}
---

# {title}

> **来源**: {url}
> **平台**: {platform}
> **引擎**: {result.get('engine', '?')}
> **日期**: {now.strftime('%Y-%m-%d %H:%M')}
{f'''> **降级链**: {result['_tried']}''' if len(result.get('_tried', [])) > 1 else ''}

---

## {transcript_label}

{result['transcript']}
"""
    fpath.write_text(md, encoding="utf-8")
    log("📝", f"已保存 Obsidian: {fname}")
    return fpath

# ============================================================
# 命令实现
# ============================================================

def cmd_pipeline(args):
    input_text = args.input
    model = getattr(args, 'model', 'base')
    no_fallback = getattr(args, 'no_fallback', False)

    log("🚀", "信息采集官 · 全自动流水线")
    log("📎", f"输入: {input_text[:80]}")

    # 1. 识别
    platform, target = detect(input_text)
    if not platform:
        log("❌", f"无法识别: {input_text}")
        log("💡", "支持的链接: 抖音/B站/YouTube/小红书/快手/视频号")
        log("💡", "也支持本地文件: mp4/mp3/wav/mov/mkv 等")
        sys.exit(1)

    log("🔍", f"识别为: {platform}")

    # 2. 构建降级链
    if platform == "抖音":
        chain = build_douyin_chain(target, model)
    elif platform == "本地文件":
        chain = build_local_chain(target, model)
    else:
        chain = build_generic_chain(target, platform, model)

    if no_fallback:
        chain = chain[:1]  # 只保留第一条策略
        log("⚠️", "已禁用兜底降级 (--no-fallback)，仅使用主策略")

    # 3. 预览模式
    if args.dry_run:
        log("🔍", "[预览模式] 降级链:")
        for i, step in enumerate(chain):
            flag = "主策略" if i == 0 else f"兜底 {i}"
            log("🔍", f"  {i+1}. [{flag}] {step['label']} (超时: {step['timeout']}秒)")
        log("🔍", f"  → 最终保存到: {OBSIDIAN_TARGET}")
        return

    # 4. 执行降级链
    start = time.time()
    chain_name = f"{platform}采集流水线"
    result = run_fallback_chain(chain_name, chain)

    if not result or not result.get("transcript"):
        elapsed = time.time() - start
        log("❌", f"所有策略均失败 ({elapsed:.0f}秒)")
        log("📋", f"尝试过的策略: {' → '.join(result.get('_tried', []))}")
        sys.exit(1)

    elapsed = time.time() - start
    strategy = result.get("_strategy", "?")
    step_idx = result.get("_step_index", "?")
    log("✅", f"转录完成: {len(result['transcript'])} 字 / {elapsed:.0f}秒")
    log("🏆", f"成功策略: [{step_idx}] {strategy}")

    # 5. 保存
    obs_path = save_to_obsidian(result)

    # 6. 摘要
    print()
    print("=" * 60)
    print(f"  ✅ 流水线完成")
    print(f"  平台: {result.get('platform', '?')}")
    print(f"  引擎: {result.get('engine', '?')}")
    print(f"  字数: {len(result['transcript'])} 字")
    print(f"  耗时: {elapsed:.0f} 秒")
    if result.get("_tried") and len(result["_tried"]) > 1:
        print(f"  降级: {' → '.join(result['_tried'])}")
    print(f"  保存: {obs_path}")
    print("=" * 60)
    print()
    print(result['transcript'][:500])
    if len(result['transcript']) > 500:
        print(f"... (共 {len(result['transcript'])} 字)")

def cmd_transcribe(args):
    if not Path(args.file).exists():
        log("❌", f"文件不存在: {args.file}")
        sys.exit(1)

    model = getattr(args, 'model', 'base')
    chain = build_local_chain(args.file, model)
    result = run_fallback_chain("单文件转录", chain)

    if not result or not result.get("transcript"):
        log("❌", "所有转录策略均失败")
        sys.exit(1)

    log("✅", f"转录完成: {len(result['transcript'])} 字 "
              f"(策略: {result.get('_strategy', '?')})")

    if args.output:
        Path(args.output).write_text(result['transcript'], encoding="utf-8")
        log("📝", f"已保存: {args.output}")
    else:
        print(result['transcript'])

def cmd_sync(args):
    json_file = args.file
    if not Path(json_file).exists():
        log("❌", f"文件不存在: {json_file}")
        sys.exit(1)

    sync_js = SCRIPTS_DIR / "sync-to-feishu.js"
    if sync_js.exists():
        r = subprocess.run(
            ["node", str(sync_js), f"--account-file={json_file}"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120, cwd=str(TOOLKIT_DIR),
        )
        print(r.stdout)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
    else:
        log("❌", "sync-to-feishu.js 不存在")

def cmd_detect(args):
    platform, target = detect(args.input)
    if platform:
        print(f"平台: {platform}")
        print(f"目标: {target}")
        # 同时展示降级链
        print()
        print("降级链预览:")
        if platform == "抖音":
            chain = build_douyin_chain(target)
        elif platform == "本地文件":
            chain = build_local_chain(target)
        else:
            chain = build_generic_chain(target, platform)
        for i, step in enumerate(chain):
            flag = "主策略" if i == 0 else f"兜底 {i}"
            print(f"  {i+1}. [{flag}] {step['label']}")
    else:
        print("无法识别")

# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="信息采集官 · 统一流水线（含多级兜底）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
默认值:
  转录引擎: faster-whisper (本地GPU离线, --model base)
  抖音平台: Chrome CDP 优先 → 质量不合格自动降级到下载+Whisper
  其他平台: yt-dlp 下载 → Whisper GPU 转录

示例:
  python collector.py pipeline <链接>              全自动流水线
  python collector.py pipeline <链接> --dry-run     预览降级链
  python collector.py pipeline <链接> --no-fallback 仅主策略，不兜底
  python collector.py pipeline <文件> --model medium 指定模型
  python collector.py transcribe 视频.mp4            单文件转录
  python collector.py detect <链接>                 识别+展示降级链

降级链示例 (抖音):
  策略1: Chrome CDP 直取 + 质量校验 (~20秒, 字幕≠逐字稿时自动降级)
    ↓ 超时/失败/质量不合格
  策略2: 自动启动 Chrome + CDP 重试 + 质量校验
    ↓ 超时/失败
  策略3: yt-dlp 下载完整视频 → Whisper GPU 转录 (真正的逐字稿)
    ↓ 超时/失败
  策略4: yt-dlp 仅音频 → Whisper tiny 快速转录
    ↓ 超时/失败
  策略5: yt-dlp 下载 → Paraformer 在线 API
        """)

    sub = parser.add_subparsers(dest="command", help="子命令")

    p_pipe = sub.add_parser("pipeline", help="全自动流水线: 链接 → 识别 → 转录 → Obsidian")
    p_pipe.add_argument("input", help="视频链接 或 本地文件路径")
    p_pipe.add_argument("--model", "-m", default="base",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper 模型 (默认 base)")
    p_pipe.add_argument("--dry-run", action="store_true", help="预览降级链，不实际执行")
    p_pipe.add_argument("--no-fallback", action="store_true",
                        help="禁用兜底降级，仅使用主策略")

    p_trans = sub.add_parser("transcribe", help="单文件转录（含兜底）")
    p_trans.add_argument("file", help="音视频文件路径")
    p_trans.add_argument("--model", "-m", default="base",
                         choices=["tiny", "base", "small", "medium", "large-v3"])
    p_trans.add_argument("--output", "-o", help="输出文件路径")

    p_sync = sub.add_parser("sync", help="同步 JSON 到飞书")
    p_sync.add_argument("--file", "-f", required=True, help="videos.json 路径")
    p_sync.add_argument("--platform", "-p", default="douyin", help="平台标识")

    p_det = sub.add_parser("detect", help="仅识别链接平台 + 展示降级链")
    p_det.add_argument("input", help="视频链接")

    args = parser.parse_args()

    if args.command == "pipeline":
        cmd_pipeline(args)
    elif args.command == "transcribe":
        cmd_transcribe(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "detect":
        cmd_detect(args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
