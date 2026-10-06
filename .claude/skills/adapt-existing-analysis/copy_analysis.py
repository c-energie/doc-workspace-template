#!/usr/bin/env python3
"""Copy an existing analysis project into the workspace's analysis repo. The source is read, never written.

Driven by the `adapt-existing-analysis` skill. Three steps; `copy` and `verify` are safe
to re-run, and `plan` refuses to overwrite a plan that may hold agreed placements:

    plan     inventory the source (every file, with its SHA-256) and write a placement plan
             to .setup/analysis-import/plan.json -- one `dest` per file, edited before copying
    copy     copy every planned file to its `dest` inside the analysis repo
    verify   re-hash the source against the inventory, and re-list every file in it
             (ignored ones included): exit 1 if anything changed, appeared or vanished

Nothing here opens a source file for writing, deletes, moves or renames one, or runs a
git command that changes the source checkout. `copy` refuses to start if the source no
longer matches the inventory, and refuses any `dest` that resolves outside the analysis
repo -- so the source cannot be a destination either.

Run with uv so no system Python is needed:

    uv run --no-project --python 3.12 .claude/skills/adapt-existing-analysis/copy_analysis.py plan --source ../old-analysis

Stdlib only.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath

# .claude/skills/adapt-existing-analysis/copy_analysis.py -> the workspace root
ROOT = Path(__file__).resolve().parents[3]
STATE_FILE = ROOT / "workspace.toml"
WORK_DIR = ROOT / ".setup" / "analysis-import"
PLAN = WORK_DIR / "plan.json"
CLONE_DIR = ROOT / ".setup" / "analysis-source"

SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".ipynb_checkpoints",
             ".pytest_cache", ".mypy_cache", ".idea", ".vscode", "node_modules", "build", "dist"}
# Bigger than this is probably data or output, which belongs wherever the data lives rather
# than in a git repo. Planned as skipped; the user can still give it a dest.
LARGE = 1_000_000


def say(msg=""):
    print(msg, flush=True)


def git(source, *args):
    """Read-only git queries against the source. Only ever called with ls-files,
    rev-parse and status; --no-optional-locks stops `status` refreshing .git/index."""
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(source), *args],
                            capture_output=True)
    return result.stdout if result.returncode == 0 else None


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analysis_root(override=None):
    if override:
        return (ROOT / override).resolve()
    if not STATE_FILE.exists():
        sys.exit("workspace.toml missing: run /setup-doc-workspace first, or pass --analysis-dir.")
    state = tomllib.loads(STATE_FILE.read_text(encoding="utf-8"))["workspace"]
    return (ROOT / state["analysis_dir"]).resolve()


def writing_sections():
    """Leaf directories under the document's Sections/, to suggest notebook folders from."""
    if not STATE_FILE.exists():
        return []
    sections = ROOT / tomllib.loads(STATE_FILE.read_text(encoding="utf-8"))["workspace"]["writing_dir"] / "Sections"
    if not sections.is_dir():
        return []
    return sorted(p.relative_to(sections).as_posix() for p in sections.rglob("*")
                  if p.is_dir() and p.name not in ("Figures", "Tables")
                  and not any(c.is_dir() and c.name not in ("Figures", "Tables") for c in p.iterdir()))


