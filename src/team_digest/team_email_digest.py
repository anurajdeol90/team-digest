# team_email_digest.py
# CLI for Team Digest
# - Correct --version using importlib.metadata (resilient in source/CI)
# - Stable argparse
# - Calls generator and can post to Slack via webhook

from __future__ import annotations

import os
import argparse
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Optional

# Resilient version detection: installed metadata or source fallback
try:
    from importlib.metadata import version as _pkg_version  # py>=3.8
except Exception:  # pragma: no cover
    try:
        from importlib_metadata import version as _pkg_version  # backport
    except Exception:
        _pkg_version = None  # type: ignore

if _pkg_version is not None:
    try:
        __version__ = _pkg_version("team-digest")
    except Exception:
        __version__ = os.environ.get("TEAM_DIGEST_VERSION", "0+source")
else:
    __version__ = os.environ.get("TEAM_DIGEST_VERSION", "0+source")

# Import generator and optional Slack delivery
from team_digest.team_digest_runtime import generate_digest
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="team-digest",
        description="Generate a team digest (JSON or Markdown) from logs/notes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Legacy positional retained to avoid breaking existing users
    parser.add_argument("path", nargs="?", help="(unused) legacy positional")

    parser.add_argument("--format", choices=("json", "md"), default="json", help="Output format")
    parser.add_argument("-o", "--output", dest="output", help="Optional output file path. If omitted, prints to stdout.")
    parser.add_argument("--config", dest="config", help="Optional config file (JSON or YAML).")
    parser.add_argument("--from", dest="since", metavar="SINCE", help="Include entries from this date (YYYY-MM-DD).")
    parser.add_argument("--to", dest="until", metavar="UNTIL", help="Include entries until this date (YYYY-MM-DD).")
    parser.add_argument("--input", dest="input_dir", metavar="INPUT_DIR", help="Input dir or file (default: '-' for stdin).")

    # Delivery options
    parser.add_argument("--post", choices=("slack",), help="Optional delivery channel for the rendered digest.")
    parser.add_argument("--slack-webhook", dest="slack_webhook", help="Slack Incoming Webhook URL (or set env SLACK_WEBHOOK).")

    # Correct version flag
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}", help="Show version and exit")
    return parser


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def run(
    *,
    fmt: str,
    output: Optional[str],
    config: Optional[str],
    since: Optional[str],
    until: Optional[str],
    input_dir: Optional[str],
    legacy_path: Optional[str],
    post: Optional[str],
    slack_webhook: Optional[str],
) -> int:
    content = generate_digest(
        fmt=fmt,
        config_path=config,
        since=_parse_date(since),
        until=_parse_date(until),
        input_dir=input_dir,
    )

    # Write or print
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content if content.endswith("\n") else content + "\n")

    # Optional delivery
    if post == "slack":
        webhook = slack_webhook or os.environ.get("SLACK_WEBHOOK")
        if not webhook:
            raise SystemExit("Slack posting requested but no webhook provided. Use --slack-webhook or SLACK_WEBHOOK env.")
        (__import__("slack_delivery").slack_delivery.post_markdown)(webhook, content)

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        fmt=args.format,
        output=args.output,
        config=args.config,
        since=args.since,
        until=args.until,
        input_dir=args.input_dir,
        legacy_path=args.path,
        post=args.post,
        slack_webhook=args.slack_webhook,
    )


if __name__ == "__main__":
    raise SystemExit(main())

