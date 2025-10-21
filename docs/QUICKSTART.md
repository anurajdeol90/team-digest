\# Quick Start



\## 1) Prepare logs

Create files under `logs/notes-YYYY-MM-DD.md`. See \[Log Format](LOG\_FORMAT.md).



\## 2) Run a digest

\- Daily: \*\*Actions → Daily Digest → Run\*\* (leave date blank).

\- Weekly: \*\*Actions → Weekly Digest → Run\*\* (uses last full Mon–Sun by default).

\- Monthly: \*\*Actions → Monthly Digest → Run\*\* (defaults to previous month).



\## 3) Slack (optional)

Set `SLACK\_WEBHOOK\_URL` as a repository secret. The workflows will post when present.



\## 4) Options you can toggle at run time

\- \*\*flat\_by\_name\*\* (weekly/monthly): sort globally by \*Name → Priority → Text\*.

\- \*\*group\_actions\*\* (default): bucket \*\*High / Medium / Low\*\* with owner-sort inside.

\- \*\*KPIs\*\*: monthly and weekly can emit executive KPIs + top owners table (enabled in workflow).



