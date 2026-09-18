# info-collector OSS Readiness Patch

Target repository: `sanjin587/info-collector`
Target branch: `master`
Prepared for: Codex for Open Source application readiness

## Important

This package does **not** contain the whole repository. It contains:

1. `oss-readiness.patch` — changes to existing files.
2. New files to copy into the repository.
3. `RELEASE_NOTES_v2.0.0.md` — release draft.
4. `REPO_SETTINGS.md` — GitHub repository settings that must be changed in the GitHub UI/API.

## Recommended application order

1. Create a branch from `master`, for example:
   `codex-oss-readiness-20260918`
2. Apply `oss-readiness.patch`.
3. Copy the new files in this package into the repository root, preserving paths.
4. Run:
   `python -m compileall scripts feishu utils`
5. Run:
   `python -m pip install pytest`
6. Run:
   `pytest -q`
7. Run:
   `npm ci --ignore-scripts`
8. Run:
   `node --check scripts/sync-to-feishu.js`
   `node --check pipeline/run.js`
   `node --check pipeline/feishu-auto-transcribe.js`
   `node --check pipeline/feishu-link-transcribe.js`
9. Open a PR and verify CI.
10. Merge only after review.
11. Update repository Description/Topics from `REPO_SETTINGS.md`.
12. Publish `v2.0.0` only after the merged commit is verified.

## Scope

This patch intentionally does not change the core scraping/collection logic.
It focuses on portability, project hygiene, tests, CI, maintainer guidance,
release readiness, and truthful open-source presentation.
