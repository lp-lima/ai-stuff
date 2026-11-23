#!/bin/bash
set -e

REPO_DIR="/mnt/c/Users/lplim/repos/ai-stuff"
AGY_DIR="$REPO_DIR/agy"
GEMINI_DIR="$HOME/.gemini"

mkdir -p "$AGY_DIR/skills"
mkdir -p "$AGY_DIR/config"
mkdir -p "$AGY_DIR/antigravity-cli"

echo "Syncing skills..."
rsync -a --delete --delete-excluded \
  --exclude 'venv' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'credentials.json' \
  --exclude '*secret*.json' \
  --exclude '*token*.json' \
  --exclude '*.env' \
  --exclude '*.pem' \
  --exclude '*.key' \
  --exclude 'classified_data.json' \
  "$GEMINI_DIR/skills/" "$AGY_DIR/skills/"

echo "Syncing config..."
rsync -a --delete --delete-excluded \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'credentials.json' \
  --exclude '*secret*.json' \
  --exclude '*token*.json' \
  --exclude '*.env' \
  --exclude '*.pem' \
  --exclude '*.key' \
  "$GEMINI_DIR/config/" "$AGY_DIR/config/"

echo "Syncing permissions and settings..."
if [ -f "$GEMINI_DIR/settings.json" ]; then
  cp "$GEMINI_DIR/settings.json" "$AGY_DIR/"
fi
if [ -f "$GEMINI_DIR/antigravity-cli/settings.json" ]; then
  cp "$GEMINI_DIR/antigravity-cli/settings.json" "$AGY_DIR/antigravity-cli/settings.json"
fi
if [ -f "$GEMINI_DIR/trustedFolders.json" ]; then
  cp "$GEMINI_DIR/trustedFolders.json" "$AGY_DIR/"
fi

cd "$REPO_DIR"
git add .
if git diff --staged --quiet; then
  echo "No changes to commit."
else
  if ! gpg-connect-agent 'keyinfo --list' /bye 2>/dev/null | awk '$7 == "1" {found=1} END {exit !found}'; then
    echo "Error: GPG key is not unlocked in gpg-agent. Unlock it first before committing."
    exit 1
  fi
  git commit -S -m "Sync skills, permissions and configs"
  git push -u origin main
  echo "Changes committed and pushed."
fi
