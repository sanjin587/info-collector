# -*- coding: utf-8 -*-
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def local_time(epoch):
    if epoch in (None, ""):
        return ""
    try:
        return datetime.fromtimestamp(int(epoch), timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def main(records_path, dataset_path, transcripts_path, vault_dir, profile_path):
    records = json.loads(Path(records_path).read_text(encoding="utf-8-sig"))
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8-sig"))
    transcripts = json.loads(Path(transcripts_path).read_text(encoding="utf-8-sig"))
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8-sig"))
    details = {row["video_id"]: row for row in records.get("videos", [])}
    downloads = {row["video_id"]: row for row in dataset.get("videos", [])}
    transcript_rows = {row["video_id"]: row for row in transcripts.get("videos", [])}
    out = Path(vault_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for video_id, detail in details.items():
        download = downloads.get(video_id, {})
        transcript = transcript_rows.get(video_id, {})
        title = detail.get("title") or download.get("title") or video_id
        rows.append({
            "video_id": video_id,
            "title": title,
            "create_time": detail.get("create_time"),
            "publish_time": local_time(detail.get("create_time")),
            "publish_time_text": detail.get("publish_time_text"),
            "digg_count": detail.get("digg_count"),
            "comment_count": detail.get("comment_count"),
            "share_count": detail.get("share_count"),
            "collect_count": detail.get("collect_count"),
            "play_count": detail.get("play_count"),
            "duration_sec": download.get("validation", {}).get("duration"),
            "source_url": detail.get("url") or download.get("url"),
            "local_video": download.get("local_video"),
            "transcript_status": transcript.get("status", "missing"),
        })
    rows.sort(key=lambda row: (row.get("create_time") or 0), reverse=True)
    table = ["| 发布时间 | 标题 | 点赞 | 评论 | 分享 | 收藏 | 时长(秒) | 视频 ID | 逐字稿 |", "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for row in rows:
        title = row["title"].replace("|", "／").replace("\n", " ")
        table.append(f"| {row['publish_time'] or row['publish_time_text'] or ''} | {title} | {row['digg_count'] or ''} | {row['comment_count'] or ''} | {row['share_count'] or ''} | {row['collect_count'] or ''} | {round(float(row['duration_sec']), 1) if row['duration_sec'] else ''} | {row['video_id']} | [[{row['video_id']}|查看逐字稿]] |")
    content = "\n".join([
        "---",
        "title: 老林说｜作品信息汇总",
        "account: 老林说",
        f"profile_url: {profile.get('profile_url', '')}",
        f"works_displayed: {profile.get('works_displayed')}",
        f"works_collected: {len(rows)}",
        f"media_validated: {sum(x.get('status') == 'ok' for x in downloads.values())}",
        f"transcripts_ok: {sum(x.get('status') == 'ok' for x in transcript_rows.values())}",
        "---", "", "# 老林说｜作品信息汇总", "",
        f"- 账号页显示作品：{profile.get('works_displayed')} 条",
        f"- 当前已核验作品：{len(rows)} 条",
        f"- 粉丝：{profile.get('followers_displayed')}；获赞：{profile.get('likes_displayed')}；IP：{profile.get('ip_displayed')}",
        "- 当前会话分页未补齐账号页显示的剩余作品；未核验的作品不计入下表，也没有生成伪逐字稿。",
        "- 逐字稿为本地 faster-whisper/base ASR，未经人工逐句校对。",
        "", "## 作品明细", "", *table, "",
    ])
    (out / "01_作品信息汇总.md").write_text(content, encoding="utf-8")
    summary = {"account": "老林说", "display_count": profile.get("works_displayed"), "collected_count": len(rows), "media_validated": sum(x.get("status") == "ok" for x in downloads.values()), "transcripts_ok": sum(x.get("status") == "ok" for x in transcript_rows.values()), "rows": rows}
    (out / "collection_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metadata_note": str(out / '01_作品信息汇总.md'), "rows": len(rows), "media": summary["media_validated"], "transcripts": summary["transcripts_ok"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--transcripts", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--vault-dir", required=True)
    args = parser.parse_args()
    main(args.records, args.dataset, args.transcripts, args.vault_dir, args.profile)
