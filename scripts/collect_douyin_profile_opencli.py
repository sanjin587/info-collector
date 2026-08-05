# -*- coding: utf-8 -*-
"""Read the currently connected Douyin profile page through OpenCLI."""
import argparse
import json
import re
import subprocess
from datetime import datetime


JS = "(()=>{const xs=[...new Map([...document.links].filter(a=>a.href.includes('/video/')).map(a=>[a.href.split('?')[0],a])).values()]; return JSON.stringify(xs.map(a=>({href:a.href.split('?')[0],text:(a.innerText||'').replace(/\\s+/g,' ').trim()})))})()"
BODY_JS = "JSON.stringify({url:location.href,body:document.body.innerText})"


def run_eval(profile, js):
    proc = subprocess.run(
        ["cmd.exe", "/d", "/c", "opencli.cmd", "--profile", profile, "browser", "collect", "eval", js],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def parse_json_output(raw):
    start = min([x for x in (raw.find("["), raw.find("{")) if x >= 0])
    return json.loads(raw[start:])


def first(pattern, body):
    match = re.search(pattern, body)
    return match.group(1).strip() if match else None


def main(profile, profile_url, output):
    items = parse_json_output(run_eval(profile, JS))
    page = parse_json_output(run_eval(profile, BODY_JS))
    body = page.get("body", "")
    rows = []
    for item in items:
        match = re.search(r"/video/(\d{19})$", item.get("href", ""))
        if not match:
            continue
        rows.append({
            "video_id": match.group(1),
            "url": f"https://www.douyin.com/video/{match.group(1)}",
            "card_text": item.get("text", ""),
        })
    result = {
        "profile_url": profile_url,
        "account": "老林说",
        "works_displayed": first(r"作品\s*(\d+)", body),
        "followers_displayed": first(r"粉丝\s*([^\n]+)", body),
        "likes_displayed": first(r"获赞\s*([^\n]+)", body),
        "ip_displayed": first(r"IP属地：?([^\n]+)", body),
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "videos": rows,
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": output, "displayed": result["works_displayed"], "collected": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profile-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.profile, args.profile_url, args.output)
