---
name: setup-doc-workspace
description: First-run setup of a document workspace — create the writing and analysis repos from the c-energie templates and prove a figure lands in the document. Use when workspace.toml is missing at the workspace root, or the user asks to set up the workspace or bring an Overleaf document into it.
---

# Set up a document workspace

The end state, mirroring the reference thesis workspace:

```
<workspace>/                 this repo — a SHELL: tracks CLAUDE.md, .claude/, pyproject.toml,
|                            workspace.toml, .gitignore; ignores both members
|-- <doc>-writing/           LaTeX. Own repo. Goes to Overleaf.
|-- <doc>-analysis/          Python figure/table tooling (doc_analysis). Own repo.
|                            Writes into <doc>-writing via DOC_REPO in its .env.
|-- pyproject.toml           uv workspace root; <doc>-analysis is its one member
`-- .venv/                   shared venv, created by `uv sync` HERE
```

All mechanical work is done by `setup_workspace.py` beside this file. Your job is the
interview, running its steps in order, and the judgment work the script cannot do.
Always run it through uv — the system Python may be too old, uv fetches a right one:

```bash
uv run --no-project --python 3.12 .claude/skills/setup-doc-workspace/setup_workspace.py <step> [flags]
```

Abbreviated below as `SETUP <step>`. Every step accepts `--dry-run` (before `<step>`); use
it to show the user the plan before the first step that creates a GitHub repo.

Rules:
- **Ask, don't guess** wherever the interview below says ask. Offer the default in brackets.
- **Never commit or push in any repo without asking.** The script creates repos and
  clones; it never commits. Creating a GitHub repo is outward-facing — confirm the full
  list of repos (names, owner, visibility) once, before the first `gh repo create`.
- Stop on the first failed step. Diagnose, fix, re-run that step — every step is safe to
  re-run (it reuses an existing repo / checkout rather than clobbering it).

## 0. Prerequisites

```bash
SETUP check
```

If `uv` itself is missing the command above cannot run — give the install command first:

| Tool | Windows | macOS | Linux |
|---|---|---|---|
| uv | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` or `winget install --id astral-sh.uv -e` or `pip install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` or `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| git | `winget install --id Git.Git -e` | `xcode-select --install` | `sudo apt install git` |
| gh (GitHub CLI) | `winget install --id GitHub.cli -e` | `brew install gh` | `sudo apt install gh` |
| Python ≥ 3.11.4 | `uv python install 3.12` (uv manages it; no system Python needed) | same | same |

Then `gh auth login` (HTTPS; let it configure git). After any install the user must open
a **new terminal** (and restart Claude Code) so PATH picks it up. Work down every `FAIL`
line until `check` exits 0. `--` lines (latexmk, make) are optional: Overleaf compiles the
document without a local TeX install.

## 1. Interview

Ask in this order, a few questions at a time. Collect everything before running anything.

1. **Document short name** `<doc>` — lower-case, dashes (e.g. `thesis`, `gridflex-report`).
   Default: this workspace directory's name.
2. **GitHub owner** for the new repos. Default: the `gh` login from `check`. May be an org
   they belong to.
3. **Visibility** — default `private` (a template's visibility is not inherited; unpublished
   work should be private).
4. **Repo / directory names** — default `<doc>-writing` and `<doc>-analysis`, directory
   name = repo name. Let them override either.
5. **Where is the document now?** This picks the writing mode:

   | Answer | Mode | What happens |
   |---|---|---|
   | On Overleaf, and I want to keep that project and its history | `adapt` | Overleaf's GitHub sync creates `<owner>/<doc>-writing`; the script clones it and adds the template's `AGENTS.md`/`CLAUDE.md`/ignore rules. The document is then adapted to the conventions in place. |
   | Exists (Overleaf or elsewhere), but I'd rather start from the template's layout | `import` | New repo from writing-template; the old document is staged in `.setup/import-source/` and moved into the template structure. A **new** Overleaf project is then imported from GitHub; the old one is retired. |
   | Nothing yet | `fresh` | New repo from writing-template. |

   If unsure, recommend `adapt` for anyone with an active Overleaf project and
   collaborators/supervisors commenting there, `import` for a messy or short document.

6. **Overleaf GitHub sync** (modes `adapt`, and `import` when the source is on Overleaf).
   This needs a premium Overleaf plan — many universities provide one; ask. If they do
   not have it, stop and say so: this setup only supports Overleaf via GitHub sync. For
   `import` they can instead download the project zip and give a local path as source.

   For `adapt`, walk them through it now and wait for confirmation:
   > In Overleaf, open the project → left-hand panel → **Integrations** → **GitHub** →
   > connect your GitHub account if you haven't before → enter owner `<owner>` and repo
   > name exactly `<doc>-writing`, private. Overleaf pushes the project there.

   For `import` from Overleaf: same steps but any repo name (e.g. `<doc>-overleaf-old`);
   that repo is the `--source`.
7. **Title and author** (modes `import`/`fresh` — fills the template's placeholders).
   Author is also asked for the analysis repo in every mode.
8. **Plotting backend** — `plotly` (default, recommended: one figure object gives the PDF
   PNG *and* an interactive HTML for a wiki/site) or `matplotlib` (static PNG only, no
   headless-Chrome download).
9. **Analysis distribution name** — default `<doc>-analysis`. Lower-case, digits, dashes.
   The import package stays `doc_analysis` regardless; say so if they ask why.

10. **Existing analysis?** — a project with notebooks that should feed this document: its
    local path or `OWNER/NAME`, or none. The analysis repo is still created fresh from the
    template; the existing project is copied into it in step 8 and left untouched.

Read back a summary table (every repo to be created, every directory, mode, backend) and
get an explicit yes.

## 2. Make the workspace its own repo

```bash
SETUP workspace
```

If it reports origin is already theirs (they used **Use this template**), move on. If it
reports origin is the template, or none, ask for the workspace repo name (default `<doc>`)
and run `SETUP workspace --repo <owner>/<name> --visibility private`. That renames the
template remote to `template` (kept for pulling template updates) and pushes to the new repo.

## 3. The writing repo

```bash
SETUP writing --mode adapt  --repo <owner>/<doc>-writing --dir <doc>-writing
SETUP writing --mode import --repo <owner>/<doc>-writing --dir <doc>-writing --title "<title>" --author "<author>" --source <owner/old-repo | path>
SETUP writing --mode fresh  --repo <owner>/<doc>-writing --dir <doc>-writing --title "<title>" --author "<author>"
```

## 4. The analysis repo

```bash
SETUP analysis --repo <owner>/<doc>-analysis --dir <doc>-analysis --writing-dir <doc>-writing \
               --distribution <doc>-analysis --author "<author>" --backend plotly
