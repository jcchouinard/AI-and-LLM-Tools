# System Design Explainer: agent template

A template for recreating a Claude Code skill that converts a codebase into a visual technical design, in an internal version (Confluence-ready) and a public version (anonymized, leak-scanned, with an interactive architecture explorer).

## How to use
1. Copy this folder into a new empty project, or just point an agent at it.
2. Tell Claude: "Read CLAUDE.md, then follow docs/BUILD_PLAN.md to recreate this skill."
3. The `skeleton/` folder contains a working copy of every file. You can install it directly:
   `cp -r skeleton ~/.claude/skills/system-design-explainer`
4. Test: `python3 scripts/render.py examples/example.json --mode public --out /tmp/out`

## Files
- `CLAUDE.md`: purpose, conventions, decisions, gotchas, do and don't.
- `docs/ARCHITECTURE.md`: components and data flow.
- `docs/LEARNINGS.md`: mistakes made and fixes, so you do not repeat them.
- `docs/BUILD_PLAN.md`: ordered build steps with a done-check for each.
- `skeleton/`: the skill's files.

## Renamed files

## Before you publish
Skim every file. The archive was scrubbed automatically and reviewed by hand, but no scrub is a guarantee.
