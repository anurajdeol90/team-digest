# Configuration

`team-digest` reads inputs from a directory of Markdown/notes and produces a JSON or Markdown digest.

## CLI flags (quick)
- `--format {json,md}`  Default: `json`
- `-o, --output PATH`  Write to file (or stdout if omitted)
- `--from YYYY-MM-DD`  Start date (inclusive)
- `--to   YYYY-MM-DD`  End date (inclusive)
- `--input DIR`        Input directory (default: `-` for stdin)
- `--config FILE`      Optional YAML/JSON config
- `-V, --version`      Show version and exit

## GitHub Actions variables

| Name                 | Type     | Purpose                                   | Example          |
|----------------------|----------|-------------------------------------------|------------------|
| `DIGEST_INPUT_DIR`   | variable | Input root for logs                       | `logs/alpha`     |
| `DIGEST_TEAM`        | variable | Label/team tag included in digest         | `alpha`          |
| `SLACK_WEBHOOK_URL`  | secret   | If set, posts the digest to Slack         | `https://hooks…` |
| `PYPI_API_TOKEN`     | secret   | For release workflow (optional)           | `pypi-AgEN…`     |

## Email (optional)
Provide these secrets if you plan to email digests:
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- `DIGEST_EMAIL_FROM`, `DIGEST_EMAIL_TO`
