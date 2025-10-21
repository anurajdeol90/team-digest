# team-digest

[![PyPI version](https://badge.fury.io/py/team-digest.svg)](https://pypi.org/project/team-digest/)
[![Build Status](https://github.com/anurajdeol90/team-digest/actions/workflows/ci.yml/badge.svg)](https://github.com/anurajdeol90/team-digest/actions)

Generate **daily, weekly, and monthly digests** from team meeting notes or logs — then share them in Slack or email.

---

## ✨ Features

- 📅 **Daily / Weekly / Monthly digests** from Markdown notes.
- ⚡ **CLI-based**: run locally, in cron, Task Scheduler, or GitHub Actions.
- 📊 **Executive KPIs** in weekly/monthly: actions, decisions, risks, owners.
- 📌 **Custom grouping**: by priority or globally by owner.
- 🔗 **Slack integration**: post digests directly to team channels.
- 🛠️ **Configurable**: JSON/YAML config support for repeatable setups.

---

## 🚀 Quick Start

Install from [PyPI](https://pypi.org/project/team-digest/):

```bash
pip install team-digest
```

Check version:

```bash
team-digest --version
```

---

## 📂 Input format

Put your daily notes into `logs/` as Markdown (`.md`) files:

```markdown
# Team Notes (2025-10-17)

## Decisions
- Switch weekly digest to last full calendar week.

## Actions
- [high] Sam to patch weekly-digest.yml date window.
- [medium] Anuraj Deol to retest with multiple logs in place.

## Risks
- Risk of shipping with incorrect weekly logic.
```

---

## 🖥️ CLI Usage

### Daily digest

```bash
team-digest daily \
  --logs-dir logs \
  --date 2025-10-17 \
  --output outputs/daily.md \
  --group-actions
```

### Weekly digest

```bash
team-digest weekly \
  --logs-dir logs \
  --start 2025-10-13 --end 2025-10-19 \
  --output outputs/weekly.md \
  --group-actions --emit-kpis --owner-breakdown
```

### Monthly digest

```bash
team-digest monthly \
  --logs-dir logs \
  --output outputs/monthly.md \
  --group-actions --emit-kpis --owner-breakdown
```

---

## 📊 Example Output

### Weekly Digest

```
# Team Digest (2025-10-13 – 2025-10-19)

_Range: 2025-10-13 → 2025-10-19 | Days matched: 5 | Actions: 15_

## Executive KPIs
- **Actions:** 15 (High: 5, Medium: 5, Low: 5)
- **Decisions:** 7   ·   **Risks:** 5
- **Owners:** 4   ·   **Days with notes:** 5
```

(See more samples in the [`examples/`](examples) folder.)

---

## 🔗 Slack Integration

You can post digests automatically to Slack:

```bash
team-digest weekly \
  --logs-dir logs \
  --start 2025-10-13 --end 2025-10-19 \
  --output outputs/weekly.md \
  --post slack \
  --slack-webhook $SLACK_WEBHOOK
```

Set `$SLACK_WEBHOOK` in your environment (via Secrets, .env, or GitHub Actions).

---

## ⚙️ Configuration (optional)

Instead of passing flags, use a config file:

```yaml
logs_dir: logs
output: outputs/daily.md
group_actions: true
emit_kpis: true
owner_breakdown: true
```

Run with:

```bash
team-digest daily --config config.yml
```

---

## 🛠️ GitHub Actions (automation)

Example `.github/workflows/daily.yml`:

```yaml
name: Daily Digest
on:
  schedule:
    - cron: "0 12 * * *"   # every day at noon UTC
jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install team-digest
      - run: team-digest daily --logs-dir logs --output outputs/daily.md --group-actions
      - run: cat outputs/daily.md
```

---

## 📈 Roadmap

- [x] Daily digests
- [x] Weekly digests with KPIs
- [x] Monthly digests with executive summaries
- [ ] Export to email
- [ ] More integrations (Teams, Confluence)

---

## 📜 License

[MIT](LICENSE) © Anuraj Deol
