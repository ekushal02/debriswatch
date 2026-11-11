#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
repo_name="${1:-debriswatch}"
if ! command -v gh >/dev/null; then
  echo 'Install GitHub CLI, then run: gh auth login'; exit 1
fi
gh auth status >/dev/null
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then git init -b main; fi
if [ -z "$(git config user.name || true)" ] || [ -z "$(git config user.email || true)" ]; then
  echo 'Set git user.name and user.email for your own commits first.'; exit 1
fi
git add .
if ! git diff --cached --quiet; then git commit -m 'Implement DebrisWatch backend and inspection dashboard'; fi
if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin HEAD
else
  gh repo create "$repo_name" --private --source=. --remote=origin --push --description 'Jetson-oriented debris inspection backend, event rules, and local dashboard'
fi
