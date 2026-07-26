#!/usr/bin/env bash
# Publish 4_website/site to the gh-pages branch.
#
# GitHub Pages serves this branch from its root, so the site directory is
# copied to the top level rather than nested. This avoids needing a workflow
# file, which requires a token carrying the `workflow` scope that the default
# one does not have.
#
# Usage: make deploy
set -euo pipefail

SITE_DIR="${MALLSCAPE_SITE_DIR:-4_website/site}"
BRANCH="${MALLSCAPE_PAGES_BRANCH:-gh-pages}"
WORKTREE="$(mktemp -d)"

[ -f "$SITE_DIR/index.html" ] || { echo "no site at $SITE_DIR; run 'make site' first" >&2; exit 1; }

bundle=$(grep -o 'data-bundle="[^"]*"' "$SITE_DIR/index.html" | cut -d'"' -f2)
[ -f "$SITE_DIR/$bundle" ] || { echo "index.html points at $bundle, which is missing" >&2; exit 1; }

cleanup() { git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true; }
trap cleanup EXIT

git worktree add -q --detach "$WORKTREE"
(
  cd "$WORKTREE"
  git checkout -q --orphan "$BRANCH"
  git rm -rq --cached . 2>/dev/null || true
  find . -maxdepth 1 ! -name . ! -name .git -exec rm -rf {} +
)
cp "$SITE_DIR"/* "$WORKTREE/"
touch "$WORKTREE/.nojekyll"   # otherwise Jekyll filters files it does not recognize
(
  cd "$WORKTREE"
  git add -A
  git commit -q -m "publish site from snapshot $(date +%Y-%m-%d)"
  git push -q -f origin "$BRANCH"
)
echo "published $bundle to $BRANCH"
