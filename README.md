# Team Digest

Automated team digest generator with Slack posting, scheduling, and CI.

[![CI](https://github.com/anurajdeol90/team-digest/actions/workflows/ci.yml/badge.svg)](https://github.com/anurajdeol90/team-digest/actions/workflows/ci.yml)

---

## 📌 Overview

This project generates a **digest** of team updates, risks, and dependencies.  
It can run manually or fully automated (Slack + Task Scheduler + GitHub Actions).

---

## 🚀 Features

- Digest generation from team input files
- Owner map (initials → names)
- Risks/Blockers tracked separately
- Markdown output saved in `outputs/`
- Slack posting via incoming webhook
- Windows Task Scheduler automation
- CI pipeline (GitHub Actions) with lockfile support
- Tests included (pytest)

---

## ⚙️ Setup

### Requirements
- Windows 11  
- Python 3.11  
- GitHub repository  

### Install dependencies
```bash
pip install -r requirements.lock.txt
