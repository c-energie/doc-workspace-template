# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this workspace.

<!-- setup-banner -->
> **Not set up yet?** `workspace.toml` does not exist beside this file, so nothing below is
> true yet and the `<<...>>` names are unfilled. Run **/setup-doc-workspace** first.
<!-- /setup-banner -->

## What this directory is

The `<<WORKSPACE>>` workspace: two independent checkouts that together author, illustrate
and publish one long LaTeX document. Made from `c-energie/doc-workspace-template`.

It is **itself a git repo, but only as a SHELL**: it tracks this file, `.claude/`,
`pyproject.toml`, `uv.lock`, `workspace.toml` and `.gitignore`, and ignores both members.

| Path | Remote | Role |
|---|---|---|
| `<<WRITING_DIR>>/` | `<<WRITING_REPO>>` | The LaTeX document. Pure markup — no Python. Compiled on Overleaf (GitHub sync). |
| `<<ANALYSIS_DIR>>/` | `<<ANALYSIS_REPO>>` | Notebooks + `doc_analysis` figure/table tooling. **Writes into** the document repo. |
| `pyproject.toml` | this repo | uv workspace root; the analysis repo is its one member. |
| `.venv/` | — | The one venv. Created by `uv sync` at this root. |

Each member is a repo in its own right: **a commit here records only workspace work.**
Commit member changes inside the member. Each has its own `CLAUDE.md`/`AGENTS.md` — read
it before editing there.

`c-energie/doc-publish` (optional; `/setup-doc-publish`) is not checked out: it is installed
into the venv through the analysis repo's `publish` extra and run from `<<ANALYSIS_DIR>>/`.
Its per-document state lives in `<<WRITING_DIR>>/.doc-publish/`.

## The pipeline

```
<<ANALYSIS_DIR>>/notebooks ──save_fig──┬─> Sections/<Name>/Figures/<stem>.png + \begin{figure} block ─> <<WRITING_DIR>> ─> Overleaf ─> PDF
                                    └─> figures_html/<stem>.html + figures_manifest.json ─> doc-publish ─> wiki / site
```

**`DOC_REPO` is the only joint.** It is set in `<<ANALYSIS_DIR>>/.env` (gitignored,
per-machine, absolute path). Never in a shell profile — a user-level value silently writes
figures into the wrong document. A real shell variable still wins over the file.

## Commands

From the workspace root:

```bash
uv sync --extra dev --extra notebooks --extra <<BACKEND>>    # pass EVERY extra you use; uv removes the rest
# or, reading the extras list from workspace.toml:
uv run --no-project --python 3.12 .claude/skills/setup-doc-workspace/setup_workspace.py sync
```

From `<<ANALYSIS_DIR>>/` (uv finds the root venv):

```bash
uv run python -m pytest tests -q        # not `uv run pytest`: Windows trampoline error
uv run jupyter lab
uv run check-figure-parity              # after regenerating figures; non-zero on drift
uv run check-figure-parity --snapshot   # record a new baseline
uv run check-figure-parity --figures    # which saved figures the document actually renders
uv run doc-publish doctor|build|check   # if /setup-doc-publish has been run
```

The LaTeX is compiled on Overleaf. `make` in `<<WRITING_DIR>>/` is optional and local only.
Never commit a built PDF.

## Overleaf routine (GitHub sync)

Figures arrive from the analysis repo, a third place, so order matters:

1. In Overleaf: **left-hand panel → Integrations → GitHub → Push Overleaf changes to GitHub**.
2. `git pull` in `<<WRITING_DIR>>/` — **before** regenerating any figure.
3. Run notebooks; commit `Sections/` in `<<WRITING_DIR>>/`; push.
4. In Overleaf: **Pull GitHub changes into Overleaf**.

## Rules that break things silently

- **Never rename or move a committed figure.** LaTeX resolves bare filenames via
  `\graphicspath`; doc-publish indexes by name. A rename breaks both with no error.
- **Figure filenames are unique document-wide**, and labels mirror them
  (`foo.png` ↔ `\label{Fig: foo}`) — that is how re-running a notebook knows not to append
  a second block.
- **`\graphicspath` does not recurse.** One entry per figure directory.
- **Keep private analysis code out of `<<ANALYSIS_DIR>>/src/`.** Add it as an extra and
  import it from notebooks only, so `doc_analysis` stays installable on its own.
- **Don't delete `<<WRITING_DIR>>/.doc-publish/*.json`.** They map the document to live
  Notion pages and stable site URLs.

## Skills here

| Skill | Use |
|---|---|
| `/setup-doc-workspace` | First-run setup: create both repos from the templates (or adopt an Overleaf project), name them, install, prove the pipeline. Safe to re-run. |
| `/adapt-existing-document` | Bring an existing document into the `Sections/` / `\graphicspath` / label conventions, one section at a time. |
| `/adapt-existing-analysis` | Copy an existing analysis project's notebooks in — the original stays untouched — and retrofit each with the `save_fig`/`save_table` setup. |
| `/setup-doc-publish` | Optional: corpus, Notion wiki, Quarto site. |
| `/setup-observer` | Invoked by the setup skills: logs deviations from the guide and, with consent, files them on GitHub. |
