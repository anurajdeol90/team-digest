\# Changelog

All notable changes to this project will be documented in this file.



The format is based on \[Keep a Changelog](https://keepachangelog.com/en/1.1.0/),

and this project adheres to \[Semantic Versioning](https://semver.org/).



\## \[Unreleased]

\- Placeholder for upcoming changes.



\## \[0.1.0] - 2025-10-07

\### Added

\- Initial release of \*\*Team Digest\*\*.

\- Digest generator (`team\_email\_digest.py`) with config-driven inputs.

\- Slack posting (`post\_digest.py`) with webhook support.

\- Weekly runner (`weekly\_digest.py`) with Task Scheduler automation.

\- CI workflow with lockfile support and tests.

\- Log rotation for stable long-term use.

\- MIT License and README documentation.

# Changelog

## [0.1.0] - 2025-10-07
- Phase 1–3: Digest generation, Slack posting, Windows Task Scheduler.
- Phase 4A: GitHub Actions CI on Ubuntu + Windows, coverage artifact, pip cache.
- Robust CLI JSON output for CI; safer Slack behavior; output dir auto-create.
- README + license + config example.




## [1.0.0-rc.1] - 2025-10-14
- Release candidate for v1.0.0

## [1.0.0] - 2025-10-14
- First stable release

## [1.0.0] - 2025-10-14
- First stable release

## [1.0.0-rc.2] - 2025-10-14
- Fix: remove BOM in pyproject; retry RC publish

## [1.0.0] - 2025-10-14
- First stable release

## [1.0.0] - 2025-10-14
- First stable release

## [1.0.1] - 2025-10-14
- Publish stable build via new tag

## [1.0.2] - 2025-10-14
- Fix: CLI --version now shows the installed package version

## [1.0.3] - 2025-10-14
- Fix: CLI --version now reports the installed package version

## [1.0.4] - 2025-10-14
- Fix: corrected CLI --version argument formatting

## [1.0.5] - 2025-10-14
- Fix: correct CLI --version output and remove malformed parser line

## [1.0.7] - 2025-10-14
- CLI: correct --version and stabilize parser; add run() hook

## [1.0.8] - 2025-10-14
- CLI now renders real digests from logs; supports YAML/JSON config; md/json outputs

## [1.0.9] - 2025-10-14
- CLI: resilient __version__ in source/CI contexts; CI installs package before tests

## [1.0.10] - 2025-10-14
- Fix: UTF-8 decode error in runtime; normalize punctuation

## [1.1.0] - 2025-10-14
- Slack delivery (--post slack, --slack-webhook) and scheduled workflow

## [1.1.1] - 2025-10-14
- Publish Slack delivery features
