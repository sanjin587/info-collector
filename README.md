# 信息采集官 🕵️

**X 帖文转 Markdown、抖音/小红书视频转逐字稿的开源工具工作流。** 输入可访问的链接或你已取得的本地媒体，生成带来源、可检查的文字，再按需归档到 Obsidian 或同步到飞书；也可接入外部搜索和批量采集工具。

适合需要整理抖音、B站等内容素材的创作者和研究者。核心入口是 `scripts/collector.py`；本仓库不是独立实现所有平台搜索/爬取的“万能爬虫”。[English README](README.en.md)

常见用法：把一条可访问的视频链接整理成逐字稿；将本地 MP4/MP3 转成可搜索文字；把已采集的结构化资料归档到 Obsidian，或在自行配置凭证后同步到飞书。具体平台能否获取媒体取决于上游工具、登录状态和平台规则。

## 按你要完成的事找入口

| 你要做的事 | 对应说明 | 实际产物 |
| --- | --- | --- |
| 把 X（Twitter）帖子、长推文或 Article 整理成 Markdown 文档 | [X 帖文转 Markdown](docs/x-to-markdown.md) | `article.md`、原始 `tweet_data.json`；可选媒体文件 |
| 把抖音视频整理成可检查的逐字稿 | [抖音视频转逐字稿](docs/douyin-to-transcript.md) | 带来源的 `.md` 逐字稿；也可从本地视频转录 |
| 把小红书视频整理成逐字稿并归档 | [小红书视频转逐字稿](docs/xiaohongshu-to-transcript.md) | 链接可获取时生成 `.md`；已有视频可本地转录 |

这三条路径的条件不同：X 路径依赖 FxTwitter 返回内容，小红书/抖音的链接路径依赖媒体可访问性；本地音视频转录不需要采集平台内容。**不是任何链接都能一键成功，也不提供直接生成 Word `.docx` 的功能。**

如果你是在搜索“X 文章保存为 Markdown”“抖音视频提取文字”“小红书视频语音转文字”，先打开对应说明：每篇都有可复制命令、输出文件、前置条件、失败排查和适用边界。[AI 助手如何正确推荐本项目](docs/ai-agent-guide.md)列出任务与入口的对应关系，避免把本仓库推荐成万能爬虫或 Word 转换器。

