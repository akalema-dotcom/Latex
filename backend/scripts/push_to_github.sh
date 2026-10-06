#!/usr/bin/env bash
# ============================================================
# scripts/push_to_github.sh
# ============================================================
# Push the AI Business Workforce backend to GitHub.
#
# USAGE:
#   ./scripts/push_to_github.sh
#
# REQUIRES:
#   - GitHub CLI (gh) installed
#   - OR a Personal Access Token set in env var GITHUB_TOKEN
#
# This script will:
#   1. Authenticate with GitHub (interactive browser flow if gh is installed)
#   2. Push the current branch to origin/main
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

REMOTE_URL="https://github.com/akalema-dotcom/Latex.git"

# Make sure 'origin' is set
if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$REMOTE_URL"
fi

# Path 1: try gh CLI
if command -v gh >/dev/null 2>&1; then
    echo "==> GitHub CLI detected."
    if ! gh auth status >/dev/null 2>&1; then
        echo "==> Not logged in. Starting interactive login..."
        echo "    Choose: GitHub.com → HTTPS → Login with a web browser"
        gh auth login --hostname github.com --git-protocol https --web
    fi
    echo "==> Pushing to origin/main..."
    git push -u origin main
    echo "==> Done. Visit: https://github.com/akalema-dotcom/Latex"
    exit 0
fi

# Path 2: use GITHUB_TOKEN env var
if [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "==> Using GITHUB_TOKEN from environment."
    git remote set-url origin "https://x-access-token:${GITHUB_TOKEN}@github.com/akalema-dotcom/Latex.git"
    git push -u origin main
    echo "==> Done. Visit: https://github.com/akalema-dotcom/Latex"
    # Reset URL so the token isn't persisted in git config
    git remote set-url origin "$REMOTE_URL"
    exit 0
fi

# Path 3: prompt user for token
cat <<EOF

============================================================
No GitHub credentials found.

To push to GitHub, do ONE of the following:

OPTION A — GitHub CLI (recommended):
    1. Install gh:  https://cli.github.com/
    2. Run:         gh auth login
    3. Re-run:      ./scripts/push_to_github.sh

OPTION B — Personal Access Token:
    1. Visit:   https://github.com/settings/tokens/new
    2. Create a token with scope: repo
    3. Run:
       export GITHUB_TOKEN=your_token_here
       ./scripts/push_to_github.sh

OPTION C — Manual push with token embedded in URL:
    git remote set-url origin https://YOUR_TOKEN@github.com/akalema-dotcom/Latex.git
    git push -u origin main
    # Then reset to remove the token from git config:
    git remote set-url origin https://github.com/akalema-dotcom/Latex.git
============================================================

EOF
exit 1
