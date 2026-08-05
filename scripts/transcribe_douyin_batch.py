# -*- coding: utf-8 -*-
"""Transcribe a downloaded Douyin account with one reused faster-whisper model — GPU优先."""
import argparse
import json
import os
import sys
from datetime import datetime

from faster_whisper import WhisperModel

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from utils.gpu_config import get_device_config


def main(manifest_path, output_dir, model_size="small"):
    os.makedirs(output_dir, exist_ok=True)
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    device, compute_type = get_device_config()
    device_label = "GPU" if device == "cuda" else "CPU"
    print(f"🧠 [Whisper] 加载模型: {model_size} ({device_label})", flush=True)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    rows = []
    videos = manifest.get("videos", [])
    for index, item in enumerate(videos, 1):
        video_id = item["video_id"]
        output_path = os.path.join(output_dir, f"{video_id}.md")
        row = {"video_id": video_id, "url": item.get("url", ""), "title": item.get("title", ""), "transcript_path": output_path}
        try:
            segments, info = model.transcribe(item["local_video"], language="zh", beam_size=5, vad_filter=True, vad_parameters={"min_silence_duration_ms": 500})
            parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    parts.append(f"[{segment.start:07.2f} - {segment.end:07.2f}] {text}")
            transcript = "\n".join(parts).strip()
            content = "\n".join([
                "---",
                f"title: {item.get('title', '').replace(chr(10), ' ')}",
                f"source_url: {item.get('url', '')}",
                f"video_id: {video_id}",
                "source_type: 抖音公开作品",
                "transcript_type: 本地 ASR 逐字稿（未经人工校对）",
                f"asr_engine: faster-whisper/{model_size}",
                f"transcribed_at: {datetime.now().isoformat(timespec='seconds')}",
                "---",
                "",
                "# 逐字稿",
                "",
                transcript or "（未识别到有效语音）",
                "",
            ])
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(content)
            row.update({"status": "ok", "language": getattr(info, "language", "zh"), "duration": getattr(info, "duration", 0), "characters": len(transcript)})
        except Exception as exc:
            row.update({"status": "error", "error": str(exc)[:500]})
        rows.append(row)
        print(f"[{index:02d}/{len(videos)}] {video_id} {row['status']}", flush=True)
    output = {"account": manifest.get("account"), "transcribed_at": datetime.now().isoformat(timespec="seconds"), "model": model_size, "videos": rows}
    out_manifest = os.path.join(output_dir, "transcript_manifest.json")
    with open(out_manifest, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"manifest": out_manifest, "total": len(rows), "ok": sum(x.get('status') == 'ok' for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="small")
    args = parser.parse_args()
    main(args.manifest, args.output_dir, args.model)
