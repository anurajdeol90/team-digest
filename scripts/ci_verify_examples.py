# scripts/ci_verify_examples.py
import os
import sys
import shutil
import tempfile
import subprocess as sp
from contextlib import ExitStack
from importlib.resources import files, as_file

def run(cmd: str) -> None:
    print("\n$ " + cmd + "\n", flush=True)
    r = sp.run(cmd, shell=True, text=True)
    r.check_returncode()

def main() -> None:
    # Print dist vs module version (no heredocs needed in YAML)
    try:
        import importlib.metadata as m
        import team_digest
        print("dist version:", m.version("team-digest"))
        print("module __version__:", getattr(team_digest, "__version__", "unknown"))
    except Exception as e:
        print("WARNING: could not read versions:", e, file=sys.stderr)

    # Resolve packaged examples/logs to a real filesystem path
    with ExitStack() as es:
        p = files("team_digest").joinpath("examples", "logs")
        logs_path = os.fspath(es.enter_context(as_file(p)))
        print("EXLOGS:", logs_path)

        outdir = tempfile.mkdtemp(prefix="td-verify-")
        print("OUTDIR:", outdir)

        # Weekly
        run(
            f'team-digest weekly '
            f'--logs-dir "{logs_path}" '
            f'--start 2025-10-13 --end 2025-10-19 '
            f'--output "{os.path.join(outdir, "weekly.md")}" '
            f'--group-actions --emit-kpis --owner-breakdown'
        )

        # Daily
        run(
            f'team-digest daily '
            f'--logs-dir "{logs_path}" '
            f'--date 2025-10-17 '
            f'--output "{os.path.join(outdir, "daily.md")}" '
            f'--group-actions'
        )

        # Monthly
        run(
            f'team-digest monthly '
            f'--logs-dir "{logs_path}" '
            f'--output "{os.path.join(outdir, "monthly.md")}" '
            f'--group-actions --emit-kpis --owner-breakdown'
        )

        # Sanity checks (non-empty)
        failed = []
        for name in ("daily.md", "weekly.md", "monthly.md"):
            fp = os.path.join(outdir, name)
            if not os.path.exists(fp) or os.path.getsize(fp) == 0:
                failed.append(fp)
            else:
                print(f"OK non-empty: {fp}")
        if failed:
            print("ERROR: empty/missing outputs:", failed, file=sys.stderr)
            sys.exit(2)

        # Write the OUTDIR path to a file so workflow can upload it
        with open(os.path.join(outdir, "_OK"), "w", encoding="utf-8") as f:
            f.write("ok\n")

if __name__ == "__main__":
    main()
