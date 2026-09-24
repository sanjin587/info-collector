# 抖音视频转逐字稿 Markdown

需要把抖音视频语音整理成可搜索、可回听的文字时，可输入可访问的抖音视频链接；已有合法取得的本地 MP4/MP3，也能跳过链接获取环节直接转录。

这篇回答“抖音视频怎么提取文字/转逐字稿”。它有两条不同路径：**链接→尝试获取媒体→转录→Markdown**，或**本地文件→转录→文本**。如果你只需要确认链接会走哪种处理方式，先用 `--dry-run`，它不会下载视频或生成逐字稿。

## 链接路径

先只预览处理方式，不访问视频：

```bash
python scripts/collector.py pipeline "https://www.douyin.com/video/视频ID" --dry-run
```

准备好转录依赖、媒体访问条件后，去掉 `--dry-run` 执行。流水线会先尝试读取播放器字幕并做质量校验，再尝试下载媒体后用本地 Whisper 语音识别；最后的 Paraformer 在线兜底需要单独配置。播放器字幕不一定是视频语音的逐字稿，引用前应回听核对。

把示例 URL 换成真实可访问的作品链接。实际执行命令是 `python scripts/collector.py pipeline "<真实抖音视频URL>"`。在仓库根目录先准备 Python 3.11+ 和项目转录依赖；下载回退需要 `yt-dlp`，本地语音识别需要 `faster-whisper`/模型文件。`setup.bat` 是 Windows 的完整安装入口，可能安装较多可选依赖；可先运行上面的预览命令判断这是不是你要的流程。

成功时默认保存到 `outputs/transcripts/` 下的 `.md`，包含来源链接和使用的引擎。设置 `OBSIDIAN_OUTPUT_DIR` 可改为你自己的 Obsidian 目录。链接路径依赖可访问的媒体、`yt-dlp`/Chrome 等环境及平台规则；预览成功不代表下载或转录成功。

Markdown 里会记录来源、平台、引擎及正文。如果成功策略标成 Chrome CDP，应把结果视为**播放器字幕提取**；若策略是 Whisper/Paraformer，才是语音识别结果。两者都可能漏字或错字。若要用于引用、发表或研究，请回听原视频核对人名、数字和上下文。

## 已有本地视频

```bash
python scripts/collector.py transcribe "视频.mp4" --output "逐字稿.txt"
```

也可用 `python scripts/transcribe_local.py "视频.mp4" --engine whisper --output "逐字稿.txt"` 只走本地 Whisper。模型文件和转录依赖需先准备；自动转写可能误识别专有名词、数字和标点。

本地文件路径最稳妥：它不依赖抖音链接能否下载。如果你希望把单个文件输出成 Markdown，可以把 `--output` 指向 `逐字稿.md`，但 `collector.py transcribe` 写入的是**纯转录文本**，不会自动加上来源元数据；带来源的 Markdown 是 `pipeline` 成功后保存的版本。

## 常见问题

- **预览成功，正式执行失败？** 预览只展示策略，不访问平台；检查媒体是否可访问、转录依赖和终端中的具体失败策略。
- **只有标题/简介，没有口播文字？** 标题和页面说明不是逐字稿。需取得可处理的媒体并实际运行转录。
- **一定要登录或配置 API Key 吗？** 本地文件+Whisper 不需要平台账号或在线转录 Key；平台链接可能受访问限制，在线 Paraformer 兜底需要自行配置。
- **能批量处理账号吗？** 仓库有额外的账号/批量脚本，但本页给的是单链接和单文件的明确入口；不要据此推断任意账号可无条件批量抓取。

源码：[统一流水线](../scripts/collector.py) · [本地语音转写](../scripts/transcribe_local.py)。不要把平台字幕、自动 ASR 或页面简介当作已人工校对的逐字稿。
