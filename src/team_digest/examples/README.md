# Examples — Team Digest

This folder contains working examples of **logs** and **configs** that you can use
to quickly test `team-digest`.

## Structure

examples/
logs/
notes-2025-10-13.md
notes-2025-10-14.md

...

configs/
prod.yml
README.md ← this file


## Usage

To run against these sample logs:

```bash
# Daily
team-digest daily --logs-dir examples/logs --date 2025-10-13 --output outputs/daily.md --group-actions

# Weekly
team-digest weekly --logs-dir examples/logs --start 2025-10-13 --end 2025-10-19 --output outputs/weekly.md --group-actions --emit-kpis --owner-breakdown

# Monthly
team-digest monthly --logs-dir examples/logs --output outputs/monthly.md --group-actions --emit-kpis --owner-breakdown

Notes

The sample logs are fictional but demonstrate expected structure.

The prod.yml config file illustrates how you could map owners, Slack posting, etc.



