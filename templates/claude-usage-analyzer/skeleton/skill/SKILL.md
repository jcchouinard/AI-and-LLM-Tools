---
name: claude-usage-analyzer
description: Analyze Claude Code session logs (~/.claude/projects) for $ cost per model, per project, per task and per day, turns per task, cache efficiency, subagent and tool usage, and efficiency recommendations. Generates an interactive local dashboard. Use when the user asks about Claude Code token usage or cost, which models/projects/prompts cost the most, how many turns tasks take, wants a usage chart or dashboard, or wants advice on using Claude Code more efficiently.
---

# Claude Usage Analyzer

The tool does all the analysis and builds the dashboard itself. Run it with
the right scope, then explain the results. Don't hand-build charts or a
dashboard artifact.

## Run it
```bash
python3 /path/to/project/claude_usage.py [flags]
```

Scope flags (omit for full history; the dashboard filters live):
- `--days N`, or `--since YYYY-MM-DD` / `--until YYYY-MM-DD`
- `--project .`, a path, or a substring of a project name
- `--redact` when the user wants to share the dashboard

Output flags:
- Default: terminal summary, writes `~/.claude/usage-report.html`, opens it.
- `--no-open` when you only need the numbers.
- `--json PATH` for raw per-task data. Each task has `m` = {model index:
  [cost, input, output, cache_read, write_5m, write_1h, calls]}, plus `calls`
  (turns), `sub`, `tools`, `errs`, `ctx`, `cat`.

## After running
Reply in 3 to 5 sentences: total cost and period, top model and project with
share, and the one or two most actionable findings. Point to the dashboard.
Quote dollars, not token counts. Costs are API list-price equivalents.

For "just the total", run with `--no-html` and answer in one line.
