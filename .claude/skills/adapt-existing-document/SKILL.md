---
name: adapt-existing-document
description: Adapt an existing LaTeX document to the conventions the figure tooling needs (Sections/<Name>/Figures, \graphicspath, bare filenames, labels mirroring filenames), one section at a time — in place, or moved from .setup/import-source/ into the template. Use after setup-doc-workspace in adapt or import mode, or when generated figures aren't found by the document.
---

# Adapt an existing document

Read `workspace.toml` at the workspace root for `writing_dir`, `analysis_dir` and
`writing_mode`. Then read `<writing_dir>/AGENTS.md` and the template's
[SETUP.md](https://github.com/c-energie/writing-template/blob/main/SETUP.md) section
"Adapting an existing document" — that is the authority; this skill is the procedure.

Rules:
- **One section at a time.** Move one, prove a figure lands, commit, then the next.
- **Never rename a committed figure file**, and never change prose. Layout and markup only.
- **Ask before every commit and push.** In `adapt` mode the repo is live on Overleaf: a
  push followed by "Pull GitHub changes into Overleaf" is what makes a change real there.
- You cannot see a rendered PDF. What you can check: balanced braces, every
  `\subfile`/`\input`/`\include`/`\includegraphics`/`\ref` target exists. If the user has
  latexmk (`make` in the writing dir), use it; otherwise ask them to recompile on Overleaf
  after each section and report errors back.

## What is required, and what is not

| Required | Why it matters |
|---|---|
| A root `.tex` at the repo root | Everything starts there. `main.tex`, `thesis.tex`, `dissertation.tex`, `report.tex`, `book.tex` are found automatically; any other name → set `DOC_MAIN_TEX=<name>.tex` in `<analysis_dir>/.env`. **Do not rename it.** |
| Figures referenced by **bare filename** (`\includegraphics{foo.png}`, never `figs/ch2/foo.png`) | `\graphicspath` resolves them; the tooling indexes by name |
| Labels mirroring filenames (`foo.png` ↔ `\label{Fig: foo}`) | How the analysis tooling knows a figure is already placed; without it, re-running a notebook appends a duplicate block |
| Sections that get generated figures live in `Sections/<Name>/` with a `Figures/` dir | Where `doc_analysis` writes |
| Figure filenames unique across the whole document | Two matches = `ambiguous`, silently dropped from wiki/site |

Not required — leave alone: the document class, the root filename, the `.sty` name, the
bibliography location, whether a glossary exists, `\chapter` vs `\section`.

## Mode `adapt` — restructure in place

1. **Survey.** List the root `.tex`, how sections are pulled in (`\subfile`/`\input`/`\include`),
   where figures live, every `\graphicspath` (and which file it is in), and every
   `\includegraphics` that uses a path or extension. Report it as a table and agree with
   the user which section to do first — pick one that will get generated figures soonest.
2. **Move one section.**
   ```bash
   mkdir -p Sections/<Name>/Figures
   git mv <old>/<file>.tex Sections/<Name>/
   git mv <old figure files for this section> Sections/<Name>/Figures/
   ```
   `git mv` (not copy) keeps history and lets Overleaf's sync see a move.
3. **Fix the references.** The `\input`/`\subfile` line in the root `.tex`; add
   `Sections/<Name>/Figures/` to `\graphicspath` (it does **not** recurse — one entry per
   directory, each with a trailing slash, each in its own braces); make that section's
   `\includegraphics` bare filenames. If a section used `\subfile`, the `subfiles` package
   must already be loaded; don't introduce it if they use `\input`.
4. **Labels.** For figures this section's notebooks will (re)generate, the label must be
   `Fig: <stem>`. Renaming a label means updating every `\ref`/`\cref` to it — grep the
   whole repo. Leave figures nobody will regenerate alone.
5. **Prove it.** Recompile (local `make` or Overleaf). Then, from the analysis repo,
   `uv run notebook-skeleton new <Name> <notebook>` and fill in its figure cell to save one
   figure for this section. (If `/adapt-existing-analysis` will bring this section's real
   notebooks in later, delete this one then.) Confirm the PNG landed in
   `Sections/<Name>/Figures/` and a commented `\begin{figure}` block was appended.
6. **Commit** in the writing repo (ask), push, then Overleaf → Pull GitHub changes.
7. Repeat for the next section. Sections that will never hold generated figures may stay
   where they are.

## Mode `import` — move into the template layout

The new writing repo is the initialised template; the old document is in
`.setup/import-source/` (read-only reference — never edit it, never commit it).

1. **Class and preamble.** Copy any `.cls` beside `main.tex` and swap the `\documentclass`
   line. Move the old preamble's packages and macros into `document_settings.sty`, keeping
   what the template already loads and resolving duplicate/conflicting packages with the
   user. Old acronym/glossary entries → `glossary_terms.tex`.
2. **Front matter** into `Preamble/` (title page, abstract, acknowledgements).
3. **Bibliography** `.bib` files into `Bibliographies/`; fix `\addbibresource`. If the old
   document used BibTeX (`\bibliography{}`) rather than biblatex, ask before converting.
4. **Sections**, one at a time, each into `Sections/<Name>/<file>.tex` with its figures in
   `Sections/<Name>/Figures/`, a `\subfile` line in `main.tex` in reading order, and a
   `\graphicspath` line in `document_settings.sty`. Each section file needs the
   `\documentclass[../../main.tex]{subfiles}` wrapper — copy it from
   `Sections/Example/example.tex`. Apply the bare-filename and label rules above as you go.
5. Once the first real section compiles and a generated figure lands in it, **delete
   `Sections/Example/`**, its `\subfile` line and its `\graphicspath` entry, and the
   example notebook in the analysis repo (`notebooks/example/`) and its `figures_config.toml`
   entry. Re-run `uv run check-figure-parity --snapshot` from the analysis dir.
6. Diff the old and new document for lost content: every `\label` in the old should exist
   in the new. Report any that don't.
7. Commit (ask), push, then Overleaf **New Project → Import from GitHub**. Delete
   `.setup/import-source/` at the workspace root.

## Finish

Update `<writing_dir>/AGENTS.md` so its layout description matches the document as it now
is (it was written for the template's example layout). Then suggest `/setup-doc-publish`
if they want a corpus/wiki/site — its `doc-publish build` is the strictest audit of
everything above and will name anything still unresolved.
