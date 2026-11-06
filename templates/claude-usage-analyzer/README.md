# Claude Code usage analyzer: template

A template for recreating a local, zero-dependency tool that shows where
Claude Code spend goes (by model, project, task, day) with a terminal summary
and an interactive HTML dashboard.

## How to use
1. Copy this folder into a new empty project directory.
2. Open Claude Code there and say: "Read CLAUDE.md and recreate this project
   following docs/BUILD_PLAN.md."
3. Either build from scratch using the docs, or start from `skeleton/` (a
   working reference implementation) and adapt it.
4. Before trusting the numbers, update the `PRICES` table against the current
   Anthropic pricing page.

## Contents
- `CLAUDE.md`: agent instructions (purpose, stack, decisions, gotchas).
- `docs/ARCHITECTURE.md`: components and data flow.
- `docs/LEARNINGS.md`: lessons from building it.
- `docs/BUILD_PLAN.md`: ordered steps with done-checks.
- `skeleton/`: `claude_usage.py`, `dashboard.html`, an optional Claude Code
  skill (`skill/SKILL.md`) and its evals.
