# scripts/ci_build_digests.py
import os
import subprocess as sp
from pathlib import Path

EXLOGS = os.environ["EXLOGS"]
OUTDIR = os.environ["OUTDIR"]
Path(OUTDIR).mkdir(parents=True, exist_ok=True)


def run(cmd: str, outfile: Path | None = None):
    print("\n$ " + cmd + "\n", flush=True)
    r = sp.run(cmd, shell=True, text=True, capture_output=True)
    # Always show what the tool printed
    if r.stdout:
        print(r.stdout)
    if r.returncode != 0:
        if r.stderr:
            print(r.stderr)
        # If it errored, bubble up immediately
        r.check_returncode()

    # Fallback: if caller expected a file but it's missing/empty, write stdout to it
    if outfile is not None:
        if not outfile.exists() or outfile.stat().st_size == 0:
            if r.stdout and r.stdout.strip():
                outfile.write_text(r.stdout, encoding="utf-8")
                print(
                    f"[fallback] wrote stdout to {outfile} ({outfile.stat().st_size} bytes)"
                )
            else:
                print(f"[warning] no stdout to write for {outfile}")


def must_exist_nonempty(p: Path):
    if not p.exists() or p.stat().st_size == 0:
        raise SystemExit(f"ERROR: expected non-empty file missing: {p}")
    print(f"OK: {p} {p.stat().st_size} bytes")


weekly_path = Path(OUTDIR) / "weekly.md"
daily_path = Path(OUTDIR) / "daily.md"
monthly_path = Path(OUTDIR) / "monthly.md"

# weekly
run(
    cmd=(
        f'team-digest weekly --logs-dir "{EXLOGS}" '
        f"--start 2025-10-13 --end 2025-10-19 "
        f'--output "{weekly_path}" '
        f"--group-actions --emit-kpis --owner-breakdown"
    ),
    outfile=weekly_path,
)
must_exist_nonempty(weekly_path)

# daily
run(
    cmd=(
        f'team-digest daily --logs-dir "{EXLOGS}" '
        f"--date 2025-10-17 "
        f'--output "{daily_path}" '
        f"--group-actions"
    ),
    outfile=daily_path,
)
must_exist_nonempty(daily_path)

# monthly
run(
    cmd=(
        f'team-digest monthly --logs-dir "{EXLOGS}" '
        f'--output "{monthly_path}" '
        f"--group-actions --emit-kpis --owner-breakdown"
    ),
    outfile=monthly_path,
)
must_exist_nonempty(monthly_path)

print("\nBuilt files:")
for p in Path(OUTDIR).glob("*.md"):
    print(f"- {p} ({p.stat().st_size} bytes)")
