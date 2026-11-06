#!/bin/bash
# Install create-project without the plugin system: copies it to ~/.claude/create-project and adds the
# /create-project skill to ~/.claude/skills. Touches nothing else (no shell config). Safe to re-run.
set -euo pipefail
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v git >/dev/null || echo "note: git not found, modes 2 to 4 need it"
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/create-project"
SKILL="$HOME/.claude/skills/create-project"
[ "$SRC" = "$DEST" ] && { echo "Run install.sh from the cloned repo, not from $DEST"; exit 1; }
rm -rf "$DEST.new" && mkdir -p "$DEST.new"
cp -R "$SRC/scripts" "$SRC/templates" "$SRC/skills" "$DEST.new/"
rm -rf "$DEST" && mv "$DEST.new" "$DEST"
mkdir -p "$SKILL"
sed -e "s|\${CLAUDE_PLUGIN_ROOT}|$DEST|g" -e 's/^name: new$/name: create-project/' "$DEST/skills/new/SKILL.md" > "$SKILL/SKILL.md"
echo "Installed. In Claude Code run: /create-project my-app"
