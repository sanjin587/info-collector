# Changelog

All notable changes to this project will be documented here.

The project follows Semantic Versioning for published releases.

## [2.0.0] - 2026-09-18

### Added

- Unified `scripts/collector.py` CLI entry point
- Platform detection for supported video links and local media files
- Multi-step fallback chains for collection/transcription
- Transcript quality validation before accepting CDP output
- Local Whisper and Paraformer transcription paths
- Feishu and Obsidian workflow integration
- Portable transcript output configuration
- Contributor, security, agent-maintenance, test, and CI scaffolding

### Changed

- Removed the maintainer-specific hard-coded Obsidian path from the unified collector
- Clarified which capabilities are implemented in this repository and which are provided by upstream open-source projects
- Aligned Node package metadata with the planned 2.0.0 release

### Maintenance

- Added lightweight tests for core logic
- Added GitHub Actions CI
- Added release and contribution documentation

## [1.0.0] - 2026-07-25

### Added

- Initial public information-collection toolkit
- Multi-platform collection helpers
- Local transcription helpers
- Feishu and Obsidian synchronization scripts
