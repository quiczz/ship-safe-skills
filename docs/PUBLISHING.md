# Publishing your own copy

For whoever owns the GitHub repository.

## Fast path

```bash
./publish.sh YOUR_GITHUB_USERNAME
```

It fills in your name, validates everything, builds the zips, makes the first commit and, if the GitHub CLI (`gh`) is logged in, creates the public repository, sets topics and pushes. Without `gh` it prints the commands to run after you create an empty repository at https://github.com/new (no README, no license).

## By hand

```bash
python3 tools/set_owner.py YOUR_GITHUB_USERNAME   # replaces the OWNER / quiczz placeholders
python3 tools/validate.py                         # skills, manifests, scripts, hooks
git init -b main && git add . && git commit -m "Initial release"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/ship-safe-skills.git
git push -u origin main
```

## Make the repository page look right

1. **Social preview:** Settings, General, Social preview, upload [`docs/assets/social-preview.png`](assets/social-preview.png) (1280 by 640). It is the card shown when the link is shared.
2. **About box:** description *Skills for Claude Code that check, build and watch your app, and run on their own.* Topics: `claude-code`, `claude-skills`, `agent-skills`, `ai-security`, `zero-trust`, `owasp`, `monitoring`, `skeleton-loading`.
3. **Releases:** push a tag that matches `version` in `.claude-plugin/plugin.json`:
   ```bash
   git tag v1.1.0 && git push origin v1.1.0
   ```
   The Release workflow builds the per-skill zips (for Claude.ai upload) and attaches them.
4. **Security:** Settings, Code security, enable private vulnerability reporting (referenced by `SECURITY.md`).

## Shipping a change

1. Edit, then `python3 tools/validate.py`.
2. Bump `version` in **both** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`; add a line to `CHANGELOG.md`.
3. Commit, tag `vX.Y.Z`, push the tag. Plugin users only receive an update when the version changes.

## What the CI does

- `ci.yml`: on every push and pull request, runs `tools/validate.py`, builds the zips, and installs the skills and autopilot into a temporary home.
- `release.yml`: on a `v*` tag, checks the tag equals the plugin version, builds the zips and creates a GitHub release with them. (These workflows have not run on GitHub yet; check the first run.)
