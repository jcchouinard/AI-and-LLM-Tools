# adversarial-reviewer template

A recipe for building a lightweight adversarial safety gate (credentials, prompt injection, hidden unicode, risky files, PII) that runs before any PR or push, as a Claude Code skill.

## How to use
1. Copy this folder into a new project directory.
2. Tell Claude: "Read CLAUDE.md, then follow docs/BUILD_PLAN.md to recreate the skill."
3. Files in `skeleton/` that end in `.txt` had their original extension hidden for sharing. Strip the `.txt` suffix when recreating them.

## Contents
- `CLAUDE.md` main instructions for the agent
- `docs/ARCHITECTURE.md` components and data flow
- `docs/LEARNINGS.md` lessons from the original build
- `docs/BUILD_PLAN.md` ordered steps with done-checks
- `skeleton/` starter config files

## Skeleton renames
`skeleton/pr-gate-ignore.txt` becomes `.pr-gate-ignore` and `skeleton/gitignore-secrets.txt` becomes `.gitignore-secrets` (append its lines to the project `.gitignore`).
