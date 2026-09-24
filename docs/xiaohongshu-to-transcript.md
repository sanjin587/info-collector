# 小红书视频转逐字稿与 Markdown 归档

需要整理小红书视频语音时，本仓库提供两种入口：尝试从可访问的笔记链接取得媒体并转录，或对你已经取得的本地视频做离线转录。链接获取能力取决于上游 `yt-dlp`、登录状态和平台规则；不是所有小红书笔记都含视频，也不保证链接可下载。

这篇回答“小红书视频怎么转文字/逐字稿”。先区分笔记类型：图文笔记没有需要做语音识别的视频；只有视频笔记或你手头已有音视频文件，才适用以下转录步骤。

## 从可访问的链接开始

```bash
python scripts/collector.py pipeline "https://www.xiaohongshu.com/explore/笔记ID" --dry-run
```

这一步只展示处理链。具备媒体访问条件、转录依赖后，去掉 `--dry-run`，才会尝试下载并用 Whisper 转录。成功时默认生成 `outputs/transcripts/` 下带来源的 `.md`。Cookie 回退仅在你已合法登录并允许使用时适用；本仓库不提供绕过登录或访问限制的方法。

请把占位 URL 换成真实的 `xiaohongshu.com` 笔记地址。实际执行命令是 `python scripts/collector.py pipeline "<真实小红书视频笔记URL>"`。目前链接识别器匹配 `xiaohongshu.com`；短链或跳转链接可能要先取得可识别的完整地址。处理链会尝试 `yt-dlp` 下载，再调用 Whisper；如果平台限制下载，命令可能失败，`--dry-run` 不能证明能拿到媒体。

准备 Python 3.11+、下载工具和转录依赖；可先看 [项目安装说明](../README.md#快速开始)。成功的 Markdown 会记录来源 URL、平台、引擎和转写文本。若链接路径不可用，优先用你有权使用的本地视频，不要把访问失败写成“没有逐字稿”。

## 视频已经在本地

```bash
python scripts/collector.py transcribe "视频.mp4" --output "逐字稿.txt"
```

转写完成后要回听校对。若你已有结构化 `dataset.json` 与包含 `videos[].video_id`、`transcript_path` 的 `transcript_manifest.json`，还可用 `scripts/archive_xhs_transcript_to_obsidian.py --dataset <dataset.json> --transcripts <manifest所在目录> --vault-dir <目标目录>` 将现有逐字稿整理成 Obsidian Markdown。这个脚本**只负责归档已有结果，不负责抓取或语音识别**；缺失的逐字稿会标记“未生成”。

这里的“已有结果”至少包含 `dataset.json` 中的 `videos[].video_id`，以及 manifest 中与之相同的 `video_id` 和 `transcript_path`。这不是普通用户输入一条笔记链接即可直接调用的命令。归档会生成每条视频的 Markdown 和账号索引；如果逐字稿文件不存在，归档页会明确写“未生成逐字稿”，不能把它算成转写成功。

## 常见问题

- **为什么完整链接仍下载失败？** 平台可能要求登录或限制媒体访问；本工具不绕过这些限制。可使用你已合法取得的本地文件。
- **图文笔记能转逐字稿吗？** 不能；没有视频语音时，应保存原文字而不是生成虚构的转录内容。
- **归档脚本显示成功就有逐字稿吗？** 不一定。它会为缺失转录写占位提示；需要检查 manifest 状态和 Markdown 正文。
- **ASR 能直接拿去发表吗？** 不建议。人名、数字、术语和标点应回听核对。

源码：[统一流水线](../scripts/collector.py) · [本地语音转写](../scripts/transcribe_local.py) · [已有结果归档](../scripts/archive_xhs_transcript_to_obsidian.py)。请只处理有权访问和保存的素材；自动转写不是人工逐句校对。