def list_files(source):
    """Relative POSIX paths of the source's files: git-tracked plus untracked-not-ignored
    in a checkout (ignored files are outputs and environments), everything else otherwise."""
    tracked = git(source, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if tracked is not None:
        names = [n for n in tracked.decode("utf-8").split("\0") if n]
    else:
        names = [p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()]
    return sorted(n for n in names
                  if not set(PurePosixPath(n).parts[:-1]) & SKIP_DIRS and (source / n).is_file())


def every_file(source):
    """Every file under the source but .git, ignored ones included: a run of a copied
    notebook that writes a cache or an output back into the source shows up here, where
    the hashed inventory (tracked files only) cannot see it."""
    return sorted(p.relative_to(source).as_posix() for p in source.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(source).parts)


def default_dest(rel, size):
    """Notebooks to notebooks/unsorted/, everything else to imported/, large files and
    .env files skipped. The skill replaces these with the agreed placement before `copy`."""
    path = PurePosixPath(rel)
    if path.name.startswith(".env"):
        return None, "secret"
    if path.suffix == ".ipynb":
        inner = PurePosixPath(*path.parts[1:]) if path.parts[0] == "notebooks" and len(path.parts) > 1 else path
        return f"notebooks/unsorted/{inner}", "notebook"
    kind = "code" if path.suffix == ".py" else "other"
    return (None if size > LARGE else f"imported/{rel}"), kind


def load_plan():
    if not PLAN.exists():
        sys.exit(f"No plan at {PLAN.relative_to(ROOT)}: run `plan --source ...` first.")
    return json.loads(PLAN.read_text(encoding="utf-8"))


def changed_sources(plan):
    """Every inventoried source file that is missing or no longer matches its hash."""
    source = Path(plan["source"])
    problems = []
    now = set(every_file(source))
    before = set(plan["all_files"])
    problems += [f"new      {rel}" for rel in sorted(now - before)]
    problems += [f"gone     {rel}" for rel in sorted(before - now)]
    for entry in plan["files"]:
        path = source / entry["src"]
        if not path.is_file():
            problems.append(f"missing  {entry['src']}")
        elif sha256(path) != entry["sha256"]:
            problems.append(f"changed  {entry['src']}")
    return problems


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------

def cmd_plan(args):
    if PLAN.exists():
        sys.exit(f"{PLAN.relative_to(ROOT)} exists and may hold agreed placements. Edit it, "
                 f"or delete it to plan from scratch.")
    local = Path(args.source).expanduser()
    if local.is_dir():
        source = local.resolve()
    else:
        if CLONE_DIR.exists():
            sys.exit(".setup/analysis-source/ already holds a clone, maybe of another repo. "
                     "Delete it (it is only a clone) or pass its path as --source.")
        else:
            say(f"$ gh repo clone {args.source} .setup/analysis-source")
            if subprocess.run(["gh", "repo", "clone", args.source, str(CLONE_DIR)]).returncode:
                sys.exit(f"Could not clone {args.source}; give a local path instead.")
        source = CLONE_DIR.resolve()
    target = analysis_root(args.analysis_dir)
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        sys.exit(f"Source {source} and the analysis repo {target} overlap; they must be separate.")

    files = []
    for rel in list_files(source):
        size = (source / rel).stat().st_size
        dest, kind = default_dest(rel, size)
        files.append({"src": rel, "dest": dest, "kind": kind, "bytes": size,
                      "sha256": sha256(source / rel)})
    head = git(source, "rev-parse", "HEAD")
    status = git(source, "status", "--porcelain")
    plan = {
        "source": str(source),
        "analysis_dir": str(target),
        "source_git_head": head.decode().strip() if head else None,
        "source_git_status": status.decode() if status is not None else None,
        "sections": writing_sections(),
        "all_files": every_file(source),
        "files": files,
    }
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")

    say(f"Inventoried {len(files)} file(s) in {source}")
    for kind in ("notebook", "code", "other", "secret"):
        say(f"  {sum(f['kind'] == kind for f in files):4d} {kind}")
    skipped = [f for f in files if f["dest"] is None]
    for entry in skipped:
        why = ("a secret; copy it by hand if the copy needs it" if entry["kind"] == "secret"
               else f"{entry['bytes']:,} bytes: data or output? give it a dest to copy it")
        say(f"  skip {entry['src']}  ({why})")
    if plan["sections"]:
        say("Document sections (suggested notebook folders):")
        for section in plan["sections"]:
            say(f"  notebooks/{section}/")
    say(f"Wrote {PLAN.relative_to(ROOT)}. Set each file's `dest` (relative to the analysis "
        f"repo, or null to skip), then run `copy`.")
    return 0


def cmd_copy(args):
    plan = load_plan()
    source, target = Path(plan["source"]), Path(plan["analysis_dir"])
    problems = changed_sources(plan)
    if problems:
        say("The source no longer matches the inventory; nothing copied:")
        for line in problems:
            say(f"  {line}")
        return 1

    conflicts, copied, present = [], 0, 0
    for entry in plan["files"]:
        if not entry["dest"]:
            continue
        dest = (target / entry["dest"]).resolve()
        if not dest.is_relative_to(target) or dest.is_relative_to(source):
            sys.exit(f"dest {entry['dest']!r} resolves outside the analysis repo; fix the plan.")
        if dest.exists():
            if sha256(dest) == entry["sha256"]:
                present += 1
            else:
                conflicts.append(entry)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / entry["src"], dest)
        copied += 1
        say(f"  copy  {entry['src']}  ->  {entry['dest']}")

    say(f"Copied {copied}, already present {present}, conflicts {len(conflicts)}.")
    for entry in conflicts:
        say(f"  conflict  {entry['dest']} exists with different content (left as is; "
            f"from {entry['src']})")
    return 1 if conflicts else 0


def cmd_verify(args):
    plan = load_plan()
    problems = changed_sources(plan)
    status = git(Path(plan["source"]), "status", "--porcelain")
    if plan["source_git_status"] is not None and status is not None \
            and status.decode() != plan["source_git_status"]:
        problems.append("git status of the source differs from when it was inventoried")
    target = Path(plan["analysis_dir"])
    missing = [e["dest"] for e in plan["files"] if e["dest"] and not (target / e["dest"]).exists()]
    for line in problems:
        say(f"  SOURCE {line}")
    for dest in missing:
        say(f"  not copied yet  {dest}")
    if problems:
        say(f"FAIL: the source at {plan['source']} changed. Restore it from git or a backup "
            f"before going on.")
        return 1
    say(f"OK: all {len(plan['files'])} source file(s) unchanged"
        + (f"; {len(missing)} planned file(s) not copied yet." if missing else "."))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="step", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--source", required=True, help="local path, or OWNER/NAME to clone")
    p.add_argument("--analysis-dir", help="override workspace.toml's analysis_dir")
    sub.add_parser("copy")
    sub.add_parser("verify")
    args = ap.parse_args(argv)
    return {"plan": cmd_plan, "copy": cmd_copy, "verify": cmd_verify}[args.step](args)


if __name__ == "__main__":
    sys.exit(main())
