# Team Digest

[![CI](https://github.com/anurajdeol90/team-digest/actions/workflows/ci.yml/badge.svg)](https://github.com/anurajdeol90/team-digest/actions/workflows/ci.yml)
[![Daily Digest](https://github.com/anurajdeol90/team-digest/actions/workflows/daily-digest.yml/badge.svg)](https://github.com/anurajdeol90/team-digest/actions/workflows/daily-digest.yml)
[![Weekly Digest](https://github.com/anurajdeol90/team-digest/actions/workflows/weekly-digest.yml/badge.svg)](https://github.com/anurajdeol90/team-digest/actions/workflows/weekly-digest.yml)
[![Monthly Digest](https://github.com/anurajdeol90/team-digest/actions/workflows/monthly-digest.yml/badge.svg)](https://github.com/anurajdeol90/team-digest/actions/workflows/monthly-digest.yml)

Automated team meeting digests: summarize updates, decisions, risks, and actions into Markdown or JSON, with optional Slack/email notifications.

---

## ✨ Features
- Parse logs or model outputs into structured summaries
- Export to **Markdown** or **JSON**
- Optional **Slack** & **Email (SMTP)** notifications
- GitHub Actions workflows for **Daily / Weekly / Monthly** cadences
- Optional owner mapping via config file
- Works on **Windows** and **Linux**

---

## 🚀 Quick Start

### 1) Clone the repository
```bash
git clone https://github.com/anurajdeol90/team-digest.git
cd team-digest
```

### 2) Install the CLI
```bash
pip install -U team-digest
```

### 3) Run locally (Markdown)
```bash
# Read from ./logs and write to outputs/
mkdir -p outputs
team-digest --input logs --format md > outputs/local_test.md
```

### 4) (Optional) Use a config file
```bash
team-digest --input logs --format md --config config.json > outputs/local_test.md
```

---

## 🧭 Workflows (what gets created)

- **Daily** (weekdays 9am Central) → `outputs/daily_YYYY-MM-DD.md` *(yesterday)*
- **Weekly** (Mondays 9am Central) → `outputs/weekly_YYYY-WW.md` *(previous week)*
- **Monthly** (1st @ 9am Central) → `outputs/monthly_YYYY-MM.md` *(previous month)*

Run on demand: **Actions → [workflow] → Run workflow** (branch: `main`).

---

## 🔧 Repository Configuration  
**Settings → Secrets and variables → Actions**

**Repository variables (optional)**
- `DIGEST_INPUT_DIR` (default: `logs`)
- `DIGEST_TEAM` (if your setup uses team routing)

**Repository secrets (optional)**
- **Slack**: `SLACK_WEBHOOK_URL`  
- **Email (SMTP)**: `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `DIGEST_EMAIL_FROM`, `DIGEST_EMAIL_TO`

---

## ✅ Repo Settings
- **Settings → Actions → General → Workflow permissions** → **Read and write permissions**

---

## 🧪 Verify
1. Add at least one file under `logs/` (or your `DIGEST_INPUT_DIR`).  
2. Run **Daily**, **Weekly**, and **Monthly** manually on `main`.  
3. Confirm new files appear under `outputs/` and (if configured) Slack/email arrive.
