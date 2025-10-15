# Workflows: manual & scheduled digests

## Manual runs (Publish Digests)
Actions → **Publish Digests** → “Run workflow”

Inputs:
- **digest**: `daily` | `weekly` | `monthly`
- **date** (optional): `YYYY-MM-DD` for daily/weekly, `YYYY-MM` for monthly
- **dry run**: if checked, no commit/publish
- **tz**: IANA time zone (default `UTC`) – affects timestamps in the generated digest

## Automatic runs (Schedules)
Three workflows call the reusable one:
- **Daily Digest (schedule)** – runs at the cron time in the file (UTC)
- **Weekly Digest (schedule)** – cron in UTC
- **Monthly Digest (schedule)** – cron in UTC

All three pass:
```yaml
tz: ${{ vars.DIGEST_TZ || 'UTC' }}
