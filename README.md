# doc-workspace-template

A workspace for writing one long LaTeX document — thesis, report, book — with generated
figures, kept as two repositories side by side:

```
my-thesis/                 ← this template: the workspace shell + Claude Code skills
├── my-thesis-writing/     ← the LaTeX   (c-energie/writing-template, or your Overleaf project)
└── my-thesis-analysis/    ← the figures (c-energie/analysis-template)
```

Notebooks in the analysis repo write PNGs and `\begin{figure}` blocks straight into the
document repo; Overleaf compiles it via GitHub sync. Optionally,
[doc-publish](https://github.com/c-energie/doc-publish) turns the same LaTeX into a Notion
wiki or a Quarto site.

## Start

You need **git**, the **GitHub CLI** and **uv** installed, and **Claude Code**:

| | Windows | macOS | Linux |
|---|---|---|---|
| git | `winget install --id Git.Git -e` | `xcode-select --install` | `sudo apt install git` |
| GitHub CLI | `winget install --id GitHub.cli -e` | `brew install gh` | `sudo apt install gh` |
| uv | `winget install --id astral-sh.uv -e` | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Claude Code | `npm install -g @anthropic-ai/claude-code` (needs Node 18+: `winget install --id OpenJS.NodeJS.LTS -e` / `brew install node`), or see https://docs.claude.com/en/docs/claude-code |

(`pip install uv` also works.) Python itself is not a prerequisite — uv installs one.

```bash
gh auth login
gh repo create my-thesis --template c-energie/doc-workspace-template --private --clone
cd my-thesis
claude
```

Then, in Claude Code:

```
/setup-doc-workspace
```

It checks the prerequisites, asks you a handful of questions (names, whether you have an
existing Overleaf project, plotting backend), creates `my-thesis-writing` and
`my-thesis-analysis` as **your own** repos from the templates, installs everything and
proves a figure lands in the document. It asks before creating any repo and before any
commit or push.

**Have an existing Overleaf document?** That is the main case this is built for. You will
need Overleaf's GitHub sync (a premium feature; many universities provide it). You can
keep your Overleaf project and its history (`adapt`), or move the content into the
template's layout (`import`).

Cloned this template directly instead of using `--template`? Fine — the setup skill
notices and offers to give the workspace its own repo.

## Skills

| Skill | |
|---|---|
| `/setup-doc-workspace` | First-run setup. Safe to re-run. |
| `/adapt-existing-document` | Move an existing document onto the conventions the tooling needs, a section at a time. |
| `/setup-doc-publish` | Optional: corpus, Notion wiki, Quarto site. |

The mechanical steps live in
`.claude/skills/setup-doc-workspace/setup_workspace.py` (stdlib Python, run via
`uv run --no-project --python 3.12 …`), so they can be run by hand too — `--help` lists them.

## Further reading

- [writing-template/SETUP.md](https://github.com/c-energie/writing-template/blob/main/SETUP.md) —
  the conventions an existing document must satisfy, and both Overleaf workflows.
- [analysis-template/README.md](https://github.com/c-energie/analysis-template) —
  `save_fig`, `figures_config.toml`, backends.
