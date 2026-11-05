# Install, update and uninstall

## A. Claude Code plugin (recommended)

```text
/plugin marketplace add quiczz/ship-safe-skills
/plugin install ship-safe-skills@ship-safe-skills
```

Restart Claude Code. Skills are namespaced by the plugin: `/ship-safe-skills:app-readiness-audit`, and so on. Autopilot comes with it.

- Update: `/plugin marketplace update ship-safe-skills` (new versions arrive when `version` changes in `plugin.json`).
- Uninstall: `/plugin uninstall ship-safe-skills@ship-safe-skills`.
- Check: `/plugin` lists installed plugins; `/hooks` lists active hooks.

## B. Skills CLI

```bash
npx skills add quiczz/ship-safe-skills
```

Pick the skills and agents. Skills only; no autopilot. (The `skills` CLI is a third-party tool; check its help for options such as global install.)

## C. Copy the folders

```bash
git clone https://github.com/quiczz/ship-safe-skills.git
cp -r ship-safe-skills/skills/* ~/.claude/skills/             # every project
cp -r ship-safe-skills/skills/* YOUR-PROJECT/.claude/skills/  # one project
```

Restart Claude Code. Skills only. Add autopilot afterwards with `python3 install.py autopilot on`.

Uninstall: delete the folders you copied.

## D. The installer

Needs Python 3.8+ and git (git only for third-party downloads).

```bash
python3 install.py install --own           # the 8 skills; asks whether to turn autopilot on
python3 install.py install --own -y        # no questions, autopilot on
python3 install.py install --own --no-autopilot
python3 install.py install --own --project # into ./.claude/skills for this project
python3 install.py autopilot on|off|status [--project]
python3 install.py list                    # everything available
python3 install.py uninstall app-readiness-audit
```

`--project` installs to `./.claude/skills`; with autopilot it writes `.claude/settings.local.json`, which holds a path on your machine and should not be committed.

## E. Claude.ai and Claude Desktop

1. Open the repo's **Releases** page and download the zip for the skill you want (for example `zero-trust-review.zip`). There is also `ship-safe-skills-all-skills-<version>.zip` for copying into `~/.claude/skills/`; that bundle is **not** for the uploader.
2. In Claude: **Settings, Capabilities, Skills, Upload**.
3. Repeat per skill.

Each per-skill zip has the skill folder at its root, which is what the uploader expects. Skills with scripts need code execution enabled. There are no hooks in Claude.ai, so autopilot does not apply; the skills still trigger from their descriptions.

Build the zips yourself: `python3 tools/build_release.py` (output in `dist/`).

## Which to pick

| You use | Choose |
|---------|--------|
| Claude Code and want everything | A |
| Claude Code, no plugins | D |
| Several coding agents | B |
| Locked-down machine, full control | C |
| Claude.ai or Desktop chat | E |

## Troubleshooting

- **Skills do not appear:** restart Claude Code; check the folder is `~/.claude/skills/<name>/SKILL.md` (one level, not nested inside another folder).
- **Plugin marketplace add fails:** confirm the repo is public and the name is exact; `/plugin marketplace add https://github.com/quiczz/ship-safe-skills.git` also works.
- **Both plugin and autopilot installed:** run `python3 install.py autopilot off`.
- **Claude.ai rejects the zip:** use a per-skill zip; the skill folder must be at the zip root.
