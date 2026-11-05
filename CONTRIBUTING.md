# Contributing

Thanks for helping. This repo is plain text and standard-library Python, so most changes are easy to review.

## Ground rules

- **Evidence over opinion.** A skill that says "check X" should say how, and scanners must say they find leads, not verdicts.
- **No network calls, no extra dependencies** in scripts or hooks (Python standard library only). Hooks must never block or fail a session and must never print a secret value.
- **Do not bundle third-party skills or assets.** The installer downloads them from their authors at pinned commits; add new ones to `skills.json` with repo, commit, license and path.
- **Be honest about testing.** If you could not run it, say so in the docs.

## Setup and checks

```bash
git clone https://github.com/quiczz/ship-safe-skills.git
cd ship-safe-skills
python3 tools/validate.py          # must pass: front matter, manifests, scripts, hooks, self-tests
python3 tools/build_release.py     # builds dist/*.zip
claude plugin validate .           # if you have Claude Code
```

## Adding or changing a skill

1. Create `skills/<name>/SKILL.md` with front matter `name` (equal to the folder, lowercase and hyphens) and `description` (under 1024 characters; say what it does **and when to use it**; include a "use proactively when..." clause if it should run on its own).
2. Put detail in `references/`, scripts in `scripts/`, copyable files in `templates/`. Keep `SKILL.md` under about 500 lines and link to the rest.
3. Add the name to `own` in `skills.json`.
4. If it has a scanner, test it on a small project with **planted** problems (to prove it finds them) and on a clean one (to prove it stays quiet). Add the real output to `docs/examples/`.
5. Add a row to the README tables and a section to `docs/skills.md`.
6. Bump the version in both plugin manifests and add a `CHANGELOG.md` line.

## Changing autopilot

Edit `hooks/autopilot.py`. Keep it fast (well under a second), quiet, and non-blocking. Add a test case to `tools/validate.py` for new checks.

## Pull requests

Describe what changed and how you tested it. Small, focused PRs are reviewed fastest.
