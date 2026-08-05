# -*- coding: utf-8 -*-
"""Download captured Douyin video/audio tracks and mux them into playable MP4 files."""
import argparse
import json
import os
import subprocess
import urllib.request
import re
from datetime import datetime


def download(url, path):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
            "Referer": "https://www.douyin.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response, open(path, "wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def probe(path):
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", path, "-f", "null", "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        text = result.stderr or ""
        match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
        duration = 0.0
        if match:
            duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
        return {"duration": duration, "size": os.path.getsize(path), "ffmpeg_returncode": result.returncode}
    except Exception as exc:
        return {"error": str(exc)[:200]}


def main(raw_path, video_dir, manifest_path):
    os.makedirs(video_dir, exist_ok=True)
    payload = json.load(open(raw_path, encoding="utf-8"))
    manifest = []
    for index, item in enumerate(payload["videos"], 1):
        video_id = item["video_id"]
        video_track = os.path.join(video_dir, f"{video_id}.video.mp4")
        audio_track = os.path.join(video_dir, f"{video_id}.audio.mp4")
        final_path = os.path.join(video_dir, f"{video_id}.mp4")
        row = {"video_id": video_id, "url": item["url"], "title": item.get("title", ""), "local_video": final_path}
        try:
            if not os.path.exists(video_track) or os.path.getsize(video_track) < 10000:
                download(item["media_video_url"] or item["media_url"], video_track)
            if item.get("media_audio_url"):
                if not os.path.exists(audio_track) or os.path.getsize(audio_track) < 10000:
                    download(item["media_audio_url"], audio_track)
                subprocess.run(
                    ["ffmpeg", "-y", "-i", video_track, "-i", audio_track, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", final_path],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.run(["ffmpeg", "-y", "-i", video_track, "-c", "copy", final_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            row["validation"] = probe(final_path)
            row["status"] = "ok" if row["validation"].get("size", 0) > 10000 and row["validation"].get("duration", 0) > 0 else "invalid"
        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)[:500]
        manifest.append(row)
        print(f"[{index:02d}/{len(payload['videos'])}] {video_id} {row['status']}", flush=True)
    output = {"account": payload.get("account"), "raw_dataset": raw_path, "downloaded_at": datetime.now().isoformat(timespec="seconds"), "videos": manifest}
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"manifest": manifest_path, "total": len(manifest), "ok": sum(x.get("status") == "ok" for x in manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--video-dir", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    main(args.raw, args.video_dir, args.manifest)
