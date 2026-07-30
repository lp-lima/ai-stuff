#!/bin/bash
set -e

REPO_DIR="/mnt/c/Users/lplim/repos/ai-stuff"
AGY_DIR="$REPO_DIR/agy"
GEMINI_DIR="$HOME/.gemini"

mkdir -p "$AGY_DIR/skills"
mkdir -p "$AGY_DIR/config"

echo "Syncing skills..."
rsync -a --exclude 'venv' --exclude '.venv' --exclude '__pycache__' "$GEMINI_DIR/skills/" "$AGY_DIR/skills/"

echo "Syncing config..."
cp -r "$GEMINI_DIR/config/"* "$AGY_DIR/config/"

echo "Syncing permissions and settings..."
if [ -f "$GEMINI_DIR/settings.json" ]; then
  cp "$GEMINI_DIR/settings.json" "$AGY_DIR/"
fi
if [ -f "$GEMINI_DIR/trustedFolders.json" ]; then
  cp "$GEMINI_DIR/trustedFolders.json" "$AGY_DIR/"
fi

cd "$REPO_DIR"
git add .
if git diff --staged --quiet; then
  echo "No changes to commit."
else
  git commit -m "Sync skills, permissions and configs"
  git push -u origin main
  echo "Changes committed and pushed."
fi
