# Contributing to info-collector

Thanks for helping improve `info-collector`.

## What contributions are useful

- Bug fixes and compatibility fixes
- Tests for link detection, transcript validation, fallback behavior, and data normalization
- Documentation and setup improvements
- Cross-platform portability improvements
- Safer configuration handling
- Small, well-scoped integrations that fit the existing workflow

## Development setup

The project is Windows-first for its interactive `.bat` entry points, while core Python tests should remain portable.

For lightweight development checks:

```bash
python -m pip install pytest
python -m compileall scripts feishu utils
pytest -q
npm ci --ignore-scripts
node --check scripts/sync-to-feishu.js
node --check pipeline/run.js
node --check pipeline/feishu-auto-transcribe.js
node --check pipeline/feishu-link-transcribe.js
```

Full runtime features may also require Python dependencies, Node.js, Chrome, ffmpeg,
MediaCrawler, agent-reach, credentials, or platform login state.

## Pull request guidelines

1. Keep each PR focused.
2. Explain the problem before the implementation.
3. Add or update tests for behavior changes when practical.
4. Do not commit credentials, cookies, access tokens, private chat data, downloaded media, or local absolute paths.
5. Do not make unrelated formatting or refactoring changes in the same PR.
6. Preserve attribution and licensing for upstream projects.
7. If a platform integration changes because an upstream service changed, document the affected platform and failure mode.

## Privacy and data handling

This project may process locally stored or downloaded content. Contributors must not
include real private user data in tests, examples, fixtures, issues, or pull requests.
Use synthetic examples.

## Legal and platform rules

Contributions should not be designed to bypass authentication, access controls, rate
limits, anti-abuse protections, or platform restrictions. Users are responsible for
complying with applicable law and platform terms.

## Commit messages

Prefer short, descriptive messages such as:

- `fix: remove user-specific output path`
- `test: cover fallback chain`
- `docs: clarify upstream dependencies`
