# Usage Guide

This document describes how to use **team-digest** from the command line.

---

## CLI Overview

```bash
team-digest [-h] {daily,weekly,monthly} ...
```

## Commands

- **daily** – Build a daily digest for a single date
- **weekly** – Build a digest for a date range (inclusive)
- **monthly** – Build a digest for a calendar month (or month-to-date)

---

## Common Options

- `--logs-dir PATH` – Path to a folder of Markdown logs
- `--date YYYY-MM-DD` – Single date (for daily mode)
- `--start YYYY-MM-DD` / `--end YYYY-MM-DD` – Date range (for weekly)
- `--output FILE` – Path to write the digest (.md or .json)
- `--format {md,json}` – Output format (default: md)
- `--group-actions` – Group actions by owner / type
- `--emit-kpis` – Include KPIs (weekly/monthly only)
- `--owner-breakdown` – Breakdown by log owner (weekly/monthly only)
- `--config FILE` – Use a YAML/JSON config file instead of CLI args
- `--post slack` + `--slack-webhook URL` – Post digest directly to Slack

---

## Examples

### Daily

```bash
team-digest daily \
  --logs-dir logs \
  --date 2025-10-17 \
  --output outputs/daily.md \
  --group-actions
```

### Weekly

```bash
team-digest weekly \
  --logs-dir logs \
  --start 2025-10-13 --end 2025-10-19 \
  --output outputs/weekly.md \
  --group-actions --emit-kpis --owner-breakdown
```

### Monthly

```bash
team-digest monthly \
  --logs-dir logs \
  --output outputs/monthly.md \
  --group-actions --emit-kpis
```

---

## Using Packaged Examples

If you installed from PyPI, you can use the bundled example logs/configs:

```bash
team-digest weekly \
  --logs-dir "$(python -m importlib.resources team_digest.examples.logs)" \
  --start 2025-10-13 --end 2025-10-19 \
  --output weekly.md
```

Or load them in Python:

```python
from importlib.resources import files
logs = files("team_digest.examples") / "logs"
print(list(logs.rglob("*.md")))
```

---

## Slack Integration

Set your webhook URL:

```bash
# Linux / macOS
export SLACK_WEBHOOK="https://hooks.slack.com/services/XXX/YYY/ZZZ"
# Windows PowerShell
$env:SLACK_WEBHOOK="https://hooks.slack.com/services/XXX/YYY/ZZZ"

```

Post a weekly digest:

```bash
team-digest weekly \
  --logs-dir logs \
  --start 2025-10-13 --end 2025-10-19 \
  --output weekly.md \
  --post slack
```

---

## Config File Mode

Instead of passing CLI flags, you can use a config:

```yaml
logs_dir: logs
output: outputs/weekly.md
start: 2025-10-13
end: 2025-10-19
group_actions: true
emit_kpis: true
owner_breakdown: true
```

Run with:

```bash
team-digest weekly --config configs/weekly.yml
```
