#!/usr/bin/env python3
import argparse
import datetime
from pathlib import Path
import textwrap

def infer_default_date(digest_type: str) -> str:
    today = datetime.date.today()
    if digest_type == "daily":
        return today.isoformat()
    elif digest_type == "weekly":
        return f"{today.year}-W{today.isocalendar().week:02d}"
    elif digest_type == "monthly":
        return f"{today.year}-{today.month:02d}"
    else:
        raise ValueError(f"Unknown digest type: {digest_type}")

def sample_content(digest_type: str, date_str: str) -> str:
    today = datetime.date.today().isoformat()
    return textwrap.dedent(f"""\
    # {digest_type.title()} Digest — {date_str}

    Generated automatically on {today}.

    ## Summary
    - Key project updates summarized here.
    - Example: Alpha budget approved with extra funding.

    ## Decisions
    - Decision 1
    - Decision 2

    ## Actions
    - [ ] Task 1 — Owner (due date)
    - [ ] Task 2 — Owner (due date)

    ---
    """)
    
def main():
    parser = argparse.ArgumentParser(description="Publish team digests")
    parser.add_argument("--digest", required=True, choices=["daily", "weekly", "monthly"], help="Digest type")
    parser.add_argument("--date", default="", help="Date (defaults based on digest type)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files, just print")
    args = parser.parse_args()

    digest_type = args.digest
    date_str = args.date or infer_default_date(digest_type)

    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    filename = f"{digest_type}_{date_str}.md"
    filepath = out_dir / filename
    content = sample_content(digest_type, date_str)

    if args.dry_run:
        print(f"[DRY RUN] Would write {filepath}:\n{content}")
    else:
        filepath.write_text(content, encoding="utf-8")
        print(f"✅ Wrote {filepath}")

if __name__ == "__main__":
    main()
