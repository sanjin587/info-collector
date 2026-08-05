# -*- coding: utf-8 -*-
"""Archive a Xiaohongshu note and its local ASR transcript into Obsidian."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def clean_transcript(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    if "# 逐字稿" in text:
        text = text.split("# 逐字稿", 1)[1]
    text = re.sub(r"^\[\d+\.\d+ - \d+\.\d+\]\s*", "", text, flags=re.M)
    return text.strip()


def main(args):
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8-sig"))
    transcript_manifest = json.loads(Path(args.transcripts, "transcript_manifest.json").read_text(encoding="utf-8-sig"))
    transcript_map = {row["video_id"]: row for row in transcript_manifest.get("videos", [])}
    source_note = Path(args.source_note).read_text(encoding="utf-8-sig").strip() if args.source_note else ""
    out_dir = Path(args.vault_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in dataset.get("videos", []):
        video_id = item["video_id"]
        trow = transcript_map.get(video_id, {})
        raw_path = Path(trow.get("transcript_path", ""))
        transcript = clean_transcript(raw_path) if raw_path.exists() else "（未生成逐字稿）"
        title = item.get("title") or video_id
        note_path = out_dir / f"{video_id}.md"
        content = "\n".join([
            "---",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            f"platform: 小红书",
            f"author: {dataset.get('account', '')}",
            f"note_id: {video_id}",
            f"source_url: {item.get('url', '')}",
            f"local_video: {item.get('local_video', '')}",
            f"raw_asr: {raw_path}",
            "source_type: 小红书公开视频笔记",
            "transcript_type: 本地 ASR 逐字稿（未经人工校对）",
            f"asr_engine: faster-whisper/{transcript_manifest.get('model', 'unknown')}",
            f"archived_at: {datetime.now().isoformat(timespec='seconds')}",
            "---",
            "",
            f"# {title}",
            "",
            "## 原笔记信息",
            "",
            source_note or "（未保存页面文字摘要）",
            "",
            "## 视频逐字稿",
            "",
            transcript,
            "",
            "## 采集备注",
            "",
            "- 视频已下载到本地，并通过 FFmpeg 播放性检查。",
            "- 逐字稿为 faster-whisper 本地 ASR，已去除时间戳；原始带时间戳文件保留在采集目录。",
            "- 专有名词、数字、标点及少量口语可能存在识别误差，引用或发布前应回听原视频校对。",
            "",
        ])
        note_path.write_text(content, encoding="utf-8")
        rows.append({"note_id": video_id, "title": title, "obsidian_note": str(note_path), "transcript_status": trow.get("status", "missing")})
    index = "\n".join([
        f"# 小红书逐字稿｜{dataset.get('account', '')}",
        "",
        f"- 笔记：[[{rows[0]['note_id']}|{rows[0]['title']}]]" if rows else "- 无笔记",
        f"- 作者：{dataset.get('account', '')}",
        f"- 已下载并校验：{len(rows)} 条",
        f"- 本地 ASR：{sum(x['transcript_status'] == 'ok' for x in rows)}/{len(rows)} 条",
        "- 来源：小红书公开笔记；ASR 未经人工逐句校对。",
        "",
    ])
    (out_dir / "00_账号索引.md").write_text(index, encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "notes": len(rows), "asr_ok": sum(x['transcript_status'] == 'ok' for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--transcripts", required=True)
    parser.add_argument("--vault-dir", required=True)
    parser.add_argument("--source-note")
    main(parser.parse_args())
