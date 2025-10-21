# team-digest

[![PyPI](https://img.shields.io/pypi/v/team-digest.svg)](https://pypi.org/project/team-digest/)
[![GitHub Actions](https://github.com/anurajdeol90/team-digest/actions/workflows/ci.yml/badge.svg)](https://github.com/anurajdeol90/team-digest/actions)

Automated **daily, weekly, and monthly team digests** from repo-stored logs.  
Posts directly to Slack and saves as artifacts — designed for engineering teams, managers, and leadership.

---

## ✨ Features
- Generate **daily, weekly, and monthly** summaries from `logs/notes-YYYY-MM-DD.md`
- Group **Actions** by priority (`[high]`, `[medium]`, `[low]`)
- Executive KPIs view (for monthly)
- Slack integration via webhook
- Artifacts attached in CI/CD runs
- Works locally and with GitHub Actions

---

## 📦 Installation
```bash
pip install team-digest
```

Or in a fresh virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install team-digest
```

---

## 🚀 Usage

### Daily
```bash
team-digest daily   --logs-dir logs   --date 2025-10-17   --output outputs/daily.md   --group-actions
```

### Weekly
```bash
team-digest weekly   --logs-dir logs   --start 2025-10-13 --end 2025-10-19   --output outputs/weekly.md   --group-actions --emit-kpis --owner-breakdown
```

### Monthly
```bash
team-digest monthly   --logs-dir logs   --output outputs/monthly.md   --group-actions
```

See [QUICKSTART.md](docs/QUICKSTART.md) for full setup details.

---

## ⚙️ GitHub Actions
- `daily-digest.yml` → Runs every day at midnight UTC
- `weekly-digest.yml` → Runs every Monday morning
- `monthly-digest.yml` → Runs at start of the month
- Artifacts + Slack posts are included

---

## 📈 Example Output
![Example Screenshot](docs/example-digest.png)

---

## 📝 License
MIT © 2025 [Anuraj Deol](mailto:AnurajDeol90@gmail.com)
