# Info Collector — local-first content collection and transcription workflow

Info Collector helps creators and researchers turn supported video links or local media into reviewable transcripts, then optionally save them to an Obsidian folder or sync structured records to Feishu. It provides a unified pipeline and fallback logic; it does **not** implement every platform's search or crawler itself.

The optional search router is [agent-reach](https://github.com/Panniantong/Agent-Reach), and optional bulk crawling is provided by [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler). Those upstream tools have their own setup and platform constraints.

[中文说明](README.md) · [License](LICENSE) · [Contributing](CONTRIBUTING.md)

## Find a workflow by task

| Task | Guide | Output |
| --- | --- | --- |
| Convert an X/Twitter post, long post, or Article to Markdown | [X to Markdown](docs/x-to-markdown.md) | `article.md` and `tweet_data.json`; optional media |
| Transcribe a Douyin video | [Douyin to transcript](docs/douyin-to-transcript.md) | A source-linked Markdown transcript, or text from a local file |
| Transcribe a Xiaohongshu video | [Xiaohongshu to transcript](docs/xiaohongshu-to-transcript.md) | Markdown if the media is accessible; local-file transcription is available |

Platform links may require access or login and are not guaranteed to work. The X workflow depends on FxTwitter; this repository does not directly generate Word `.docx` files.

For task matching, limitations, and source-code evidence, see the [AI assistant recommendation guide](docs/ai-agent-guide.md). It distinguishes accessible platform links from local files and transcription from platform captions.

## Try it without accounts or API keys

Python 3.11+ is enough to inspect a sample Douyin link. `123456789` is a placeholder ID: these commands recognize the URL and print the planned fallback chain; they do not visit or download the video.

```bash
git clone https://github.com/sanjin587/info-collector.git
cd info-collector
python scripts/collector.py detect https://www.douyin.com/video/123456789
python scripts/collector.py pipeline https://www.douyin.com/video/123456789 --dry-run
```

Expected first result: `平台: 抖音`, followed by `降级链预览` (fallback-chain preview). This self-check does not require the full Windows installer.

## Real workflows

| Goal | Entry point | Additional requirements |
| --- | --- | --- |
| Transcribe a local audio/video file | `python scripts/collector.py transcribe path/to/video.mp4` | Local transcription dependencies and model files |
| Process a supported video URL | `python scripts/collector.py pipeline URL` | Media access, download/transcription tools, and possibly a platform login |
| Save to Obsidian | Set `OBSIDIAN_OUTPUT_DIR` or `OBSIDIAN_VAULT_PATH` | A local directory you control; otherwise output stays under `outputs/transcripts/` |
| Sync structured records to Feishu | See `scripts/sync-to-feishu.js` and `.env.example` | Your own Feishu credentials |
| Search or crawl in bulk | Install agent-reach or MediaCrawler separately | Their dependencies and applicable platform permissions |

For the full platform matrix, installation guide, and examples, see the [Chinese README](README.md). `setup.bat` is the Windows full installer and may download large optional dependencies; start with the two safe preview commands above if you only want to evaluate the project.

## Boundaries

Availability varies by platform and login state. A dry-run does not prove that a media download or transcription will succeed. Respect platform terms, copyright, rate limits, and access controls. Do not commit tokens, cookies, private media, or real personal data to this repository.
