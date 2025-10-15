# Team Digest

Automate team updates into clean **Markdown** or **JSON** digests. Point it at your notes/logs, and (optionally) send the result to **Slack** on a daily, weekly, or monthly schedule.

> Install in seconds. Works on Windows, macOS, and Linux.

---

## Quick Start

### Windows (PowerShell)
```powershell
# Write first digest to outputs\first.md using the included example logs
if (-not (Test-Path outputs)) { New-Item -ItemType Directory outputs | Out-Null }; team-digest --input .\examples\logs --format md > .\outputs\first.md
