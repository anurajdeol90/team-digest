# Changelog

All notable changes to this project will be documented in this file.

## 1.1.13 — 2025-10-21
### Fixed
- Align `team_digest.__version__` with installed distribution metadata to prevent version drift.

### Packaging
- Ensure `src/team_digest/examples/**` (logs, configs, README) are included in wheel and sdist.
- Added CI workflow to verify packaged examples from PyPI and run daily/weekly/monthly against them.

## [1.1.12] - 2025-10-21
### Added
- Updated README and CHANGELOG for PyPI distribution.
- Enhanced monthly digest with Executive KPIs and Owner breakdown.

### Fixed
- Corrected CLI entrypoint usage (`team-digest daily|weekly|monthly`).
- Removed duplicate priority labels in Actions section.

## [1.1.11] - 2025-10-20
### Added
- Trusted Publisher configuration for PyPI release workflow.
- Daily, Weekly, and Monthly digests stabilized with correct date windows.

### Fixed
- Weekly digest date window to align with calendar week (Mon–Sun).
- Correct Slack posting integration for digests.

## [1.1.10] - 2025-10-19
### Added
- Support for grouping Actions by priority or flat sorting by name>priority.
- Monthly digest initial implementation.

### Fixed
- Robust matcher for parsing log sections and actions.

## [1.1.9] - 2025-10-17
### Added
- Diagnostics scripts for weekly digest window and actions parsing.

## [1.1.8] - 2025-10-16
### Fixed
- Workflow buttons restored by correcting YAML syntax in GitHub Actions.

## [1.1.7] - 2025-10-15
### Added
- Sample logs and outputs included in package for testing.
