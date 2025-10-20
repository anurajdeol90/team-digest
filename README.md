# Team Digest

Automate **daily**, **weekly**, and optional **monthly** digests from repo-stored logs (`/logs/notes-YYYY-MM-DD.md`). Post to Slack and upload artifacts via GitHub Actions.

## Features
- Daily / Weekly / Monthly digests
- Priority grouping (**High / Medium / Low**) or **flat-by-name** sorting
- Executive KPIs and owner breakdown (monthly/weekly optional)
- Slack posting (via webhook), artifacts uploaded on each run
- Robust parsing (mojibake fixes, wide bullet support), safe defaults

## Quick Start (1 minute)
1. Add a few files under `logs/notes-YYYY-MM-DD.md` (see [`docs/LOG_FORMAT.md`](docs/LOG_FORMAT.md)).
2. Go to **GitHub → Actions**:
   - **Daily Digest → Run workflow** (leave date blank to auto-pick)
   - **Weekly Digest → Run workflow** (leave dates blank to use last full Mon–Sun)
   - **Monthly Digest → Run workflow** (leave month blank to use previous calendar month)
3. Download the artifact or check Slack (if webhook is set).

> Slack: set `SLACK_WEBHOOK_URL` in repo **Settings → Secrets → Actions**.

## Docs
- [Quick Start](docs/QUICKSTART.md)
- [Log Format](docs/LOG_FORMAT.md)
- [Workflows & Options](docs/WORKFLOWS.md)

## License
MIT
