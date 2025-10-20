#!/usr/bin/env python
# scripts/diagnose_weekly.py
import os, re, glob, datetime as dt, sys, pathlib

SECTIONS = ["Summary", "Decisions", "Actions", "Risks", "Dependencies", "Notes"]
HDR = re.compile(r"^[ \t]*#{2,6}\s*([A-Za-z][^\n#]*)$", re.M)

BULLET_RE = re.compile(
    r'^[\s\u00A0]*('
    r'(?:[-*+])|'
    r'(?:\d+[.)])|'
    r'(?:\[[ xX\-]\])|'
    r'[\u2022\u2023\u2043\u2219\u25AA\u25AB\u25CF\u25E6\u2013\u2014]'
    r')\s+',
    re.M
)
PRI = {
    "high": re.compile(r"\[high\]", re.I),
    "medium": re.compile(r"\[medium\]", re.I),
    "low": re.compile(r"\[low\]", re.I),
}

def main():
    inp = os.environ.get("LOGS_DIR", "logs")
    start = os.environ.get("START")
    end   = os.environ.get("END")
    if not start or not end:
        print("START and END env vars are required", file=sys.stderr)
        sys.exit(1)

    start_d = dt.date.fromisoformat(start)
    end_d   = dt.date.fromisoformat(end)

    print(f"GITHUB_WORKSPACE={os.getcwd()}")
    print(f"Window: {start_d}..{end_d}")
    print(f"LOGS_DIR: {inp}")

    rx_filedate = re.compile(r"notes-(\d{4}-\d{2}-\d{2})\.md$", re.I)
    candidates = sorted(glob.glob(os.path.join(inp, "notes-*.md")))
    matches = []
    for c in candidates:
        m = rx_filedate.search(os.path.basename(c))
        if not m:
            continue
        d = dt.date.fromisoformat(m.group(1))
        if start_d <= d <= end_d:
            matches.append((d.isoformat(), c))

    print("\nMATCHES in window:")
    if not matches:
        print("  (none)")
        return

    for d, path in sorted(matches):
        print(f"  ✓ {d} -> {path}")
    print(f"TOTAL MATCHES: {len(matches)}")

    print("\n=== Section/Action scan per matched file ===")
    for d, path in sorted(matches):
        print(f"\n[{d}] {path}")
        try:
            txt = pathlib.Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")
        except Exception as e:
            print("  ! could not read:", e)
            continue

        # Which headings are present
        found_map = {s: False for s in SECTIONS}
        for m in HDR.finditer(txt):
            raw = m.group(1).strip()
            base = raw.split()[0].rstrip(":-—–")
            for s in SECTIONS:
                if base.lower() == s.lower():
                    found_map[s] = True

        # Actions block + bullet/priority counts
        acts_info = "n/a"
        if found_map["Actions"]:
            hdr_pat = re.compile(r"^[ \t]*#{2,6}\s*Actions\b.*$", re.M | re.I)
            m = hdr_pat.search(txt)
            if m:
                nxt = re.search(r"^[ \t]*#{2,6}\s+\S", txt[m.end():], re.M)
                body = txt[m.end(): m.end()+nxt.start()] if nxt else txt[m.end():]
                bullets = [ln for ln in body.splitlines() if BULLET_RE.match(ln)]
                n = len(bullets)
                hi = sum(1 for line in body.splitlines() if PRI["high"].search(line))
                me = sum(1 for line in body.splitlines() if PRI["medium"].search(line))
                lo = sum(1 for line in body.splitlines() if PRI["low"].search(line))
                # Fallback visibility (like aggregator)
                if n == 0 and (hi or me or lo):
                    n = sum(1 for L in body.splitlines() if L.strip())
                    acts_info = f"{n} lines (fallback; high:{hi}, medium:{me}, low:{lo})"
                else:
                    acts_info = f"{n} bullets (high:{hi}, medium:{me}, low:{lo})"

        print("  Sections found:", ", ".join([s for s,v in found_map.items() if v]) or "(none)")
        print("  Actions:", acts_info)

if __name__ == "__main__":
    main()
