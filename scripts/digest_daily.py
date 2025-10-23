#!/usr/bin/env python
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from team_digest.team_digest_runtime import aggregate_range


def _write_output(text: str, output: str | None) -> None:
    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    else:
        print(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs-dir", required=True)
    ap.add_argument("--date", type=lambda s: dt.date.fromisoformat(s), required=True)
    ap.add_argument("--output")
    ap.add_argument("--group-actions", action="store_true")
    ap.add_argument("--flat-by-name", action="store_true")
    ap.add_argument("--emit-kpis", action="store_true")
    ap.add_argument("--owner-breakdown", action="store_true")
    ap.add_argument("--owner-top", type=int, default=8)
    a = ap.parse_args()

    text = aggregate_range(
        logs_dir=Path(a.logs_dir),
        start=a.date,
        end=a.date,
        group_actions=a.group_actions,
        flat_by_name=a.flat_by_name,
        emit_kpis=a.emit_kpis,
        owner_breakdown=a.owner_breakdown,
        owner_top=a.owner_top,
    )
    _write_output(text, a.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
