#!/usr/bin/env python3
"""
Minimal digest generator used by the GitHub Actions workflow.

Reads DIGEST, DATE, DRY_RUN from env vars (set by Makefile) and
creates a simple artifact under ./digests/<digest>/<YYYY-MM-DD>.md

Safe defaults:
- DIGEST: daily
- DATE: today (UTC)
- DRY_RUN: true  -> no files written
"""
from __future__ import annotations
import os, sys, pathlib, datetime as dt

def log(msg: str) -> None:
    print(f"[digest] {msg}", flush=True)

def main() -> int:
    digest = (os.environ.get("DIGEST") or "daily").strip().lower()
    date_str = (os.environ.get("DATE") or "").strip()
    dry_run = (os.environ.get("DRY_RUN") or "true").strip().lower() in ("1","true","yes","y")

    if digest not in {"daily","weekly","monthly"}:
        log(f"Unsupported digest '{digest}'. Use daily|weekly|monthly.")
        return 2

    # parse date or use today (UTC)
    if date_str:
        try:
            day = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            log(f"Invalid DATE '{date_str}'. Expected YYYY-MM-DD.")
            return 2
    else:
        day = dt.datetime.utcnow().date()

    log(f"Running for digest='{digest}', date={day.isoformat()}, dry_run={dry_run}")

    # Generate a minimal file that is safe for Pages
    out_dir = pathlib.Path("digests") / digest
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{day.isoformat()}.md"

    content = f"""---
title: {digest.capitalize()} Digest — {day.isoformat()}
date: {day.isoformat()}
---

This is a placeholder {digest} digest for **{day.isoformat()}**.
(Replace this with your real generation logic.)
"""

    if dry_run:
        log(f"[DRY RUN] Would write: {out_file}")
        log(f"[DRY RUN] Content preview (first 200 chars): {content[:200]!r}")
    else:
        out_file.write_text(content, encoding="utf-8")
        log(f"Wrote {out_file.relative_to(pathlib.Path.cwd())}")

    log("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
