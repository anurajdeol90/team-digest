# scripts/ci_copy_examples.py
import os
from importlib.resources import files, as_file
from contextlib import ExitStack

RUNNER_TEMP = os.environ["RUNNER_TEMP"]
OUTDIR = os.path.join(RUNNER_TEMP, "td-verify")
EXLOGS = os.path.join(RUNNER_TEMP, "exlogs")
os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(EXLOGS, exist_ok=True)

def copy_tree(traversable, dst):
    os.makedirs(dst, exist_ok=True)
    for ch in traversable.iterdir():
        target = os.path.join(dst, ch.name)
        if ch.is_dir():
            copy_tree(ch, target)
        else:
            with ch.open("rb") as rf, open(target, "wb") as wf:
                wf.write(rf.read())

# Keep resource context alive while copying
root = files("team_digest") / "examples" / "logs"
with ExitStack() as es:
    es.enter_context(as_file(root))
    copy_tree(root, EXLOGS)

print("OUTDIR:", OUTDIR)
print("EXLOGS:", EXLOGS)
print("Copied files:")
for dp, _, fns in os.walk(EXLOGS):
    for f in fns:
        print(os.path.join(dp, f))

# Export step outputs
gout = os.environ.get("GITHUB_OUTPUT")
if gout:
    with open(gout, "a", encoding="utf-8") as fh:
        fh.write(f"outdir={OUTDIR}\n")
        fh.write(f"exlogs={EXLOGS}\n")
