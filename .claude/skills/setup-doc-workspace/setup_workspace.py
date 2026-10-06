#!/usr/bin/env python3
"""Create a document workspace's two member repos and wire them together.

The workspace (this repo) holds two independent checkouts:

    <workspace>/
    |-- <doc>-writing/    the LaTeX document  (from c-energie/writing-template, or your Overleaf project)
    |-- <doc>-analysis/   figures and tables  (from c-energie/analysis-template)
    |-- pyproject.toml    uv workspace root; the analysis repo is its one member
    `-- .venv/            the venv notebooks, tests and console scripts use

Driven by the `setup-doc-workspace` skill, which does the interview and then calls the
steps below in order. Each step is also runnable by hand, and each refuses rather than
overwrites when its target already exists:

    check       prerequisites, with the install command for anything missing
    workspace   make sure this repo's `origin` is yours, not the template
    writing     create or adopt the document repo
    analysis    create the analysis repo and run its init.py
    root        write pyproject.toml, workspace.toml, the .gitignore block, fill CLAUDE.md
    sync        uv sync at the root

Run with uv so no system Python is needed:

    uv run --no-project --python 3.12 .claude/skills/setup-doc-workspace/setup_workspace.py check

Stdlib only.
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

# .claude/skills/setup-doc-workspace/setup_workspace.py -> the workspace root
ROOT = Path(__file__).resolve().parents[3]

ORG = "c-energie"
WORKSPACE_TEMPLATE = f"{ORG}/doc-workspace-template"
WRITING_TEMPLATE = f"{ORG}/writing-template"
ANALYSIS_TEMPLATE = f"{ORG}/analysis-template"

STATE_FILE = ROOT / "workspace.toml"
IMPORT_DIR = ROOT / ".setup" / "import-source"

# The .gitignore lines naming the members live between these markers, so a re-run (or a
# renamed member) replaces the block instead of appending a second one.
BLOCK_START = "# >>> members (managed by setup-doc-workspace) >>>"
BLOCK_END = "# <<< members <<<"

# Files carried from writing-template into an adopted Overleaf repo. Only the
# agent-facing ones: the layout of an existing document is adapted by hand, never
# overwritten (see the adapt-existing-document skill).
OVERLAY_FILES = ("AGENTS.md", "CLAUDE.md")

MIN_PYTHON = (3, 11, 4)

DRY_RUN = False


# ---------------------------------------------------------------------------
# install commands, per platform
# ---------------------------------------------------------------------------

def _os():
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


INSTALL = {
    "git": {
        "windows": "winget install --id Git.Git -e",
        "macos": "xcode-select --install   (or: brew install git)",
        "linux": "sudo apt install git   (or your distro's package manager)",
    },
    "gh": {
        "windows": "winget install --id GitHub.cli -e",
        "macos": "brew install gh",
        "linux": "sudo apt install gh   (see https://github.com/cli/cli/blob/trunk/docs/install_linux.md)",
    },
    "uv": {
        "windows": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
                   "   (or: winget install --id astral-sh.uv -e, or: pip install uv)",
        "macos": "curl -LsSf https://astral.sh/uv/install.sh | sh   (or: brew install uv, or: pip install uv)",
        "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh   (or: pip install uv)",
    },
    "latexmk": {
        "windows": "winget install --id MiKTeX.MiKTeX -e   (optional: Overleaf compiles without it)",
        "macos": "brew install --cask mactex-no-gui   (optional: Overleaf compiles without it)",
        "linux": "sudo apt install texlive-full latexmk   (optional: Overleaf compiles without it)",
    },
    "make": {
        "windows": "winget install --id ezwinports.make -e   (optional: only for local LaTeX builds)",
        "macos": "xcode-select --install   (optional: only for local LaTeX builds)",
        "linux": "sudo apt install make   (optional: only for local LaTeX builds)",
    },
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def say(msg=""):
    print(msg, flush=True)


def run(cmd, cwd=None, stdin=None, check=True, capture=False):
    where = f"  (in {Path(cwd).relative_to(ROOT) if cwd and Path(cwd).is_relative_to(ROOT) else cwd or '.'})"
    say(f"$ {' '.join(str(c) for c in cmd)}{where}")
    if DRY_RUN:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    result = subprocess.run([str(c) for c in cmd], cwd=cwd, input=stdin, text=True,
                            capture_output=capture)
    if check and result.returncode != 0:
        if capture:
            say(result.stdout)
            say(result.stderr)
        sys.exit(f"\nFAILED ({result.returncode}): {' '.join(str(c) for c in cmd)}")
    return result


def quiet(cmd, cwd=None):
    """Run for the answer, not the side effect. Never honours DRY_RUN: reads only."""
    try:
        return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "not found")


def write(path, text):
    say(f"  write {path.relative_to(ROOT)}")
    if not DRY_RUN:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def repo_exists(repo):
    return quiet(["gh", "repo", "view", repo, "--json", "name"]).returncode == 0


def wait_for_content(repo, timeout=90):
    """A repo generated from a template is filled asynchronously; cloning too early
    yields an empty checkout with no error."""
    if DRY_RUN:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if quiet(["gh", "api", f"repos/{repo}/commits?per_page=1"]).returncode == 0:
            return
        time.sleep(3)
    sys.exit(f"{repo} still has no commits after {timeout}s. Check it on GitHub, then re-run.")


def create_from_template(template, repo, visibility):
    if repo_exists(repo):
        say(f"{repo} already exists; using it as-is.")
    else:
        run(["gh", "repo", "create", repo, "--template", template, f"--{visibility}"])
    wait_for_content(repo)


def clone(repo, directory):
    target = ROOT / directory
    if target.exists() and any(target.iterdir()):
        if (target / ".git").exists():
            say(f"{directory}/ is already a checkout; leaving it alone.")
            return target
        sys.exit(f"{directory}/ exists and is not empty. Move it aside, then re-run.")
    run(["gh", "repo", "clone", repo, directory], cwd=ROOT)
    return target


def run_init(checkout, answers):
    """Templates ship a self-deleting init.py that prompts on stdin. Feed it the answers
    the skill already collected, one per line, so it runs unattended."""
    init = checkout / "init.py"
    if not init.exists():
        say(f"No init.py in {checkout.name}/ (already initialised); skipping.")
        return
    run([sys.executable, "init.py"], cwd=checkout, stdin="\n".join(answers) + "\n")


def gh_raw(repo, path):
    result = quiet(["gh", "api", f"repos/{repo}/contents/{path}",
                    "-H", "Accept: application/vnd.github.raw"])
    if result.returncode != 0:
        sys.exit(f"Could not read {path} from {repo}: {result.stderr.strip()}")
    return result.stdout


def origin_url(path):
    result = quiet(["git", "remote", "get-url", "origin"], cwd=path)
    return result.stdout.strip() if result.returncode == 0 else ""


def load_state():
    if not STATE_FILE.exists():
        return {}
    return tomllib.loads(STATE_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------

def cmd_check(args):
    os_name = _os()
    missing_required = False
    say(f"platform: {platform.system()} ({os_name})")

    py = sys.version_info[:3]
    ok = py >= MIN_PYTHON
    say(f"[{'ok' if ok else 'FAIL'}] python {'.'.join(map(str, py))} (need >= 3.11.4)")
    if not ok:
        missing_required = True
        say("       uv python install 3.12   then re-run this script with `uv run --python 3.12`")

    for tool, required in (("git", True), ("gh", True), ("uv", True),
                           ("latexmk", False), ("make", False)):
        found = shutil.which(tool)
        tag = "ok" if found else ("FAIL" if required else "--")
        say(f"[{tag}] {tool}{'' if found else '  ->  ' + INSTALL[tool][os_name]}")
        missing_required |= required and not found

    if shutil.which("gh"):
        auth = quiet(["gh", "auth", "status"])
        if auth.returncode == 0:
            login = quiet(["gh", "api", "user", "--jq", ".login"]).stdout.strip()
            say(f"[ok] gh authenticated as {login}")
        else:
            missing_required = True
            say("[FAIL] gh not authenticated  ->  gh auth login   (choose HTTPS, and let it configure git)")

    for name, repo in (("writing", WRITING_TEMPLATE), ("analysis", ANALYSIS_TEMPLATE)):
        if shutil.which("gh") and not repo_exists(repo):
            missing_required = True
            say(f"[FAIL] cannot see template {repo} with your gh login")

    say("\nAll required prerequisites present." if not missing_required
        else "\nInstall the FAIL items above, open a NEW terminal so PATH updates, then re-run.")
    return 1 if missing_required else 0


def cmd_workspace(args):
    origin = origin_url(ROOT)
    if origin and WORKSPACE_TEMPLATE.lower() not in origin.lower():
        say(f"origin is {origin}: already your own repo. Nothing to do.")
        return 0
    if not args.repo:
        say(f"origin is {origin or '(none)'}: this workspace is not yet its own repo.")
        say("Re-run with --repo OWNER/NAME to create it and point origin at it.")
        return 2
    if repo_exists(args.repo):
        sys.exit(f"{args.repo} already exists. Point origin at it by hand: "
                 f"git remote set-url origin https://github.com/{args.repo}.git")
    if origin:
        # Kept, not deleted: pulling template improvements later is `git pull template main`.
        run(["git", "remote", "rename", "origin", "template"], cwd=ROOT)
    has_commits = quiet(["git", "rev-parse", "HEAD"], cwd=ROOT).returncode == 0
    cmd = ["gh", "repo", "create", args.repo, f"--{args.visibility}",
           "--source", ".", "--remote", "origin"]
    run(cmd + (["--push"] if has_commits else []), cwd=ROOT)
    return 0


def cmd_writing(args):
    if args.mode == "adapt":
        # The Overleaf project's own GitHub-sync repo becomes the document repo, history
        # and Overleaf link intact. Overleaf must create it; nothing here can.
        if not repo_exists(args.repo):
            sys.exit(f"{args.repo} does not exist yet. In Overleaf: Menu -> GitHub -> "
                     f"create a repository named {args.repo.split('/')[-1]}, then re-run.")
        wait_for_content(args.repo)
        checkout = clone(args.repo, args.dir)
        overlay(checkout)
    else:
        create_from_template(WRITING_TEMPLATE, args.repo, args.visibility)
        checkout = clone(args.repo, args.dir)
        run_init(checkout, [args.title, args.author])
        if args.mode == "import":
            stage_import_source(args.source)
    say(f"\nDocument repo ready at {args.dir}/. Nothing has been committed in it.")
    return 0


def overlay(checkout):
    """Bring the template's agent instructions and ignore rules into an adopted repo,
    without touching any of the document."""
    for name in OVERLAY_FILES:
        target = checkout / name
        if target.exists():
            say(f"  kept  {checkout.name}/{name}  (exists)")
            continue
        write(target, gh_raw(WRITING_TEMPLATE, name))

    template_lines = gh_raw(WRITING_TEMPLATE, ".gitignore").splitlines()
    gitignore = checkout / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    have = {line.strip() for line in existing}
    new = [line for line in template_lines
           if line.strip() and not line.startswith("#") and line.strip() not in have]
    if new:
        text = "\n".join(existing + ["", "# ---- from c-energie/writing-template ----"] + new) + "\n"
        write(gitignore, text.lstrip("\n"))
    else:
        say(f"  kept  {checkout.name}/.gitignore  (already covers the template's rules)")


def stage_import_source(source):
    """Put the existing document somewhere the adapt-existing-document skill can read it
    from. Never inside a member: it is scaffolding, deleted once the import is done."""
    if not source:
        say("No --source given; copy the existing document into .setup/import-source/ by hand.")
        return
    if IMPORT_DIR.exists():
        say(f".setup/import-source/ already exists; leaving it alone.")
        return
    if Path(source).expanduser().is_dir():
        say(f"  copy  {source} -> .setup/import-source/")
        if not DRY_RUN:
            shutil.copytree(Path(source).expanduser(), IMPORT_DIR,
                            ignore=shutil.ignore_patterns(".git"))
    else:
        IMPORT_DIR.parent.mkdir(parents=True, exist_ok=True)
        run(["gh", "repo", "clone", source, str(IMPORT_DIR)], cwd=ROOT)


def cmd_analysis(args):
    writing = ROOT / args.writing_dir
    if not writing.is_dir():
        sys.exit(f"{args.writing_dir}/ does not exist. Run the `writing` step first.")
    create_from_template(ANALYSIS_TEMPLATE, args.repo, args.visibility)
    checkout = clone(args.repo, args.dir)
    # init.py asks: distribution name, author, DOC_REPO path, backend. DOC_REPO is
    # absolute because .env is per-machine and read from wherever the cwd happens to be.
    run_init(checkout, [args.distribution, args.author, writing.as_posix(), args.backend])
    say(f"\nAnalysis repo ready at {args.dir}/, with .env pointing DOC_REPO at {args.writing_dir}/.")
    return 0


PYPROJECT = """\
# The workspace root: a uv workspace whose one member is the analysis repo. Run
# `uv sync` HERE, not inside the member, so the whole workspace shares one .venv.
#
# The document repo ({writing}/) is deliberately NOT a member. It is LaTeX, has no
# Python, and the analysis repo locates it through DOC_REPO in {analysis}/.env.
#
# Pass every extra you want on EVERY sync: `uv sync` removes the ones you leave out.
#
#   uv sync --extra dev --extra notebooks --extra {backend}

