# Team Digest

[![PyPI](https://img.shields.io/pypi/v/team-digest.svg)](https://pypi.org/project/team-digest/)
[![Docs](https://img.shields.io/badge/docs-MkDocs-blue.svg)](https://anurajdeol90.github.io/team-digest/)

**Team Digest** turns free-form team notes or logs into a clean summary you can share.  
Output to **Markdown** or **JSON**, and optionally post to **Slack**.

---

## ✨ Features

- Parse ad-hoc logs into structured updates
- Export **Markdown** (`.md`) and **JSON**
- Optional **Slack** delivery (webhook)
- Works on **Windows / macOS / Linux**
- Ready-made schedules (GitHub Actions)
- Bundled **examples** inside the package so you can try immediately

---

## 🚀 Quick Start (no repo clone needed)

Install from PyPI:

```bash
pip install team-digest
```

Show version:

```bash
team-digest --version
```

Use the **bundled example logs** that ship inside the package:

```bash
# Resolve the packaged examples directory
python - <<'PY'
import importlib.resources as r, team_digest
print((r.files(team_digest) / "examples" / "logs").__fspath__())
PY
```

Render outputs:

```bash
# Save the examples path to a variable (bash/zsh)
LOGS_DIR="$(python - <<'PY'
import importlib.resources as r, team_digest
print((r.files(team_digest) / "examples" / "logs").__fspath__())
PY
)"

# Produce Markdown + JSON
team-digest --input "$LOGS_DIR" --format md   --output digest.md
team-digest --input "$LOGS_DIR" --format json --output digest.json
```

> 🪟 **Windows PowerShell** tip: Replace the `$(...)` subshell with:
>
> ```powershell
> $logsPath = @'
> import importlib.resources as r, team_digest
> print((r.files(team_digest) / "examples" / "logs").__fspath__())
> '@ | python -
> team-digest --input "$logsPath" --format md   --output digest.md
> team-digest --input "$logsPath" --format json --output digest.json
> ```

---

## 💬 Post to Slack (optional)

Provide a webhook via CLI or env var:

```bash
# Option 1: CLI flag
team-digest --input "$LOGS_DIR" --format md --post slack --slack-webhook "https://hooks.slack.com/services/XXX/YYY/ZZZ"

# Option 2: Environment variable (recommended for CI)
export TEAM_DIGEST_SLACK_WEBHOOK="https://hooks.slack.com/services/XXX/YYY/ZZZ"
team-digest --input "$LOGS_DIR" --format md --post slack
```

---

## ⏱️ Scheduling

- **GitHub Actions**: daily/weekly/monthly workflows are easy—install `team-digest` and run the CLI.
- **Windows Task Scheduler / cron**: run the same command on your cadence.

Example GitHub Action (daily):

```yaml
name: Daily Digest
on:
  schedule:
    - cron: "0 14 * * *" # 2pm UTC daily
jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install --upgrade pip team-digest
      - name: Resolve packaged examples (demo)
        id: logs
        run: |
          python - <<'PY' | tee logs_path.txt
          import importlib.resources as r, team_digest
          print((r.files(team_digest) / "examples" / "logs").__fspath__())
          PY
      - name: Render outputs
        run: |
          mkdir -p out
          team-digest --input "$(cat logs_path.txt)" --format md   --output out/digest.md
          team-digest --input "$(cat logs_path.txt)" --format json --output out/digest.json
          test -s out/digest.md && test -s out/digest.json
      # - name: Post to Slack (optional)
      #   run: team-digest --input "$(cat logs_path.txt)" --format md --post slack
      #   env:
      #     TEAM_DIGEST_SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
```

---

## 📚 Documentation

- **Getting Started / Quick Start / Schedules / Slack** → published docs  
  👉 https://anurajdeol90.github.io/team-digest/

---

## 🧩 Command Reference

```
usage: team-digest [-h] [--format {json,md}] [-o OUTPUT] [--config CONFIG]
                   [--from SINCE] [--to UNTIL]
                   [--input INPUT_DIR]
                   [--post {slack}] [--slack-webhook SLACK_WEBHOOK]
                   [-V] [path]
```

Common flags:

- `--input <dir>`: directory of logs to digest  
- `--format md|json`: choose output format  
- `--output <file>`: write to file  
- `--post slack`: send to Slack (use with `--slack-webhook` or env var)  
- `-V` / `--version`: show version

---

## 📄 License

MIT © Anuraj Deol
