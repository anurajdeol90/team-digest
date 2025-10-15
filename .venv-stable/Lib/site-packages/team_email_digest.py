# team_email_digest.py
# CLI for Team Digest
# - Correct --version using importlib.metadata
# - Stable, explicit argparse configuration

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Optional

# Version comes from installed distribution metadata (no hard-coding)
try:
    from importlib.metadata import version as _pkg_version
except ImportError:  # pragma: no cover (py<3.8)
    from importlib_metadata import version as _pkg_version  # type: ignore

__version__ = _pkg_version("team-digest")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="team-digest",
        description="Generate a team digest (JSON or Markdown) from logs/notes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Keep this legacy positional to preserve your current interface
    parser.add_argument(
        "path",
        nargs="?",
        help="(unused) legacy positional",
    )

    parser.add_argument(
        "--format",
        choices=("json", "md"),
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Optional output file path. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--config",
        dest="config",
        help="Optional config file (JSON or YAML).",
    )
    parser.add_argument(
        "--from",
        dest="since",
        metavar="SINCE",
        help="Include entries from this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to",
        dest="until",
        metavar="UNTIL",
        help="Include entries until this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--input",
        dest="input_dir",
        metavar="INPUT_DIR",
        help="Input dir or file (default: '-' for stdin).",
    )

    # Correct version flag (no string/indent errors)
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit",
    )

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
) -> int:
    """
    PLACE YOUR EXISTING GENERATION LOGIC HERE.

    This stub preserves the CLI interface so your users arenâ€™t broken.
    If your real implementation lives in another module, import and call it here, e.g.:

        from team_digest.runtime import generate_digest
        content = generate_digest(fmt=fmt, config=config, since=_parse_date(since), ...)

    For now, we emit a minimal placeholder so the CLI works end-to-end.
    """
    # ---- BEGIN minimal placeholder (safe, replace with your real logic) ----
    payload = {
        "ok": True,
        "format": fmt,
        "config": config,
        "since": since,
        "until": until,
        "input": input_dir or "-",
        "path": legacy_path,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "version": __version__,
        "message": "team-digest CLI is wired. Replace run() with your real generator.",
    }

    if fmt == "json":
        rendered = json.dumps(payload, indent=2)
    else:
        # tiny MD summary; replace with your Jinja template output
        lines = [
            f"# Team Digest ({datetime.utcnow().date().isoformat()})",
            "",
            f"- config: {config or 'none'}",
            f"- since: {since or 'n/a'}",
            f"- until: {until or 'n/a'}",
            f"- input: {input_dir or '-'}",
            f"- version: {__version__}",
            "",
            "_Replace this stub with your real digest rendering._",
        ]
        rendered = "\n".join(lines)
    # ---- END minimal placeholder ----

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered + ("\n" if not rendered.endswith("\n") else ""))

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
    )


if __name__ == "__main__":
    raise SystemExit(main())
