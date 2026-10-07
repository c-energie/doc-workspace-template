---
name: setup-observer
description: Observe a setup run — record each deviation from the setup guide, research its cause outside the guide, and with the user's consent file the findings as GitHub issues or pull requests on the c-energie repo that owns them. Invoked first by setup-doc-workspace, adapt-existing-document, adapt-existing-analysis and setup-doc-publish; or when the user asks to report setup problems.
hooks:
  PostToolUseFailure:
    - matcher: "Bash|PowerShell"
      hooks:
        - type: command
          command: 'mkdir -p "$CLAUDE_PROJECT_DIR/.setup/observer" && { cat; echo; } >> "$CLAUDE_PROJECT_DIR/.setup/observer/events.jsonl"'
---

# Setup observer

The setup guide — the invoking skill, its scripts, and the docs they point at — is **the
thing under test**. Your job alongside running it is to notice every place where reality
and the guide disagree, find out why from evidence outside the guide, and turn that into
reports the maintainer can act on. The setup itself always comes first: fix the problem
as the guide intends, and log it as you go.

```bash
uv run --no-project --python 3.12 .claude/skills/setup-observer/observe.py <step>
```

Abbreviated `OBSERVE <step>`. Everything lives in `.setup/observer/` (gitignored). The hook
in this skill's frontmatter appends every failed shell command to `events.jsonl` for the
rest of the session; it needs nothing installed.

## 1. Baseline

`OBSERVE baseline --skill <invoking skill>` — OS, tool versions, env vars already set
(`DOC_REPO`, a conda or venv), the workspace's state. It opens `log.md` with a session
heading. If `uv` is not installed yet, the hook still records; run the baseline as soon as
`uv` works. Done when the baseline is printed — read it: tools already present, a
`DOC_REPO` already set, an existing venv are deviations-in-waiting.

## 2. Watch

A **deviation** is anything the guide did not predict:
- a command fails, warns, prompts, or prints something the guide does not describe;
- a step was unnecessary (already installed, already exists) or something needed was
  missing from the guide;
- a UI differs from its description (a menu moved, a button renamed);
- a version, path or default differs from what the guide assumes — including a notebook
  kernel or IDE interpreter other than the one the guide names;
- the user does something other than the guide says, or is unsure what it means.

For each, append to `log.md` straight away, while the detail is fresh:

```markdown
### D<n> — <short title>
- step: <skill> §<step>
- expected: "<what the guide says, quoted>"
- found: <what happened; exact error text>
- events: E<n>, ...  (from `OBSERVE events`, when a failed command is involved)
- machine: <the baseline facts that bear on it>
- evidence: <each thing checked, with its result>
- cause: confirmed | likely | unknown — <one line>
- fix: <the concrete change, in which file>
- owner: <repo, from the table below> | upstream | this machine only
```

**Evidence comes from outside the guide**, since the guide is what may be wrong: the
tool's `--help` and `--version`, the installed package's source, the tool's current
documentation or a web search, the template's current code on GitHub (`gh api`,
`gh search code`), and what the user actually saw. `cause: confirmed` needs evidence that
shows it; a plausible story is `likely`.

| Owner | What it covers |
|---|---|
| `c-energie/doc-workspace-template` | these skills and their scripts, the workspace `CLAUDE.md`/`README.md` |
| `c-energie/analysis-template` | `doc_analysis`, `notebook-skeleton`, its `init.py`, README, AGENTS.md |
| `c-energie/writing-template` | the LaTeX template, `SETUP.md`, its `init.py` |
| `c-energie/doc-publish` | the `doc-publish` CLI and its docs |
| upstream | a third-party tool's own bug (uv, gh, Overleaf). Owned by a repo above only if the guide should work around it |
| this machine only | caused by something unique here that no guide change would help |

## 3. Reconcile

At the end of each invoking skill (or when the user stops), `OBSERVE events`. Every event
it marks `!` gets a deviation entry citing it, or a line `- E<n>: noise — <reason>` (a
typo, a probe that is expected to fail). Merge entries describing one problem. Done when
`OBSERVE events` exits 0.

## 4. Report — only with consent

1. Leave out `this machine only` and pure `upstream` entries; mention them to the user.
2. Draft into `.setup/observer/drafts/`, one file per report:
   - **Issue** — the default: one per distinct problem, with expected / found / evidence /
     suggested fix, and the relevant baseline facts (OS, versions).
   - **Pull request** — only when `cause: confirmed` and the fix is a concrete edit to
     text or scripts in the owning repo. Bundle the small doc fixes for one repo into one.
3. `OBSERVE redact .setup/observer/drafts/*`, then read every draft yourself for anything
   else private (data paths, people, project names) and remove it.
4. Look for an existing report: `gh issue list -R <repo> --state all --search "<keywords>"`
   and `gh pr list -R <repo> --state all --search "<keywords>"`. If one matches, offer a
   comment on it instead.
5. Show the user each draft in full, with its target repo, and ask: issue, PR, comment, or
   skip. File only what they say yes to.
6. File:
   - Issue: `gh issue create -R <repo> --title "[setup] <title>" --body-file <draft>`.
   - PR: in `.setup/observer/pr/`, `gh repo fork <repo> --clone` (or `gh repo clone` when
     `gh repo view <repo> --json viewerPermission` says WRITE or ADMIN), branch
     `setup-observer/<slug>`, make the edit, commit, push, then
     `gh pr create -R <repo> --base main --body-file <draft>`. Changes reach `main` only
     through a reviewed pull request.
7. Append each filed URL to its entry in `log.md`. Done when every entry not skipped by
   the user has a URL.
