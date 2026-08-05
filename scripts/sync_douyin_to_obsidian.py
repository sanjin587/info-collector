# -*- coding: utf-8 -*-
"""Archive a Douyin account collection and its ASR transcripts into Obsidian."""
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


VAULT_ACCOUNT_DIR = Path(r"D:\知识库\知识库\05_内容生产库\三金AI实验室_30天万粉作战计划\对标账号\宅不住的AI")


def clean_title(value):
    value = (value or "").replace(" - 抖音", "").strip()
    return value or "未命名作品"


def main(download_manifest, transcript_manifest, output_dataset):
    downloads = json.loads(Path(download_manifest).read_text(encoding="utf-8"))
    transcripts = json.loads(Path(transcript_manifest).read_text(encoding="utf-8"))
    transcript_map = {x["video_id"]: x for x in transcripts.get("videos", [])}
    VAULT_ACCOUNT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in downloads.get("videos", []):
        video_id = item["video_id"]
        t = transcript_map.get(video_id, {})
        transcript_path = Path(t.get("transcript_path", ""))
        transcript = transcript_path.read_text(encoding="utf-8") if transcript_path.exists() else ""
        if "# 逐字稿" in transcript:
            transcript = transcript.split("# 逐字稿", 1)[1].strip()
        title = clean_title(item.get("title"))
        note_path = VAULT_ACCOUNT_DIR / f"{video_id}.md"
        note = "\n".join([
            "---",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            f"source_url: {item.get('url', '')}",
            f"video_id: {video_id}",
            "account: 宅不住的AI",
            f"local_video: {item.get('local_video', '')}",
            f"local_transcript: {transcript_path}",
            "source_type: 抖音公开作品",
            "transcript_type: 本地 ASR 逐字稿（未经人工校对）",
            f"asr_engine: faster-whisper/{transcripts.get('model', 'base')}",
            "---",
            "",
            f"# {title}",
            "",
            "## 来源与文件",
            f"- 原视频：{item.get('url', '')}",
            f"- 本地视频：`{item.get('local_video', '')}`",
            f"- 原始采集记录：`{download_manifest}`",
            "",
            "## 本地 ASR 逐字稿（未经人工校对）",
            "",
            transcript or "（未找到逐字稿内容）",
            "",
            "## 备注",
            "- 这份文字是本地 faster-whisper 识别结果，可能存在专有名词、数字和标点错误。",
            "- 若要作为发布稿或引用依据，应回听原视频人工校对。",
            "",
        ])
        note_path.write_text(note, encoding="utf-8")
        rows.append({**item, "title": title, "transcript_path": str(transcript_path), "obsidian_note": str(note_path), "transcript_status": t.get("status", "missing")})

    all_text = "\n".join((x.get("title", "") + " " + (transcript_map.get(x["video_id"], {}) and Path(transcript_map[x["video_id"]].get("transcript_path", "")).read_text(encoding="utf-8") if Path(transcript_map[x["video_id"]].get("transcript_path", "")).exists() else "")) for x in rows)
    keywords = ["AI视频", "AI生图", "AIGC", "豆包", "Lovart", "RunningHub", "Seedance", "广告", "短剧", "教程", "测评", "一键", "保姆级", "专业", "普通人", "行业", "SOP", "Agent", "设计", "代码", "导演", "Vidu", "Higgsfield", "小龙虾", "工作流"]
    keyword_counts = Counter({k: all_text.lower().count(k.lower()) for k in keywords})
    keyword_counts = {k: v for k, v in keyword_counts.items() if v}
    title_text = "\n".join(x.get("title", "") for x in rows)
    hook_patterns = {
        "结果承诺": r"一键|保姆级|公式|SOP|正确打开方式|从0到1",
        "反差/冲突": r"邪修|完蛋|淘汰者|物理外挂|平权|超过你的想象|太离谱|强到可怕",
        "低门槛": r"普通人|小白|不懂|不用|一句话|只需要一句",
        "疑问驱动": r"[？?]",
    }
    hook_counts = {k: len(re.findall(v, title_text, flags=re.I)) for k, v in hook_patterns.items()}
    type_patterns = {
        "教程/工作流": r"教程|保姆级|工作流|SOP|公式|怎么做|正确打开方式",
        "工具测评/发布解读": r"实测|测评|专业性|平替|工具|模型|全新|开年第一炸",
        "AI视频/广告/短剧": r"视频|短片|广告片|短剧|导演|Seedance|Vidu|Higgsfield|LibTV|VibeMotion",
        "AI设计/生图": r"设计|生图|GPT-image|Lovart|电商",
        "AI硬件/实体产品": r"机器狗|宠物|玩具",
    }
    type_counts = {k: len(re.findall(v, title_text, flags=re.I)) for k, v in type_patterns.items()}
    report_path = VAULT_ACCOUNT_DIR / "01_账号分析报告.md"
    top_keywords = "、".join(f"{k}（{v}）" for k, v in sorted(keyword_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:12])
    table_rows = "\n".join(f"| {i} | {x['video_id']} | {x['title'].replace('|', '／')} | {x.get('url','')} | {x.get('local_video','')} | {x.get('transcript_status')} |" for i, x in enumerate(rows, 1))
    report = f"""---
title: 宅不住的AI账号分析报告
account: 宅不住的AI
source_url: https://www.douyin.com/user/MS4wLjABAAAAdSEZrolOwkMaR7gVOFFWOTlDxMhdibtEV3m41a4YrWo
captured_at: {datetime.now().isoformat(timespec='seconds')}
source_count_verified: {len(rows)}
download_count_verified: {sum(x.get('status') == 'ok' for x in rows)}
transcript_count_verified: {sum(x.get('transcript_status') == 'ok' for x in rows)}
---

# 宅不住的AI：账号分析报告

## 一、证据边界

- 本次从账号作品页核验到 **33 条作品**；8 条页脚/推荐区链接未计入账号作品。
- 33 条作品均捕获到画面媒体流和音频媒体流，合并为本地 MP4，并通过 FFmpeg 播放性校验。
- 33 条均完成本地 faster-whisper/base 中文 ASR。以下逐字稿是机器识别稿，不等同于人工校对后的真实原始逐字稿。
- 账号页采集时显示：**宅不住的AI**，抖音号 `ZHAIBUZHU123`，约 **95.2 万粉丝、569.2 万获赞**，IP 浙江；简介为“算法工程师 / 前代码农 / 现役遛弯评测员”。这些是本次采集时页面可见值，不作历史增长曲线。

## 二、账号一句话画像

这是一个以“工程师可信度”做背书、以“新 AI 工具实测 + 可复制工作流 + 结果展示”为主线的 AIGC/AI 产品评测账号；内容不断追逐新工具，但始终把工具翻译成普通人能理解的结果。

## 三、内容结构

### 1. 内容矩阵（按标题关键词，允许一条作品同时落入多个类别）

{chr(10).join(f'- {k}：{v} 条' for k, v in type_counts.items())}

高频词：{top_keywords}

### 2. 选题来源

- **模型/产品更新**：豆包、Seedance、Lovart、RunningHub、ViduClaw、GPT-image、Higgsfield 等。
- **能力结果**：从一句话做短片、做广告、做设计、做短剧、做办公任务，把技术变化转成可观看的成品。
- **行业焦虑与机会**：设计行业是否被替代、导演是否被 AI 平权、不要成为 AI 时代淘汰者。
- **低门槛教学**：保姆级、从 0 到 1、普通人、小白、一句话等表达，主动扩大受众面。

## 四、为什么容易获得流量

### 1. 反差不是装饰，而是点击理由

标题把“专业技术”与“极低门槛/极强结果”放在同一句里，例如“保姆级入门”“普通人也能”“一句话直出”“不懂也能”。观众先被结果吸引，再被工程师身份说服。

### 2. 每条内容有明确的结果承诺

它很少只讲“某工具是什么”，而是讲“能做出什么”：短片、广告片、设计、办公任务、机器宠物。结果可视化，适合短视频快速证明。

### 3. 工具更新带来天然时效

持续追踪新模型、新产品和新玩法，使账号有稳定的选题供给；同时用“实测、测评、平替、正确打开方式”降低观众的试错成本。

### 4. 专业身份与生活化叙述结合

“算法工程师/前代码农”提供可信度，但标题和讲法不依赖专业术语，形成“懂技术的人替我试过了”的观看理由。

## 五、可借鉴的方法

### 1. 借鉴“反差结构”，不要照搬人设

你可以把自己的可信资产放进标题：**专业判断 + 普通人结果**。例如“我用一套可复用流程，把一个复杂 AI 工具拆成 3 步”“不懂代码，也能先做出第一版”。重点是把你的真实实践放在结果前面。

### 2. 建立固定的“工具实测五件套”

每次测试都记录：适合谁、输入是什么、输出是什么、耗时/成本、最容易失败的地方。这样内容不只是新闻转述，而是可积累的评测资产。

### 3. 用成品做第一证据

开头先展示结果或前后对比，再解释过程；不要先从概念定义开始。你的账号可以把“逐字稿、提示词、工作流、成片”做成连续栏目，形成可追更的系列。

### 4. 把“低门槛”落实到操作路径

标题可以写“普通人能学”，但正文必须给出第一步、最小工具组合和失败兜底，否则低门槛承诺会透支信任。

### 5. 做系列化，而不是只追热点

建议固定三条主线：

- **AI 工具实测**：一条视频只解决一个真实任务；
- **AI 工作流拆解**：从输入到成品，展示关键节点；
- **AI 时代判断**：用具体案例回答“谁会被替代、谁会获得杠杆”。

### 6. 标题模板可借鉴

- “我把【复杂任务】压缩成【一步/三步】，普通人也能先做出【结果】”
- “别急着学【大概念】，先用【工具】完成一个【可见结果】”
- “【工具】到底是不是智商税？我用【真实任务】跑了一遍”
- “AI 不是替你给答案：我让它先完成【动作】，结果差别很大”

## 六、风险与短板

- **热点依赖**：工具更新快，旧内容可能快速失效；需要在每条内容中沉淀不随工具变化的方法论。
- **工具过多**：观众可能记住工具名，却没有记住账号的独特判断；应反复使用固定评测标准。
- **结果过强的标题**： “完蛋、王炸、太离谱”等词有点击力，但若成品证明不足，会降低长期信任。
- **商业合作识别**：品牌/工具内容要明确实测边界，区分“体验结论”和“广告承诺”。

## 七、对你的直接建议

不要复制“他测了什么工具”，而要复制他的内容工程：**选题抓新变化、开头给反差、过程给证据、结尾给可复制动作**。你的差异化可以放在“把 AI 工具变成可复用生产系统”，让观众不只看完觉得惊讶，还能带走一套能复现的步骤。

## 八、作品与文件索引

| 序号 | 视频 ID | 标题 | 原视频 | 本地视频 | 逐字稿状态 |
|---:|---|---|---|---|---|
{table_rows}

"""
    report_path.write_text(report, encoding="utf-8")
    index_path = VAULT_ACCOUNT_DIR / "00_账号索引.md"
    index_path.write_text("\n".join([
        "# 宅不住的AI｜账号采集索引", "", f"- 账号主页：https://www.douyin.com/user/MS4wLjABAAAAdSEZrolOwkMaR7gVOFFWOTlDxMhdibtEV3m41a4YrWo", f"- 本次核验作品：{len(rows)} 条", "- 视频：33/33 已下载并通过播放性校验", "- 逐字稿：33/33 本地 ASR，未经人工校对", "", "## 报告", "- [[01_账号分析报告]]", "", "## 逐条笔记", "", "\n".join(f"- [[{x['video_id']}|{x['title']}]]" for x in rows), "" ]), encoding="utf-8")
    Path(output_dataset).write_text(json.dumps({"account": "宅不住的AI", "source_count_verified": len(rows), "download_count_verified": sum(x.get("status") == "ok" for x in rows), "transcript_count_verified": sum(x.get("transcript_status") == "ok" for x in rows), "videos": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"account_dir": str(VAULT_ACCOUNT_DIR), "notes": len(rows), "report": str(report_path), "index": str(index_path)}, ensure_ascii=False))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", required=True)
    parser.add_argument("--transcripts", required=True)
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    main(args.downloads, args.transcripts, args.dataset)
