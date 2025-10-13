# Workflows

- **Daily Digest**: weekdays 9am CT → `outputs/daily_YYYY-MM-DD.md`
- **Weekly Digest**: Mondays 9am CT → `outputs/weekly_YYYY-ww.md` or range
- **Monthly Digest**: 1st of month 9am CT → `outputs/monthly_YYYY-MM.md`
- **Publish to Pages**: builds `/site` + lists `outputs/*.md` → GitHub Pages

Tips:
- Stagger schedules by a couple of minutes to avoid simultaneous writes.
- Each writer workflow uses `git pull --rebase` before push to reduce conflicts.
- If teams want isolation, create multiple repos or namespaced input dirs (e.g., `logs/alpha`).
