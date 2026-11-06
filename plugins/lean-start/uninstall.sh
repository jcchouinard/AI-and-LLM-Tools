#!/bin/bash
# Remove what install.sh added. Keeps your config (~/.config/lean-start) and every project you created.
set -euo pipefail
rm -rf "$HOME/.claude/lean-start" "$HOME/.claude/skills/lean-start"
echo "Removed. Config kept at ${XDG_CONFIG_HOME:-$HOME/.config}/lean-start (delete it by hand if you want)."
