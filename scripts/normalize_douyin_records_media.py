# -*- coding: utf-8 -*-
"""Prepare captured Douyin records for the local downloader."""
import argparse
import json


def main(source, output):
    payload = json.loads(open(source, encoding="utf-8-sig").read())
    videos = []
    for row in payload.get("videos", []):
        videos.append({
            "video_id": row["video_id"],
            "url": row.get("url", ""),
            "title": row.get("title") or row.get("card_text", ""),
            "media_video_url": row.get("media_url"),
            "media_audio_url": None,
            "source_status": row.get("status"),
            "create_time": row.get("create_time"),
            "digg_count": row.get("digg_count"),
            "comment_count": row.get("comment_count"),
            "share_count": row.get("share_count"),
            "collect_count": row.get("collect_count"),
            "play_count": row.get("play_count"),
            "author_nickname": row.get("author_nickname"),
            "cover_url": row.get("cover_url"),
            "publish_time_text": row.get("publish_time_text"),
        })
    result = {
        "account": payload.get("account"),
        "profile_url": payload.get("profile_url"),
        "display_count": payload.get("display_count"),
        "source_records": source,
        "videos": videos,
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output, "total": len(videos), "media_urls": sum(bool(x.get("media_video_url")) for x in videos)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.source, args.output)
