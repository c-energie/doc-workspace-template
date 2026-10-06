---
name: adapt-existing-analysis
description: Copy an existing analysis project's notebooks into the workspace's analysis repo, placed by document section, and retrofit each with the save_fig/save_table setup. Use after setup-doc-workspace names an existing analysis, or when asked to bring old notebooks in.
---

# Adapt an existing analysis project

**First, invoke `/setup-observer`** (once per session): it records where this guide and
reality disagree, so the maintainer can fix the guide.

## The source is read-only

The existing project is **copied, never modified.** Every file in it stays exactly where
and as it is; all work happens on the copies inside `<analysis_dir>/`.

- Files reach the analysis repo only through `COPY copy`, which only reads the source.
- In the source, only read files and run `git --no-optional-locks` `log`, `show`,
  `ls-files` or `status`.
- Run notebooks only as copies, and only after step 4.1 has pointed every write at the
  analysis repo.
- `COPY verify` re-hashes the source and re-lists every file in it, ignored ones included.
  It must print `OK` at the end of every step below. On `FAIL`, stop and show the user what
  changed.

## Setup

Read `workspace.toml` at the workspace root for `analysis_dir`, `writing_dir`, `backend`.
Read `<analysis_dir>/AGENTS.md`: it is the authority on the saver conventions.

```bash
uv run --no-project --python 3.12 .claude/skills/adapt-existing-analysis/copy_analysis.py <step>
```

Abbreviated `COPY <step>`. The plan lives in `.setup/analysis-import/plan.json`
(gitignored). To re-plan from scratch, delete `.setup/analysis-import/` and any
`.setup/analysis-source/` clone: both are scaffolding, never the original.

Sections are named after the document's `Sections/` tree, so adapt the document first
(`/adapt-existing-document`), at least for the sections these notebooks feed. A notebook
whose section does not exist yet goes to `notebooks/unsorted/`.

## 1. Inventory

Ask where the existing project is: a local path, or `OWNER/NAME` (cloned into
`.setup/analysis-source/`). Then `COPY plan --source <it>`.

The plan gives every file a default `dest`: notebooks → `notebooks/unsorted/`, other files
→ `imported/`, `.env*` files and files over 1 MB → `null` (skipped). It also lists the
document's sections. Done when `plan` printed `Inventoried N file(s) in <the path given>`.

## 2. Placement

Set the `dest` of each notebook and helper in `plan.json`, with the user. Each notebook
goes to `notebooks/<Section path>/<name>.ipynb`, mirroring `<writing_dir>/Sections/`.

1. **Gather evidence per notebook**: the figure files it saves (`savefig`, `write_image`)
   and which `Sections/*/Figures/` already holds a file of that name; its headings; any
   section named in it. A figure already in the document is the strongest evidence.
2. **Propose a table**: notebook → section → evidence. Ask the user about every notebook
   whose evidence is missing or points at two sections, a few at a time. A notebook the
   user cannot place yet stays in `notebooks/unsorted/`.
3. **Helper code** the notebooks import: small modules go in `notebooks/` beside
   `setup_notebook.py` (the setup cell puts that directory on `sys.path`). A package goes
   in through the plan too (`dest: packages/<name>/...`) and becomes an extra pointing at
   that copy — see `<analysis_dir>/AGENTS.md` on keeping it out of `src/`.
4. **Large files, data and secrets** stay `null` unless the user names one to copy.
5. Read back the final table and get an explicit yes.

Done when every notebook `dest` outside `notebooks/unsorted/` matches the table the user
said yes to, and the user has named each notebook left in `unsorted/`.

## 3. Copy

`COPY copy`, then `COPY verify`. Done when copy reports no conflicts and verify prints `OK`.
A conflict means the `dest` already holds different content: agree a different `dest`
with the user and re-run `copy`.

## 4. Retrofit, one notebook at a time

For each placed notebook (`notebooks/unsorted/` ones wait until they have a section):

1. **Point every write at the analysis repo.** Find each path in the copy that resolves
   into the source (absolute paths, and relative ones from the source's old working
   directory). Reads may stay. Anything written there — caches, `to_csv`, pickles,
   `open(..., "w")` — goes under `<analysis_dir>/` instead.
2. From `<analysis_dir>/`:
   `uv run notebook-skeleton retrofit <notebook> --section <Section path>`.
   It inserts the template's setup cell (`SECTION`, `NOTEBOOK`, `TEX`, `save_fig`,
   `save_table`) and lists the lines outside it still saving the old way.
3. Convert each listed line:

   | Listed | Becomes |
   |---|---|
   | `figure save` — `plt.savefig(...)`, `fig.write_image(...)` | `save_fig(fig, "<figure>.png", caption=..., label="<figure>")` |
   | `html export` — `fig.write_html(...)` | removed: `save_fig` writes the interactive export |
   | `table export` — `df.to_latex(...)` written to a file | `save_table(df, "<table>", caption=...)` |
   | `path hack` — `os.chdir`, `sys.path.append` | removed: the setup cell does this |

   `<figure>` is the **existing filename** when the document already has that figure, so
   it is regenerated in place. Remove the notebook's own save helpers and `SAVE = ...`
   flags; `figures_config.toml` decides now. Pin each figure's size as `AGENTS.md` says;
   for a committed PNG, inches = its pixels ÷ `PRINT_DPI` (in `doc_analysis/style.py`).
4. Run it from `<analysis_dir>/`:
   `uv run jupyter nbconvert --to notebook --execute <notebook> --output <notebook file name>`.
5. Done when the notebook runs clean, each converted figure is in
   `<writing_dir>/Sections/<Section>/Figures/` (report the document repo's `git status`),
   and `COPY verify` prints `OK`. Then the next notebook.

## 5. Finish

1. From `<analysis_dir>/`: `uv run check-figure-parity --snapshot`.
2. Ask before each commit and push, in the analysis repo and then the writing repo.
3. Tell the user which notebooks are still in `notebooks/unsorted/` and which files were
   left in the source (`dest: null`).
4. Last `COPY verify`. Once it prints `OK` and nothing is left in `unsorted/`,
   `.setup/analysis-import/` and any `.setup/analysis-source/` clone can be deleted.
