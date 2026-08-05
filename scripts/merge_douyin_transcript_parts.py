# -*- coding: utf-8 -*-
import argparse
import json
import shutil
from pathlib import Path


def main(dataset, parts_dir, output_dir, parts):
    base = json.loads(Path(dataset).read_text(encoding="utf-8-sig"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    by_id = {}
    for index in range(1, parts + 1):
        manifest_path = Path(parts_dir) / f"out_{index}" / "transcript_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for row in manifest.get("videos", []):
            source = Path(row.get("transcript_path", ""))
            target = out / source.name
            shutil.copy2(source, target)
            row["transcript_path"] = str(target)
            by_id[row["video_id"]] = row
    rows = [by_id[item["video_id"]] for item in base.get("videos", []) if item["video_id"] in by_id]
    merged = {"account": base.get("account"), "transcribed_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "model": "base", "videos": rows}
    manifest_path = out / "transcript_manifest.json"
    manifest_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "total": len(rows), "ok": sum(x.get("status") == "ok" for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--parts-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parts", type=int, default=3)
    args = parser.parse_args()
    main(args.dataset, args.parts_dir, args.output_dir, args.parts)
