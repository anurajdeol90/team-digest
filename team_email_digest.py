#!/usr/bin/env python3
"""
Team Digest Generator

Parses team updates (logs, emails, meeting notes) into structured digests,
then outputs them in JSON or posts them to Slack/email.
"""

import os
import re
import sys
import json
import argparse
import datetime
from pathlib import Path

try:
    from team_digest_version import __version__
except Exception:
__version__ = "0.1.1"


# ---------------------------
# Parsing Utilities
# ---------------------------

def parse_sections(text: str) -> dict:
    """
    Parse plain text updates into sections.
    Expected sections: Summary, Decisions, Actions, Risks, Dependencies, Open Questions
    """
    sections = {
        "summary": [],
        "decisions": [],
        "actions": [],
        "risks": [],
        "dependencies": [],
        "open_questions": []
    }

    current = None
    for line in text.splitlines():
        line = line.strip()

        # Section headers
        if re.match(r"(?i)^summary", line):
            current = "summary"
            continue
        elif re.match(r"(?i)^decisions?", line):
            current = "decisions"
            continue
        elif re.match(r"(?i)^actions?", line):
            current = "actions"
            continue
        elif re.match(r"(?i)^risks?", line):
            current = "risks"
            continue
        elif re.match(r"(?i)^dependencies?", line):
            current = "dependencies"
            continue
        elif re.match(r"(?i)^(open\s*questions?|questions)", line):
            current = "open_questions"
            continue

        # Collect details
        if current and line:
            sections[current].append(line.lstrip("-•* "))

    return sections


def build_digest(sections: dict) -> dict:
    """Builds a structured digest dictionary."""
    return {
        "summary": sections["summary"] or ["No summary provided."],
        "decisions": sections["decisions"],
        "actions": sections["actions"],
        "risks": sections["risks"],
        "dependencies": sections["dependencies"],
        "open_questions": sections["open_questions"],
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z"
    }


# ---------------------------
# CLI Entry
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a team digest from text updates.")
    parser.add_argument("input", help="Path to input text file containing updates.")
    parser.add_argument("-o", "--output", help="Output JSON file for digest.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"❌ Input file not found: {path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    sections = parse_sections(text)
    digest = build_digest(sections)

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(digest, indent=2), encoding="utf-8")
        print(f"✅ Digest written to {out}")
    else:
        print(json.dumps(digest, indent=2))


if __name__ == "__main__":
    main()
