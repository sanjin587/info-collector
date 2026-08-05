# -*- coding: utf-8 -*-
"""Faster resumable local ASR for a Douyin manifest — GPU优先, CPU兜底."""
import argparse
import json
import os
import sys
from datetime import datetime
from faster_whisper import WhisperModel

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from utils.gpu_config import get_device_config


def main(manifest_path, output_dir, model_size, device, compute_type):
    os.makedirs(output_dir, exist_ok=True)
    manifest = json.load(open(manifest_path, encoding="utf-8-sig"))
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    out_manifest = os.path.join(output_dir, "transcript_manifest.json")

    # ★ 断点续传：读取已有 manifest，跳过已完成项
    rows = []
    done_ids = set()
    if os.path.exists(out_manifest):
        try:
            prev = json.load(open(out_manifest, encoding="utf-8"))
            rows = prev.get("videos", [])
            done_ids = {r["video_id"] for r in rows if r.get("status") == "ok"}
            if done_ids:
                print(f"📋 断点续传: 已跳过 {len(done_ids)} 条已完成", flush=True)
        except Exception:
            pass

    videos = manifest.get("videos", [])
    for index, item in enumerate(videos, 1):
        video_id = item["video_id"]

        # 已完成则跳过
        if video_id in done_ids:
            print(f"[{index:02d}/{len(videos)}] {video_id} skipped (已转录)", flush=True)
            continue

        output_path = os.path.join(output_dir, f"{video_id}.md")
        row = {"video_id": video_id, "url": item.get("url", ""), "title": item.get("title", ""), "transcript_path": output_path}
        try:
            if os.path.exists(output_path) and os.path.getsize(output_path) > 200:
                row.update({"status": "ok", "reused": True, "characters": os.path.getsize(output_path)})
                print(f"[{index:02d}/{len(videos)}] {video_id} reused", flush=True)
                rows.append(row)
                _save_manifest(out_manifest, manifest, model_size, rows)
                continue
            segments, info = model.transcribe(
                item["local_video"], language="zh", beam_size=1, best_of=1,
                condition_on_previous_text=False, vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
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
                "---", "", "# 逐字稿", "", transcript or "（未识别到有效语音）", "",
            ])
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(content)
            row.update({"status": "ok", "language": getattr(info, "language", "zh"), "duration": getattr(info, "duration", 0), "characters": len(transcript)})
            print(f"[{index:02d}/{len(videos)}] {video_id} ok", flush=True)
        except Exception as exc:
            row.update({"status": "error", "error": str(exc)[:500]})
            print(f"[{index:02d}/{len(videos)}] {video_id} error", flush=True)
        rows.append(row)
        # ★ 每完成一条立即写 manifest（中断不丢进度）
        _save_manifest(out_manifest, manifest, model_size, rows)

    result = {"account": manifest.get("account"), "transcribed_at": datetime.now().isoformat(timespec="seconds"), "model": model_size, "videos": rows}
    with open(out_manifest, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"manifest": out_manifest, "total": len(rows), "ok": sum(x.get('status') == 'ok' for x in rows), "errors": sum(x.get('status') == 'error' for x in rows)}, ensure_ascii=False))


def _save_manifest(out_manifest, manifest, model_size, rows):
    """逐条保存 manifest，中断不丢进度"""
    result = {
        "account": manifest.get("account"),
        "transcribed_at": datetime.now().isoformat(timespec="seconds"),
        "model": model_size,
        "videos": rows,
    }
    with open(out_manifest, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="base")
    auto_device, auto_compute = get_device_config()
    parser.add_argument("--device", default=auto_device, choices=["cpu", "cuda"])
    parser.add_argument("--compute-type", default=None)
    args = parser.parse_args()
    compute_type = args.compute_type or auto_compute
    main(args.manifest, args.output_dir, args.model, args.device, compute_type)
