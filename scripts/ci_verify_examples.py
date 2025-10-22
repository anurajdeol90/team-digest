# scripts/ci_verify_examples.py
import os
import sys
import tempfile
import subprocess as sp
from contextlib import ExitStack
from importlib.resources import files, as_file

def run(cmd: str) -> sp.CompletedProcess:
    print("\n$ " + cmd + "\n", flush=True)
    return sp.run(cmd, shell=True, text=True)

def must_run(cmd: str) -> None:
    r = run(cmd)
    r.check_returncode()

def cmd_supports_flag(cmd: str, flag: str) -> bool:
    # cmd like: "team-digest monthly"
    try:
        r = sp.run(f"{cmd} --help", shell=True, text=True, capture_output=True)
        if r.returncode != 0:
            return False
        text = (r.stdout or "") + (r.stderr or "")
        return flag in text
    except Exception:
        return False

def main() -> None:
    # version info (non-fatal)
    try:
        import importlib.metadata as m
        import team_digest
        print("dist version:", m.version("team-digest"))
        print("module __version__:", getattr(team_digest, "__version__", "unknown"))
    except Exception as e:
        print("WARNING: could not read versions:", e, file=sys.stderr)

    # resolve packaged examples/logs to a real filesystem path
    with ExitStack() as es:
        p = files("team_digest").joinpath("examples", "logs")
        logs_path = os.fspath(es.enter_context(as_file(p)))
        print("EXLOGS:", logs_path)

        outdir = tempfile.mkdtemp(prefix="td-verify-")
        print("OUTDIR:", outdir)

        # WEEKLY — always pass KPIs + owner breakdown (supported in 1.1.13)
        must_run(
            f'team-digest weekly '
            f'--logs-dir "{logs_path}" '
            f'--start 2025-10-13 --end 2025-10-19 '
            f'--output "{os.path.join(outdir, "weekly.md")}" '
            f'--group-actions --emit-kpis --owner-breakdown'
        )

        # DAILY
        must_run(
            f'team-digest daily '
            f'--logs-dir "{logs_path}" '
            f'--date 2025-10-17 '
            f'--output "{os.path.join(outdir, "daily.md")}" '
            f'--group-actions'
        )

        # MONTHLY — add flags only if supported by this installed version
        monthly_cmd = (
            f'team-digest monthly '
            f'--logs-dir "{logs_path}" '
            f'--output "{os.path.join(outdir, "monthly.md")}" '
            f'--group-actions'
        )

        base_cmd = "team-digest monthly"
        if cmd_supports_flag(base_cmd, "--emit-kpis"):
            monthly_cmd += " --emit-kpis"
        if cmd_supports_flag(base_cmd, "--owner-breakdown"):
            monthly_cmd += " --owner-breakdown"

        must_run(monthly_cmd)

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

        # leave a sentinel file so artifact glob definitely matches the folder
        with open(os.path.join(outdir, "_OK"), "w", encoding="utf-8") as f:
            f.write("ok\n")

if __name__ == "__main__":
    main()
