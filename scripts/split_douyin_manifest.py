# -*- coding: utf-8 -*-
import argparse
import json
from pathlib import Path


def main(source, output_dir, parts):
    payload = json.loads(Path(source).read_text(encoding="utf-8-sig"))
    videos = payload.get("videos", [])
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for index in range(parts):
        subset = videos[index::parts]
        data = {**payload, "videos": subset, "split_index": index + 1, "split_parts": parts}
        path = out / f"manifest_{index + 1}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"part": index + 1, "count": len(subset), "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parts", type=int, default=3)
    args = parser.parse_args()
    main(args.source, args.output_dir, args.parts)