```

This runs the template's `init.py` with the answers, which writes `<doc>-analysis/.env`
with an absolute `DOC_REPO`. That file is per-machine and gitignored — correct as is.

## 5. The workspace root

```bash
SETUP root --name <doc> --writing-dir <doc>-writing --writing-repo <owner>/<doc>-writing \
           --writing-mode <mode> --analysis-dir <doc>-analysis --analysis-repo <owner>/<doc>-analysis \
           --backend plotly
```

Writes `pyproject.toml` (uv workspace root), `workspace.toml` (what the other skills read),
the member block in `.gitignore`, and fills the `<<...>>` placeholders in `CLAUDE.md`.

## 6. Install

```bash
SETUP sync
```

= `uv sync --extra dev --extra notebooks --extra <backend>` at the root. Then:

- **plotly backend only — Chrome for PNG export.** kaleido renders through Chrome/Chromium.
  If none is installed, `uv run plotly_get_chrome` fetches one (or install Chrome:
  `winget install --id Google.Chrome -e` / `brew install --cask google-chrome`). Prove it:
  `uv run python -c "import plotly.express as px; px.scatter(x=[1],y=[1]).write_image('kaleido_check.png')"`
  then delete `kaleido_check.png`.
- **Tests**, from the analysis dir (uv finds the root venv):
  `cd <doc>-analysis && uv run python -m pytest tests -q`.
  Use `python -m pytest`; plain `uv run pytest` can fail on Windows with
  "trampoline failed to canonicalize script path".
- **Jupyter** comes with the `notebooks` extra: `uv run jupyter lab` from the analysis dir.
- **Optional local LaTeX build** (only if `check` showed latexmk): `make` in the writing dir.
  Never commit the PDF.

## 7. Prove the pipeline

- **`fresh` / `import`**: the writing repo still has `Sections/Example/`. Run
  `<doc>-analysis/notebooks/example/example_figure.ipynb` (plotly only) — e.g.
  `cd <doc>-analysis && uv run jupyter nbconvert --to notebook --execute notebooks/example/example_figure.ipynb --output example_figure.ipynb`.
  Expect a new `example_scatter.png` under `<doc>-writing/Sections/Example/Figures/`.
  (No figure block is appended: `example.tex` already references it — that is the
  duplicate gate working. A *new* figure name gets a commented `\begin{figure}` block.) Then
  `cd <doc>-analysis && uv run check-figure-parity --snapshot`.
  On matplotlib, copy the README's matplotlib usage block into a scratch notebook instead.
- **`adapt`**: the document has no `Sections/Example/`, so skip this. The proof happens
  in the next skill, against the first section moved into `Sections/`.

## 8. Bring existing work in

- **Document** (modes `adapt` and `import`): invoke the **adapt-existing-document** skill.
  It is judgment work (moving sections, `\graphicspath`, labels) done one section at a
  time with the user, not a script.
- **Analysis** (an existing project named in question 10): then invoke the
  **adapt-existing-analysis** skill. It runs after the document, because notebooks are
  placed by the document's `Sections/`.

## 9. Overleaf wiring

- `adapt`: already linked. Walk the user through the routine in the workspace `CLAUDE.md`,
  "Overleaf routine" — its order (pull before regenerating figures) is what keeps prose
  edited on Overleaf from colliding with regenerated figures.
- `import` / `fresh`: once the document builds, in Overleaf **New Project → Import from
  GitHub** → `<owner>/<doc>-writing`. For `import`, tell the user to archive the old
  Overleaf project so no one keeps editing it.
- Either way: **set the Overleaf compiler** (Menu → Settings) to whatever the document
  needs — the template uses biblatex/biber; lualatex or pdflatex both work for it.

## 10. Commit and finish

1. In each member, show `git status` and propose a commit (`adapt`: the overlay files;
   `fresh`/`import`: the initialised template plus any example figure). Ask before each
   commit and each push.
2. At the workspace root, the files to commit are `CLAUDE.md`, `.gitignore`,
   `pyproject.toml`, `uv.lock`, `workspace.toml`. Ask, then commit and push.
3. Delete `.setup/import-source/` once an `import` is finished (gitignored, but stale).
   `.setup/analysis-import/` belongs to adapt-existing-analysis, which deletes it itself.
4. Offer the optional next step: **/setup-doc-publish** (corpus, Notion wiki, Quarto site).
5. Point them at the `CLAUDE.md` at the workspace root — it is now filled in and is what
   every future session here loads.
