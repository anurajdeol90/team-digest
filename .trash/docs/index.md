
# Team Digest — Documentation

Welcome! This guide helps you install, try the examples, post to Slack, and schedule digests.

## Install
```bash
pip install team-digest
team-digest --version
```

## Try the bundled example
```bash
python - <<'PY'
import importlib.resources as r, team_digest
print((r.files(team_digest) / "examples" / "logs").__fspath__())
PY
```

## Render outputs
```bash
LOGS_DIR="$(python - <<'PY'
import importlib.resources as r, team_digest
print((r.files(team_digest) / "examples" / "logs").__fspath__())
PY
)"
team-digest --input "$LOGS_DIR" --format md   --output digest.md
team-digest --input "$LOGS_DIR" --format json --output digest.json
```

## Slack
Set `TEAM_DIGEST_SLACK_WEBHOOK` and add `--post slack`.

## Schedules
- GitHub Actions: see templates in `.github/workflows/`
- Windows Task Scheduler / cron: run the same CLI on your cadence.
