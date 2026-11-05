#!/usr/bin/env bash
# Publish this folder to GitHub as a public repo.
#   ./publish.sh YOUR_GITHUB_USERNAME
# Needs: git, python3. Uses the GitHub CLI (gh) if it is installed and logged in;
# otherwise prints the three commands to run after creating the repo in the browser.
set -euo pipefail
cd "$(dirname "$0")"

USER_NAME="${1:-}"
if [ -z "$USER_NAME" ]; then echo "Usage: ./publish.sh YOUR_GITHUB_USERNAME"; exit 1; fi
REPO="ship-safe-skills"

python3 tools/set_owner.py "$USER_NAME"
python3 tools/validate.py
python3 tools/build_release.py

[ -d .git ] || git init -q -b main
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-$USER_NAME}" -c user.email="${GIT_AUTHOR_EMAIL:-$USER_NAME@users.noreply.github.com}" \
    commit -q -m "Initial release" || echo "(nothing new to commit)"

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh repo create "$USER_NAME/$REPO" --public --source=. --remote=origin --push \
    --description "Skills for Claude Code: app readiness audit, monitoring, session journal, build-flow map, API security (12 rules), Zero Trust review (12 principles)"
  gh repo edit "$USER_NAME/$REPO" --add-topic claude-code --add-topic agent-skills --add-topic claude-skills --add-topic security --add-topic zero-trust || true
  echo
  echo "Published: https://github.com/$USER_NAME/$REPO"
else
  echo
  echo "gh is not installed or not logged in. Do this instead:"
  echo "  1. Create an EMPTY public repo named $REPO at https://github.com/new (no README, no license)."
  echo "  2. Run:"
  echo "       git remote add origin https://github.com/$USER_NAME/$REPO.git"
  echo "       git push -u origin main"
fi

cat <<MSG

Finish the repository page (see docs/PUBLISHING.md):
  - Settings > General > Social preview: upload docs/assets/social-preview.png
  - Settings > Code security: enable private vulnerability reporting

Make a release with downloadable zips (for Claude.ai / Desktop upload):
  git tag v1.2.0 && git push origin v1.2.0
The release workflow builds the zips and attaches them automatically.

Users then install with:
  /plugin marketplace add $USER_NAME/$REPO
  /plugin install $REPO@$REPO
MSG