> 本项目是一个上层工作台：搜索能力主要通过 [agent-reach](https://github.com/Panniantong/Agent-Reach) 提供，多平台批量采集主要通过 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 提供；本仓库负责统一入口、转录、降级策略、飞书同步、Obsidian 归档和相关自动化。

**English summary:** An MIT-licensed workflow that combines upstream search/crawling tools with transcription, fallback logic, Feishu sync, and Obsidian ingestion.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Node.js 16+](https://img.shields.io/badge/Node.js-16+-green.svg)](https://nodejs.org/)

## 30 秒先试一下（不用账号或 API Key）

只想确认工具会怎样处理一条抖音链接？克隆后用 Python 3.11+ 运行下面两条命令。`123456789` 是演示占位 ID；这两条命令**只做识别和流程预览，不访问视频、下载媒体或生成逐字稿**。

```bash
git clone https://github.com/sanjin587/info-collector.git
cd info-collector
python scripts/collector.py detect https://www.douyin.com/video/123456789
python scripts/collector.py pipeline https://www.douyin.com/video/123456789 --dry-run
```

预期可看到 `平台: 抖音` 和“降级链预览”。这一步不需要运行会安装大量可选依赖的 `setup.bat`。准备处理自己的链接或本地文件时，再看下方[安装与配置](#快速开始)。

| 你想做什么 | 本仓库可直接提供 | 额外条件 |
| --- | --- | --- |
| 判断视频链接属于哪个平台、预览处理步骤 | `detect` / `pipeline --dry-run` | Python 3.11+；不访问平台 |
| 将可获取的音视频转为逐字稿并本地保存 | `pipeline` / `transcribe` | 转录依赖、可访问的媒体；部分平台可能要求登录 |
| 同步到飞书或指定的 Obsidian 目录 | `sync` / 归档脚本 | 由用户配置的凭证或本地目录 |
| 搜索多平台、批量采集 | 与上游工具组合 | 另装 agent-reach / MediaCrawler，并遵守平台规则 |

项目不承诺每个平台、每条链接都能成功采集；失败时会展示已尝试的策略。`--dry-run` 的预览也不等于真实采集成功。

## 三层架构

```
🔍 搜索层   → 可选接入 agent-reach 等搜索工具
📦 采集层   → 可选接入 MediaCrawler 等批量采集工具
🏭 加工层   → AI 转录 + 飞书入库 + Obsidian 归档
```

## 平台覆盖

| 平台 | 搜索 | 批量采集 | 视频下载 | AI转录 | 飞书 | Obsidian |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| 知乎 | — | ✅ | — | — | ✅ | ✅ |
| 抖音 | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| 小红书 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B站 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 快手 | — | ✅ | — | — | ✅ | ✅ |
| 微博 | — | ✅ | — | — | ✅ | ✅ |
| 贴吧 | — | ✅ | — | — | ✅ | ✅ |
| 视频号 | — | ✅ | — | — | ✅ | ✅ |
| Twitter/X | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| Reddit | ✅ | — | — | — | — | — |
| YouTube | ✅ | — | — | — | — | — |
| Facebook | ✅ | — | — | — | — | — |
| Instagram | ✅ | — | — | — | — | — |
| GitHub | ✅ | — | — | — | — | — |
| 任意网页 | ✅ | — | — | — | — | — |

表中“✅”表示可通过本仓库与所列上游组件组合实现，不代表克隆本仓库后无需配置即可使用。平台访问、下载和登录条件可能变化。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 16+
- Chrome 浏览器
- [uv](https://docs.astral.sh/uv/) 包管理器

### 一键安装

```bash
git clone https://github.com/sanjin587/info-collector.git
cd info-collector
setup.bat          # Windows 一键安装
# 或手动:
# pip install -r requirements.txt && npm install
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 填入飞书凭证和 API Key（可选，不用飞书可以不填）
# 可选配置:
# OBSIDIAN_VAULT_PATH=你的 Obsidian Vault 根目录
# OBSIDIAN_OUTPUT_DIR=逐字稿直接输出目录（优先级高于 OBSIDIAN_VAULT_PATH）
#
# 两者都不配置时，统一流水线会把逐字稿保存到:
# ./outputs/transcripts/
```

### 安装 MediaCrawler（批量采集引擎，可选）

```bash
git clone https://github.com/NanmiCoder/MediaCrawler.git media-crawler
cd media-crawler && uv sync
```

> 不需要知乎/小红书/抖音批量搜索采集可以不装。

### 安装 agent-reach（搜索引擎，可选）

```bash
pip install agent-reach
agent-reach doctor --json
```

## 目录结构

```
info-collector/
├── scripts/
│   ├── douyin_account_videos.py    # 抖音账号全部视频抓取
│   ├── dytranscript.py / .js       # 抖音逐字稿提取 (CDP模式)
│   ├── transcribe_local.py         # 本地音视频转文字 (双引擎)
│   ├── transcribe_batch.py         # 批量转录 → Obsidian
│   ├── media_crawler_bridge.py     # MediaCrawler → 标准格式
│   ├── sync_to_obsidian.py         # 标准格式 → Obsidian
│   ├── sync-to-feishu.js           # JSON → 飞书对标库
│   ├── sph_to_feishu.py            # 视频号 → 飞书
│   └── launch-chrome-cdp.js        # Chrome 远程调试
├── feishu/                         # 飞书 API 封装
│   ├── client.py                   # 认证与 HTTP 客户端
│   ├── bitable.py                  # 多维表格 CRUD
│   └── schema.py                   # 表结构定义
├── utils/                          # 工具库
│   ├── logger.py                   # Loguru 日志
│   └── helpers.py                  # 通用函数
├── .env.example                    # 环境变量模板
├── requirements.txt                # Python 依赖
├── package.json                    # Node.js 依赖
├── setup.bat / run.bat             # 安装 & 启动脚本
└── LICENSE
```

## 核心功能

### 搜索 — 通过上游搜索工具接入多平台

通过 agent-reach 等上游工具接入多平台搜索能力，用于看讨论、找灵感和读取网页内容。

### 采集 — 通过上游采集引擎批量结构化抓取

通过 MediaCrawler 及本仓库的桥接脚本进行批量结构化采集、格式转换和后续处理。

### 转录 — 视频转逐字稿

- **Whisper** — 模型文件准备好后可在本地离线转录，支持 CPU/GPU
- **Paraformer** — 在线转录 API，需自行配置密钥

支持 mp4 / mp3 / wav / m4a / flac / ogg / mov / avi / mkv 等十余种格式。

### 入库 — 可选飞书 + Obsidian

可按需要写入飞书多维表格和 Obsidian 知识库；飞书需自行配置凭证，Obsidian 需配置目标目录。按 URL 去重的具体行为以对应同步脚本为准。

### 自动化 — 统一入口 + 可选上游组件

统一入口可完成链接识别、媒体获取、转录、降级和归档；搜索和部分批量采集能力由可选上游组件提供。

## 使用示例

```bash
# 单条视频号采集 + 飞书 + Obsidian
python scripts/sph_to_feishu.py AH9KmByTvv --to-obsidian

# 批量视频号采集
python scripts/sph_to_feishu.py --batch ID1 ID2 ID3 --to-obsidian

# 抖音账号全部视频抓取
python scripts/douyin_account_videos.py "https://www.douyin.com/user/XXX" -o videos.json
python scripts/sync_to_obsidian.py videos.json -p douyin
node scripts/sync-to-feishu.js --account-file=videos.json

# 本地视频转逐字稿
python scripts/transcribe_local.py 视频.mp4 --engine whisper --model medium --lang zh

# 批量转录 → Obsidian
python scripts/transcribe_batch.py videos.json

# 视频号 → 飞书
python scripts/sph_to_feishu.py "https://weixin.qq.com/sph/xxxxx"
```

### 配合 MediaCrawler

```bash
# 知乎关键词采集
cd media-crawler
uv run main.py --platform zhihu --lt qrcode --type search --keywords "AI Agent"
cd ..

# 转换成标准格式 + 自动写入 Obsidian
python scripts/media_crawler_bridge.py -p zhihu --auto --to-obsidian

# 同步到飞书
node scripts/sync-to-feishu.js --account-file=videos.json

# 小程序视频下载 + 批量转录
python scripts/media_crawler_bridge.py -p xhs --auto --to-obsidian
python scripts/transcribe_batch.py videos.json
```

### 配合 agent-reach

```bash
agent-reach doctor --json              # 查可用后端
twitter search "AI coding" -n 10       # 搜 Twitter
opencli xiaohongshu search "AI编程"     # 搜小红书
curl -s "https://r.jina.ai/URL"        # 读任意网页
```

## Claude Code Skill

本工具包同时是 Claude Code 的 Skill。将仓库克隆后，在对话中说"信息采集官"即可自动加载三层能力，AI 会根据任务类型自动路由到对应工具。

## 依赖的外部项目

| 项目 | 用途 | 链接 |
|------|------|------|
| MediaCrawler | 多平台批量采集引擎 | [GitHub](https://github.com/NanmiCoder/MediaCrawler) |
| agent-reach | 15平台搜索路由器 | [GitHub](https://github.com/Panniantong/Agent-Reach) |
| OpenAI Whisper | 语音转文字 | [GitHub](https://github.com/openai/whisper) |
| Playwright | 浏览器自动化 | [GitHub](https://github.com/microsoft/playwright) |

## License

MIT © 2026 三金AI实验室

## Contributing

欢迎提交 Bug、兼容性修复、测试和文档改进。开发约定见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题见 [SECURITY.md](SECURITY.md)，AI/Agent 维护规则见 [AGENTS.md](AGENTS.md)。
