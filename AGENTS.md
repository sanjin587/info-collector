# AGENTS.md

Repository guidance for coding agents and automated maintenance tools.

## Project purpose

`info-collector` is an open-source workflow that connects content collection/search
components with transcription, fallback logic, Feishu synchronization, and Obsidian
ingestion.

Some search/crawling functionality is provided by upstream open-source projects such as
MediaCrawler and agent-reach. Do not describe those upstream capabilities as code authored
by this repository.

## Change policy

- Keep changes small and reviewable.
- Do not change core collection behavior unless the task explicitly requires it.
- Prefer portability over maintainer-specific defaults.
- Never add absolute paths tied to one developer's machine.
- Never add secrets, cookies, tokens, private chat data, or real private fixtures.
- Preserve MIT licensing and upstream attribution.
- Do not add functionality intended to bypass authentication, access controls, rate
  limits, or anti-abuse protections.

## Validation

For changes that do not require live platform access, run:

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

If a change affects a live platform integration and cannot be tested in CI, state that
limitation clearly in the PR.

## Important files

- `scripts/collector.py` — unified pipeline and fallback logic
- `scripts/transcribe_local.py` — local media transcription
- `scripts/media_crawler_bridge.py` — upstream crawler bridge
- `scripts/sync_to_obsidian.py` — Obsidian ingestion
- `scripts/sync-to-feishu.js` — Feishu sync
- `feishu/` — Feishu API helpers
- `pipeline/` — Feishu/transcription automation
- `.env.example` — documented optional configuration

## Tests

Core tests should avoid network calls, real credentials, browser automation, and external
platform state. Prefer deterministic unit tests for detection, validation, parsing, and
fallback control flow.

## Documentation

README claims must match repository reality. When an upstream project provides a feature,
name the upstream project rather than implying the functionality is implemented here.
