# Changelog

## 1.2.0

- **Autopilot:** the skills now run on their own. Claude Code hooks (`hooks/hooks.json`, `hooks/autopilot.py`) add standing instructions at session start, a skill hint when a prompt matches, a secret and risky-setting check on every file Claude edits, and a masked transcript save at session end. Never blocks, never prints secret values, no network calls; each part can be switched off. Non-plugin installs: `python3 install.py autopilot on`.
- New skill `motionsite`: animated, video-hero landing pages (template, React hero, ffmpeg asset script, `check_motion.py` audit).
- Skill descriptions now say when Claude should use them proactively; each `SKILL.md` has a "Runs on its own" note.
- New docs: full README with diagrams and screenshots, `docs/autopilot.md`, `docs/install.md`, `docs/skills.md`, `docs/PUBLISHING.md`, real example outputs in `docs/examples/`, `CONTRIBUTING.md`, `SECURITY.md`, issue and PR templates.
- `tools/validate.py` now self-tests autopilot and the new scripts.

## 1.1.0

- New skill `skeletonizer`: finds spinners, blank-while-loading areas and missing `loading.tsx` / `<Suspense>` boundaries, then adds layout-matching skeletons (mirror mode or CSS overlay mode). Includes `skeleton.css`, React primitives, a delay hook against flashes, framework recipes (React, Next.js, Remix, Vue/Nuxt, SvelteKit, Angular, Flutter, SwiftUI, React Native), a scanner and a demo page.

## 1.0.0

First release.

- Six skills: `app-readiness-audit`, `monitor-alerts-builder`, `session-journal`, `build-flow-map`, `api-security-guard` (12 rules, OWASP API Top 10 2023), `zero-trust-review` (12 principles, NIST SP 800-207 / CISA maturity model).
- Claude Code plugin marketplace manifest (`/plugin marketplace add`), `npx skills add` layout, per-skill zips for Claude.ai / Claude Desktop upload.
- `install.py` installer for the skills in this repo plus optional pinned third-party skills (downloaded from their original repos, never bundled).
- `tools/validate.py`, `tools/build_release.py`, `tools/set_owner.py`, GitHub Actions CI and release workflows.
