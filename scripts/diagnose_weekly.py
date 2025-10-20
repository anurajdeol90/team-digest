#!/usr/bin/env python
# scripts/diagnose_weekly.py
import os, re, glob, datetime as dt, sys, pathlib

def main():
    inp = os.environ.get("LOGS_DIR", "logs")
    start = os.environ.get("START")
    end   = os.environ.get("END")
    if not start or not end:
        print("START and END env vars are required", file=sys.stderr)
        sys.exit(1)

    start_d = dt.date.fromisoformat(start)
    end_d   = dt.date.fromisoformat(end)
    rx = re.compile(r"notes-(\d{4}-\d{2}-\d{2})\.md$", re.I)

    print(f"GITHUB_WORKSPACE={os.getcwd()}")
    print(f"Window: {start_d}..{end_d}")
    print(f"LOGS_DIR: {inp}")
    p = pathlib.Path(inp)
    if not p.exists():
        print("logs dir does not exist on runner")
        return

    candidates = sorted(glob.glob(os.path.join(inp, "notes-*.md")))
    print("All candidates (by filename):")
    for c in candidates:
        print("  -", c)

    matches = []
    for c in candidates:
        m = rx.search(os.path.basename(c))
        if not m:
            continue
        d = dt.date.fromisoformat(m.group(1))
        if start_d <= d <= end_d:
            matches.append((d.isoformat(), c))

    print("\nMATCHES in window:")
    if matches:
        for d, c in sorted(matches):
            print(f"  ✓ {d}  -> {c}")
        print(f"TOTAL MATCHES: {len(matches)}")

        # Preview first 25 lines of the first match to inspect headings
        first = sorted(matches)[0][1]
        print("\nPreview of first matched file (first 25 lines):", first)
        try:
            with open(first, "r", encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if i >= 25: break
                    print(f"{i+1:02d}: {line.rstrip()}")
        except Exception as e:
            print("Could not preview:", e)
    else:
        print("  (none)")

if __name__ == "__main__":
    main()
