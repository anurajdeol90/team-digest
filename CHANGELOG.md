# Changelog
All notable changes will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.11] - 2025-10-21
### Added
- Trusted Publisher support for PyPI release.
- CLI: `daily`, `weekly`, and `monthly` commands stable.
- Executive KPIs + Owner breakdown in monthly digest.

### Fixed
- Weekly digest stable with grouped Actions and proper window handling.
- Daily digest date mismatch fixed.
- Removed duplicate priorities in Actions.

## [1.1.10] - 2025-10-20
### Added
- Slack integration tested.
- GitHub Actions workflows: daily, weekly, monthly.

## [1.1.4] - 2025-10-18
### Changed
- Repo cleaned up for customer-ready release.
- Normalized daily digest header to single date.

## [0.1.x] - Initial Development
- Basic parsing of logs from `/logs/notes-YYYY-MM-DD.md`.