[project]
name = "{name}-workspace"
version = "0.0.0"
description = "Workspace root for {name}. Not a distributable package."
requires-python = ">=3.11.4"
dependencies = ["{dist}"]

[tool.uv]
package = false

[project.optional-dependencies]
# Pass-throughs to the member's own extras, so the familiar flags read the same here.
dev = ["{dist}[dev]"]
notebooks = ["{dist}[notebooks]"]
{backend} = ["{dist}[{backend}]"]

[tool.uv.workspace]
members = ["{analysis}"]

[tool.uv.sources]
{dist} = {{ workspace = true }}
"""


def cmd_root(args):
    state = {
        "name": args.name,
        "writing_dir": args.writing_dir, "writing_repo": args.writing_repo,
        "writing_mode": args.writing_mode,
        "analysis_dir": args.analysis_dir, "analysis_repo": args.analysis_repo,
        "backend": args.backend,
        # What `sync` installs. /setup-doc-publish appends "publish" here.
        "extras": ["dev", "notebooks", args.backend],
    }
    analysis_pyproject = ROOT / args.analysis_dir / "pyproject.toml"
    if not analysis_pyproject.exists() and not DRY_RUN:
        sys.exit(f"{args.analysis_dir}/pyproject.toml missing. Run the `analysis` step first.")
    dist = (tomllib.loads(analysis_pyproject.read_text(encoding="utf-8"))["project"]["name"]
            if analysis_pyproject.exists() else "DIST")
    if dist == "PACKAGE-NAME":
        sys.exit(f"{args.analysis_dir}/ is not initialised (its init.py has not run).")
    state["analysis_distribution"] = dist

    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        say("  kept  pyproject.toml  (exists; edit it by hand, or delete it and re-run)")
    else:
        write(pyproject, PYPROJECT.format(name=args.name, dist=dist, backend=args.backend,
                                          writing=args.writing_dir, analysis=args.analysis_dir))

    write(STATE_FILE, "# Written by setup-doc-workspace and read by the workspace skills.\n"
                      "# Edit it if you rename a member directory or repo.\n\n[workspace]\n"
                      + "".join(f"{k} = {json.dumps(v)}\n" for k, v in state.items()))

    gitignore = ROOT / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    block = "\n".join([BLOCK_START,
                       "# Each member is its own repo with its own remote. Tracking them here",
                       "# would nest one history inside another.",
                       f"/{args.writing_dir}/", f"/{args.analysis_dir}/", BLOCK_END])
    if BLOCK_START in text and BLOCK_END in text:
        head, _, rest = text.partition(BLOCK_START)
        _, _, tail = rest.partition(BLOCK_END)
        text = head + block + tail
    else:
        text = block + "\n\n" + text
    write(gitignore, text)

    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        for token, value in (("<<WORKSPACE>>", args.name),
                             ("<<WRITING_DIR>>", args.writing_dir),
                             ("<<WRITING_REPO>>", args.writing_repo),
                             ("<<ANALYSIS_DIR>>", args.analysis_dir),
                             ("<<ANALYSIS_REPO>>", args.analysis_repo),
                             ("<<BACKEND>>", args.backend)):
            content = content.replace(token, value)
        # The "not set up yet" notice stops being true the moment this step runs.
        head, sep, rest = content.partition("<!-- setup-banner -->")
        if sep:
            content = head + rest.partition("<!-- /setup-banner -->\n")[2]
        if content != claude_md.read_text(encoding="utf-8"):
            write(claude_md, content)
    return 0


def cmd_sync(args):
    state = load_state().get("workspace", {})
    extras = state.get("extras", ["dev", "notebooks", "plotly"]) + (args.extra or [])
    cmd = ["uv", "sync"]
    for extra in dict.fromkeys(extras):
        cmd += ["--extra", extra]
    run(cmd, cwd=ROOT)
    return 0


# ---------------------------------------------------------------------------

def main(argv=None):
    global DRY_RUN
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print what would run; change nothing")
    sub = ap.add_subparsers(dest="step", required=True)

    sub.add_parser("check")

    p = sub.add_parser("workspace")
    p.add_argument("--repo", help="OWNER/NAME for this workspace's own repo")
    p.add_argument("--visibility", choices=("private", "public"), default="private")

    p = sub.add_parser("writing")
    p.add_argument("--mode", choices=("adapt", "import", "fresh"), required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--dir", required=True)
    p.add_argument("--title")
    p.add_argument("--author")
    p.add_argument("--source", help="import mode: OWNER/NAME or a local path of the existing document")
    p.add_argument("--visibility", choices=("private", "public"), default="private")

    p = sub.add_parser("analysis")
    p.add_argument("--repo", required=True)
    p.add_argument("--dir", required=True)
    p.add_argument("--writing-dir", required=True)
    p.add_argument("--distribution", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--backend", choices=("plotly", "matplotlib"), default="plotly")
    p.add_argument("--visibility", choices=("private", "public"), default="private")

    p = sub.add_parser("root")
    p.add_argument("--name", required=True)
    p.add_argument("--writing-dir", required=True)
    p.add_argument("--writing-repo", required=True)
    p.add_argument("--writing-mode", choices=("adapt", "import", "fresh"), required=True)
    p.add_argument("--analysis-dir", required=True)
    p.add_argument("--analysis-repo", required=True)
    p.add_argument("--backend", choices=("plotly", "matplotlib"), default="plotly")

    p = sub.add_parser("sync")
    p.add_argument("--extra", action="append", help="an extra beyond workspace.toml's `extras`")

    args = ap.parse_args(argv)
    DRY_RUN = args.dry_run
    if args.step == "writing" and args.mode != "adapt" and not (args.title and args.author):
        ap.error("--title and --author are required unless --mode adapt")

    return {"check": cmd_check, "workspace": cmd_workspace, "writing": cmd_writing,
            "analysis": cmd_analysis, "root": cmd_root, "sync": cmd_sync}[args.step](args)


if __name__ == "__main__":
    sys.exit(main())
