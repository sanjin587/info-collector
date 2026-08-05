# -*- coding: utf-8 -*-
import argparse
import json


def main(base_path, retry_path, output_path):
    base = json.loads(open(base_path, encoding="utf-8-sig").read())
    retry = json.loads(open(retry_path, encoding="utf-8-sig").read())
    retry_map = {row["video_id"]: row for row in retry.get("videos", []) if row.get("status") == "ok"}
    updated = 0
    for row in base.get("videos", []):
        new = retry_map.get(row.get("video_id"))
        if new:
            for key in ("media_video_url", "media_audio_url", "media_url"):
                row[key] = new.get(key)
            updated += 1
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(base, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output_path, "updated": updated, "total": len(base.get("videos", []))}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--retry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.base, args.retry, args.output)
