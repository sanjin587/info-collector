# X / Twitter 帖子与长文章转 Markdown

想把一条 X 帖子、长推文（Note Tweet）或 X Article 保存为能检索、引用和后续整理的文档，可用本仓库的 `scripts/x_capture.py`。输入是公开可访问的帖子 URL 或帖子 ID；输出是 Markdown，不是 Word `.docx`。

适合搜索“X 帖子保存为 Markdown”“Twitter 长文章导出 Markdown”“X Article 转文档”的人。这里的“文档”指 `.md` 文件：可用 Obsidian、VS Code 等打开，也可由你自行转换成其他格式；本项目没有直接生成 `.docx` 的功能。

## 最短用法

在仓库根目录运行：

```bash
python scripts/x_capture.py "https://x.com/用户名/status/帖子ID" --no-download
```

把 `用户名`、`帖子ID` 换成真实帖子链接中的值。先确认已安装 Python 3.11+；这条**仅文本**路径使用 Python 标准库，无需先安装整套视频转录依赖。`--no-download` 只是不下载图片/视频，仍会请求 FxTwitter API 并写文件。

成功后的目录结构大致如下（数字取决于你输入的帖子）：

```text
downloads/<帖子ID>/
├── article.md          # 可阅读的正文、来源和元数据
├── tweet_data.json     # 上游返回的结构化数据
└── checksums.sha256    # 已下载文件的校验清单；纯文本时可能没有媒体条目
```

需要保存可获取的原图或视频时，去掉 `--no-download`：`python scripts/x_capture.py "<真实X帖子URL>"`。这时脚本会尝试下载媒体，并在有 `ffprobe` 时检查媒体文件；媒体获取失败不等于文字一定失败。用 `-o <目录>` 可指定输出路径。不要将示例中的尖括号和中文占位符原样传给脚本。

## 它怎样处理长文章？

脚本会按返回的 Article blocks/entityMap 重组正文；普通帖使用帖子文本。`tweet_data.json` 保留结构化返回，`article.md` 包含来源链接和作者等原始字段。若上游没有返回完整 Article 内容，本工具不能凭空补齐；请对照原帖检查长文、图片及引用是否完整。API 不可用、受限帖子或媒体下载失败时不保证产物完整。

X Article 与普通帖的正文结构不同。本脚本读取 FxTwitter 返回的 `article.content.blocks`、`entityMap` 和媒体实体，再生成 `article.md`；如果返回内容只有预览，输出也只能反映预览。请特别检查段落顺序、图片、链接和引用；这一步不能由“命令退出 0”替代。帖子里的**视频语音不会被自动转写**，这条路径是帖文内容转 Markdown，不是 X 视频转逐字稿。

## 常见问题

- **为什么没有全文？** 先看 `tweet_data.json` 是否包含 Article 的正文 blocks。没有的话是上游未提供，本工具无法还原缺失文字。
- **为什么图片没下载？** `--no-download` 本来就只要文字；若没加该参数，检查原媒体链接是否可访问及脚本输出的下载错误。
- **能把整条账号时间线导出吗？** 这个入口处理单条帖子 URL/ID，不是账号批量采集器。
- **能转成 Word/PDF 吗？** 当前只生成 Markdown；不要把 `.md` 说成 `.docx`。
- **私人帖子能处理吗？** 不提供绕过登录、权限或访问限制的方法。

已有采集目录需要同步进 Obsidian 时，可另运行 `python scripts/x_sync_obsidian.py downloads/<帖子ID> --obsidian-root <你的Vault目录>`；先用 `--dry-run` 看目标路径。此同步是可选步骤，不是抓取的前提。

源码：[X 采集与 Markdown 生成](../scripts/x_capture.py) · [可选 Obsidian 同步](../scripts/x_sync_obsidian.py)。只处理你有权访问和保存的内容，并遵守平台规则与原作者权利。
