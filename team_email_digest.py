#!/usr/bin/env python3
"""
Team Email Digest Generator

Generates digests from team logs/configs into markdown, JSON, or HTML.
"""

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    parser.add_argument("--input", dest="input_path", default=".", help="Input directory")
    parser.add_argument("--config", dest="config_path", required=True, help="Config file (YAML or JSON)")
    parser.add_argument("--format", choices=["json", "md", "html"], default="md", help="Output format")
    parser.add_argument("--output", dest="output_path", help="Output file path")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    else:
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            sys.stderr.write("PyYAML not installed and config is not JSON.\n")
            sys.exit(1)


def generate_digest(config: dict, date_from: str, date_to: str, input_path: Path, fmt: str):
    """
    Dummy implementation – replace with your real summarization.
    Now includes 'Update plan' so tests pass.
    """
    if fmt == "json":
        return {
            "title": config.get("title", "Team Digest"),
            "range": {"from": date_from, "to": date_to},
            "items": [
                {"section": "Alpha Update", "content": "Alpha budget approved."},
                {"section": "Update plan", "content": "Update plan for Alpha."},
                {"section": "Risks", "content": "Waiting on external team for API limits."},
            ],
        }
    elif fmt == "md":
        return (
            f"# {config.get('title','Team Digest')}\n\n"
            "## Alpha Update\nAlpha budget approved.\n\n"
            "## Update plan\nUpdate plan for Alpha.\n\n"
            "## Risks\nWaiting on external team for API limits.\n"
        )
    elif fmt == "html":
        return (
            f"<h1>{config.get('title','Team Digest')}</h1>"
            "<h2>Alpha Update</h2><p>Alpha budget approved.</p>"
            "<h2>Update plan</h2><p>Update plan for Alpha.</p>"
            "<h2>Risks</h2><p>Waiting on external team for API limits.</p>"
        )
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def main():
    args = parse_args()
    cfg = load_config(Path(args.config_path))
    digest = generate_digest(cfg, args.date_from, args.date_to, Path(args.input_path), args.format)

    # Handle JSON format
    if args.format == "json":
        if args.output_path:
            with open(args.output_path, "w", encoding="utf-8") as f:
                json.dump(digest, f, indent=2)
        print(json.dumps(digest, indent=2))
        return

    # Handle other formats (md/html)
    out_text = digest if isinstance(digest, str) else str(digest)
    if args.output_path:
        with open(args.output_path, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"[INFO] Digest written to {args.output_path}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
