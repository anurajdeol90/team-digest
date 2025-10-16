# team-digest

**Automated daily/weekly/monthly team digests — delivered to Slack.**

`team-digest` parses your team’s logs/notes, generates JSON or Markdown digests, and optionally posts them to a Slack channel via Incoming Webhook. It’s designed for small teams that want structured updates without manual effort.

---

## ✨ Features
- Generate **JSON or Markdown digests** from log files, notes, or input directories.
- Flexible scheduling: run manually, via **GitHub Actions**, or **Windows Task Scheduler**.
- **Slack integration** out of the box.
- Easy config with **YAML/JSON**.
- Lightweight and dependency-minimal.

---

## 📦 Installation
Requires **Python 3.9+**.

```bash
pip install team-digest
```

---

## 🚀 Quickstart

1. Prepare a directory with simple logs/notes, e.g.:

   ```
   logs/
     2025-10-01.txt
     2025-10-02.txt
   ```

   Contents:
   ```
   2025-10-01: Fixed login bug (#123); owner: anuraj
   2025-10-02: Added weekly digest job; owner: anuraj
   ```

2. Run `team-digest` locally:

   ```bash
   # JSON output
   team-digest --input logs --format json -o digest.json

   # Markdown output
   team-digest --input logs --format md -o digest.md
   ```

3. Post to Slack (using env var):

   ```powershell
   $env:SLACK_WEBHOOK="https://hooks.slack.com/services/XXX/YYY/ZZZ"
   team-digest --input logs --format md --post slack
   ```

---

## ⚙️ Configuration

You can also supply a config file (YAML or JSON):

```yaml
# team_digest.yaml
slack_webhook: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
schedule: daily
sources:
  - "logs"
```

Run with:

```bash
team-digest --config team_digest.yaml --format md --post slack
```

---

## 📅 Scheduling Options

### GitHub Actions (cloud-friendly)

Add a workflow like `.github/workflows/daily-digest.yml`:

```yaml
name: daily-digest
on:
  schedule:
    - cron: "0 13 * * 1-5" # 8am America/Chicago on weekdays
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: |
          python -m pip install --upgrade pip
          pip install "team-digest>=1.1.6,<2"
      - name: Run digest and post to Slack
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
        run: |
          mkdir -p outputs
          team-digest --format md --post slack --input logs || true
      - uses: actions/upload-artifact@v4
        with:
          name: daily-digest
          path: outputs/**
```

> Set `SLACK_WEBHOOK` in your repo’s **Settings → Secrets and variables → Actions**.

### Windows Task Scheduler (on-prem teams)

```powershell
# Daily at 8am
schtasks /Create /TN "TeamDigestDaily" /TR "powershell -NoProfile -Command team-digest --format md --post slack --input C:\Data\logs" /SC DAILY /ST 08:00

# Weekly Monday 9am
schtasks /Create /TN "TeamDigestWeekly" /TR "powershell -NoProfile -Command team-digest --format md --post slack --input C:\Data\logs" /SC WEEKLY /D MON /ST 09:00

# Monthly 1st 9am
schtasks /Create /TN "TeamDigestMonthly" /TR "powershell -NoProfile -Command team-digest --format md --post slack --input C:\Data\logs" /SC MONTHLY /D 1 /ST 09:00
```

---

## 🔑 CLI Reference

```text
usage: team-digest [-h] [--format {json,md}] [-o OUTPUT] [--config CONFIG]
                   [--from SINCE] [--to UNTIL] [--input INPUT_DIR]
                   [--post {slack}] [--slack-webhook SLACK_WEBHOOK] [-V]
                   [path]

Generate a team digest (JSON or Markdown) from logs/notes.

optional arguments:
  -h, --help            Show this help message and exit
  --format {json,md}    Output format (default: json)
  -o OUTPUT             Output file path (default: stdout)
  --config CONFIG       Config file (YAML or JSON)
  --from SINCE          Include entries from this date (YYYY-MM-DD)
  --to UNTIL            Include entries until this date (YYYY-MM-DD)
  --input INPUT_DIR     Input dir or file (default: stdin)
  --post {slack}        Post to Slack (requires webhook)
  --slack-webhook URL   Slack Incoming Webhook URL (or set env SLACK_WEBHOOK)
  -V, --version         Show version and exit
```

---

## 🐞 Troubleshooting
- **`ModuleNotFoundError`** after install → ensure you’re on `team-digest >= 1.1.6`.
- **Slack not posting** → confirm the webhook URL is valid and points to the intended channel.
- **GitHub Action not firing** → check cron syntax; note times are in **UTC**.
- **Windows Task Scheduler not running** → ensure the full path to `team-digest` is resolvable.

---

## 📜 License
MIT License. See [LICENSE](LICENSE).

---

## 🙌 Credits
Built and maintained by [Anuraj Deol](https://github.com/anurajdeol90).
