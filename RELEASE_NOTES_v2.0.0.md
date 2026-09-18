# info-collector v2.0.0

`v2.0.0` turns info-collector from a collection of platform-specific helpers into a
more coherent open-source workflow with a unified CLI and fallback-based transcription.

## Highlights

- Unified `scripts/collector.py` entry point
- Automatic platform detection for supported video links and local media
- Multi-stage fallback chains instead of single-path failure
- CDP transcript-quality validation before results are accepted
- Whisper and Paraformer transcription paths
- Feishu and Obsidian integration
- Portable output configuration instead of a maintainer-specific local path
- Initial unit tests and GitHub Actions CI
- Contributor, security, changelog, and agent-maintenance documentation

## Upstream projects

This repository intentionally builds on and integrates upstream open-source tools,
including MediaCrawler, agent-reach, OpenAI Whisper, Playwright, and yt-dlp. Please see
the README and the upstream projects for their respective licenses and documentation.

## Upgrade notes

If you previously relied on the maintainer-specific Obsidian output path, configure one
of the following:

- `OBSIDIAN_OUTPUT_DIR` for an explicit transcript output directory, or
- `OBSIDIAN_VAULT_PATH` for an Obsidian Vault root.

If neither is configured, transcripts from the unified collector are written to:

`./outputs/transcripts/`

## Validation before publishing

Before creating the GitHub release, verify:

```bash
python -m compileall scripts feishu utils
python -m pip install pytest
pytest -q
npm ci --ignore-scripts
node --check scripts/sync-to-feishu.js
node --check pipeline/run.js
node --check pipeline/feishu-auto-transcribe.js
node --check pipeline/feishu-link-transcribe.js
```

Do not publish the release until CI passes on the merged commit.
