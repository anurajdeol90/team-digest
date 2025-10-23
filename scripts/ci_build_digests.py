# scripts/ci_build_digests.py
import os
import subprocess as sp
from pathlib import Path

EXLOGS = os.environ["EXLOGS"]
OUTDIR = os.environ["OUTDIR"]
Path(OUTDIR).mkdir(parents=True, exist_ok=True)

def run(cmd: str):
    print("\n$ " + cmd + "\n", flush=True)
    r = sp.run(cmd, shell=True, text=True, capture_output=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
    r.check_returncode()

def must_exist_nonempty(p: str):
    fp = Path(p)
    if not fp.exists() or fp.stat().st_size == 0:
        raise SystemExit(f"ERROR: expected non-empty file missing: {fp}")
    print(f"OK: {fp} {fp.stat().st_size} bytes")

# weekly
run(
    f'team-digest weekly --logs-dir "{EXLOGS}" '
    f'--start 2025-10-13 --end 2025-10-19 '
    f'--output "{OUTDIR}/weekly.md" '
    f'--group-actions --emit-kpis --owner-breakdown'
)
must_exist_nonempty(os.path.join(OUTDIR, "weekly.md"))

# daily
run(
    f'team-digest daily --logs-dir "{EXLOGS}" '
    f'--date 2025-10-17 '
    f'--output "{OUTDIR}/daily.md" '
    f'--group-actions'
)
must_exist_nonempty(os.path.join(OUTDIR, "daily.md"))

# monthly
run(
    f'team-digest monthly --logs-dir "{EXLOGS}" '
    f'--output "{OUTDIR}/monthly.md" '
    f'--group-actions --emit-kpis --owner-breakdown'
)
must_exist_nonempty(os.path.join(OUTDIR, "monthly.md"))

print("\nBuilt files:")
for p in Path(OUTDIR).glob("*.md"):
    print(f"- {p} ({p.stat().st_size} bytes)")
