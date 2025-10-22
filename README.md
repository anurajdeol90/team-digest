# team-digest

[![PyPI](https://img.shields.io/pypi/v/team-digest.svg)](https://pypi.org/project/team-digest/)
[![CI](https://github.com/AnurajDeol1990/team-digest/actions/workflows/verify-examples.yml/badge.svg)](https://github.com/AnurajDeol1990/team-digest/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Generate daily/weekly/monthly team email digests from Markdown logs and optionally deliver to Slack.

---

## Installation

```bash
pip install team-digest
```

## Quick Start

### Daily digest

```bash
team-digest daily --logs-dir logs --date 2025-10-17 --output outputs/daily.md --group-actions
```

### Weekly digest

```bash
team-digest weekly --logs-dir logs --start 2025-10-13 --end 2025-10-19 --output outputs/weekly.md --group-actions --emit-kpis --owner-breakdown
```

### Monthly digest

```bash
team-digest monthly --logs-dir logs --output outputs/monthly.md --group-actions
```

See [USAGE.md](USAGE.md) for detailed usage.

## Examples

Example logs and configs are bundled with the package:

```python
import importlib.resources as r
print(list(r.files("team_digest.examples").rglob("*")))
```

## License

MIT License.
