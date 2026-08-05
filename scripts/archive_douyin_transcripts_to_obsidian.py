# -*- coding: utf-8 -*-
"""Archive verified Douyin downloads and local ASR transcripts into Obsidian."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_title(value, video_id):
    value = re.sub(r"\s+", " ", (value or "")).strip()
    value = value.replace("/", "／").replace("\\", "＼")
    return value[:100] or f"抖音作品 {video_id}"


def transcript_body(path: Path):
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8-sig")
    marker = "# 逐字稿"
    if marker in text:
        text = text.split(marker, 1)[1]
    # Obsidian copy is a clean reading version; the raw ASR file remains beside it.
    text = re.sub(r"^\[\d{4,}:?\d{2}\.\d{2} - \d{4,}:?\d{2}\.\d{2}\]\s*", "", text, flags=re.M)
    text = re.sub(r"^\[\d+\.\d+ - \d+\.\d+\]\s*", "", text, flags=re.M)
    return text.strip()


def main(args):
    profile = read_json(Path(args.profile))
    downloads = read_json(Path(args.downloads))
    transcripts = read_json(Path(args.transcripts) / "transcript_manifest.json")
    transcript_map = {row["video_id"]: row for row in transcripts.get("videos", [])}
    vault_root = Path(args.vault_root)
    account_dir = vault_root / args.account
    account_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for item in downloads.get("videos", []):
        video_id = item["video_id"]
        trow = transcript_map.get(video_id, {})
        raw_path = Path(trow.get("transcript_path", ""))
        body = transcript_body(raw_path)
        title = safe_title(item.get("title"), video_id)
        note_path = account_dir / f"{video_id}.md"
        note = "\n".join([
            "---",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            f"account: {args.account}",
            f"video_id: {video_id}",
            f"source_url: {item.get('url', '')}",
            f"local_video: {item.get('local_video', '')}",
            f"raw_asr: {raw_path}",
            "source_type: 抖音公开作品",
            "transcript_type: 本地 ASR 逐字稿（未经人工校对）",
            f"asr_engine: faster-whisper/{transcripts.get('model', 'unknown')}",
            "---",
            "",
            f"# {title}",
            "",
            "## 逐字稿",
            "",
            body or "（未识别到有效语音）",
            "",
            "## 采集备注",
            "",
            f"- 原视频：[{video_id}]({item.get('url', '')})",
            f"- 原始 ASR 文件：`{raw_path}`",
            "- 本文已去除时间戳，保留原始 ASR 文件用于追溯。",
            "- 专有名词、数字和标点可能有识别误差；发布或引用前应回听原视频人工校对。",
            "",
        ])
        note_path.write_text(note, encoding="utf-8")
        rows.append({
            "video_id": video_id,
            "title": title,
            "source_url": item.get("url", ""),
            "local_video": item.get("local_video", ""),
            "obsidian_note": str(note_path),
            "asr_status": trow.get("status", "missing"),
        })

    display_count = profile.get("works_displayed")
    try:
        display_count = int(display_count) if display_count is not None else None
    except (TypeError, ValueError):
        display_count = None
    collected_count = len(rows)
    asr_count = sum(row["asr_status"] == "ok" for row in rows)
    captured_at = datetime.now().isoformat(timespec="seconds")
    coverage = f"{collected_count}/{display_count}" if display_count else str(collected_count)
    index_lines = [
        f"# {args.account}｜抖音逐字稿索引",
        "",
        "- 采集时间：" + captured_at,
        f"- 账号主页：{profile.get('profile_url', '')}",
        f"- 账号页显示作品数：{display_count if display_count is not None else '未读取到'}",
        f"- 本次已抓取作品：{collected_count}/{display_count if display_count is not None else collected_count}",
        f"- 本地 ASR 完成：{asr_count}/{collected_count}",
        "- 说明：这里的“逐字稿”是本地 faster-whisper ASR，未经人工逐句校对；原始带时间戳 ASR 与本地视频均保留在采集目录。",
    ]
    if display_count is not None and collected_count < display_count:
        index_lines += [
            f"- 覆盖边界：账号页显示 {display_count} 条，但当前会话只核验到 {collected_count} 条；剩余 {display_count - collected_count} 条的分页请求被抖音签名校验拦截，不能标记为已完成。",
        ]
    index_lines += ["", "## 逐条笔记", ""]
    index_lines += [f"- [[{row['video_id']}|{row['title']}]]" for row in rows]
    (account_dir / "00_账号索引.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    summary = {
        "account": args.account,
        "account_dir": str(account_dir),
        "display_count": display_count,
        "collected_count": collected_count,
        "asr_count": asr_count,
        "notes": len(rows),
        "captured_at": captured_at,
    }
    (account_dir / "collection_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--downloads", required=True)
    parser.add_argument("--transcripts", required=True)
    parser.add_argument("--vault-root", required=True)
    main(parser.parse_args())
