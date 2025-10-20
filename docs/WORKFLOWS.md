# Workflows & Options

## Daily
- Auto-picks today → yesterday → last weekday → latest available.
- Flags: `--group-actions` (on), `--flat-by-name` (off)

## Weekly
- Defaults to last full **Mon–Sun** window (UTC). Inputs override.
- Options at dispatch:
  - `flat_by_name`: one flat list, Name→Priority sorting.
  - `group_actions`: bucket High/Medium/Low (default).
  - (Optional) KPIs: add `--emit-kpis` in workflow if you want a leadership view.

## Monthly
- Defaults to previous calendar month. Inputs override (`year`, `month`).
- Enabled by default in workflow: `--emit-kpis --owner-breakdown`.

## Slack
- Webhook via secret `SLACK_WEBHOOK_URL`. If absent, skip posting.

## Artifacts
- Daily: `outputs/daily.md`
- Weekly: `outputs/weekly.md`
- Monthly: `outputs/monthly.md`
