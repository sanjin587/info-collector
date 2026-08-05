# 信息采集官 🕵️

**三合一全平台内容采集工作台** — 搜索 · 采集 · 转录 · 入库，一条命令完成。

> 基于 [agent-reach](https://github.com/Panniantong/Agent-Reach)（搜索路由器）和 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)（采集引擎）构建上层工作台，补齐转录、飞书入库、Obsidian 归档三大能力。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Node.js 16+](https://img.shields.io/badge/Node.js-16+-green.svg)](https://nodejs.org/)

## 三层架构

```
🔍 搜索层   → 15 平台全网实时搜索
📦 采集层   →  7 平台批量结构化采集
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

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 16+
- Chrome 浏览器
- [uv](https://docs.astral.sh/uv/) 包管理器

### 一键安装

```bash
git clone https://github.com/YOUR_USERNAME/info-collector.git
cd info-collector
setup.bat          # Windows 一键安装
# 或手动:
# pip install -r requirements.txt && npm install
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 填入飞书凭证和 API Key（可选，不用飞书可以不填）
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

### 搜索 — 全网实时搜索

跨 15 个平台同时搜索，看讨论、找灵感、读任意网页内容。

### 采集 — 批量结构化抓取

输入关键词或账号链接，批量抓取作品数据和视频文件，支持 7 个平台，自动去重。

### 转录 — 视频转逐字稿

- **Whisper** — 本地离线，无需联网，CPU 即跑
- **Paraformer** — 在线高精度，中文极准

支持 mp4 / mp3 / wav / m4a / flac / ogg / mov / avi / mkv 等十余种格式。

### 入库 — 飞书 + Obsidian 双写

每条采集数据同时写入飞书多维表格和 Obsidian 知识库。按 URL 自动去重，两边互备。

### 自动化 — 全流程一条命令

搜索 → 采集 → 下载视频 → AI 转录 → 飞书入库 → Obsidian 归档，全自动。

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
