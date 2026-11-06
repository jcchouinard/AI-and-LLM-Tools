#!/bin/bash
# Remove what install.sh added. Keeps your config (~/.config/create-project) and every project you created.
set -euo pipefail
rm -rf "$HOME/.claude/create-project" "$HOME/.claude/skills/create-project"
echo "Removed. Config kept at ${XDG_CONFIG_HOME:-$HOME/.config}/create-project (delete it by hand if you want)."
