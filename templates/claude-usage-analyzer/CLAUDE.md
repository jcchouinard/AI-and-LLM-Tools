# <PROJECT_NAME>: Claude Code usage and cost analyzer

## Project purpose
A zero-setup tool that reads the session logs Claude Code already writes to
`~/.claude/projects` and shows exactly where the money goes: cost by model,
project, task, and day, turns per task, cache efficiency, subagent and tool
usage, plus plain-language findings. One command prints a terminal summary
and opens a self-contained interactive HTML dashboard. Nothing leaves the
machine.

Goal for the experience: an engineer who uses Claude Code daily runs one
command and is surprised by how complete and easy the analysis is.

## Tech stack
- Python 3.8+, standard library only (no pip installs, no venv, no API key).
- One HTML template with vanilla JS and hand-drawn SVG charts (no chart
  library, no CDN). Data is embedded into the HTML at build time.
- Optional: a Claude Code skill (`SKILL.md`) that runs the tool and summarizes
  the result.

## Directory layout
```
claude_usage.py     # parser, pricing, aggregation, terminal report, HTML writer
dashboard.html      # template; contains the literal placeholder /*__DATA__*/null
README.md           # user-facing usage doc
evals/evals.json    # skill evals (prompt, expected output, assertions)
legacy/             # previous version kept for reference (optional)
```

## Commands
```bash
python3 claude_usage.py                      # all history, opens dashboard
python3 claude_usage.py --days 7
python3 claude_usage.py --since 2026-01-01 --until 2026-01-31
python3 claude_usage.py --project .          # current folder (path prefix match)
python3 claude_usage.py --project my-repo    # substring of project path
python3 claude_usage.py --redact             # hide prompt text and titles
python3 claude_usage.py --no-html            # terminal only
python3 claude_usage.py --json usage.json    # raw data ('-' = stdout)
python3 claude_usage.py --out report.html --no-open
python3 claude_usage.py --dir /path/to/projects   # also honors CLAUDE_CONFIG_DIR
```
Default dashboard path: `~/.claude/usage-report.html`.

There is no test suite. Verify by running the tool against real logs and
reconciling against Claude Code's own `cost-state` records (see Known gotchas).

## Conventions
- Report dollars, never raw token totals as a proxy for cost.
- Costs are API list-price equivalents. Say so; flat-plan users pay differently.
- A **task** = one human-typed prompt plus every API call (turn), tool call,
  and subagent it caused.
- Keep the tool to one Python file plus one HTML template.
- Plain language in UI copy and findings, with real numbers.
- Colorblind-safe neutral palette with stable per-model color slots (ordered
  by total cost). No brand palette.
- Use `f"{dt:%b} {dt.day}"`, not `%-d` (breaks on Windows).

## Architecture decisions (with why)
- **Price every API call individually** with its own model and token split
  (input, output, cache read, 5m write, 1h write). Aggregate pricing is wrong
  because write mixes and models vary per call.
- **Pricing table lives at the top of the script** (`PRICES`, plus
  `LONG_PROMPT_TIER`, `FAST_MODE`, US-only multiplier, web search fee) with a
  "last checked" date. Easy to update; check against the live pricing page,
  not cached references.
- **Global dedupe across files, oldest file first.** Forked/continued sessions
  copy parent messages; the original session keeps ownership.
- **Background calls as their own line.** Some calls (titles, away recaps,
  compaction) never get a transcript record but appear in Claude Code's
  tracker. Book the per-model difference as a separate "Background" task so
  totals reconcile without inflating real tasks.
- **Deterministic keyword classifier** for task type (build, fix, tweak,
  refactor, git, review, docs, research, question, follow-up, slash command).
  No ML dependency. Earliest-matching intent wins.
- **All filtering in the dashboard is client-side** over the full embedded
  dataset, so the default run needs no flags.
- **The skill runs the tool; it does not hand-build charts.** Having Claude
  build a dashboard on every call was the expensive part.

## Known gotchas
- Claude Code writes **one transcript record per content block**, each
  repeating the call's `usage`. Key calls by `(message.id, requestId)` and let
  the last record win. Counting records roughly doubles totals.
- Subagent logs live in `<session>/subagents/*.jsonl` with a sibling
  `.meta.json` (`agentType`). Attribute them to the parent task via `promptId`.
- Skip `model == "<synthetic>"` records.
- Skip records starting with `"api-request` cheaply before JSON parsing; they
  are bulky.
- Cache writes: `usage.cache_creation.ephemeral_5m_input_tokens` and
  `ephemeral_1h_input_tokens`. Older logs lack the split; treat as 5m. Claude
  Code mostly uses 1h writes (2x input), not 1.25x.
- Cache read multipliers differ by model (some at 0.05x, some flat rates).
  Verify each against the live pricing page.
- `cost-state` records hold Claude Code's own totals (`totalCostUSD`,
  `modelUsage`). It carries a parent's cost into a fork, so compare like for
  like (include copied calls). Use it to calibrate, target well under 1% gap.
- Filter out synthetic user records: `isMeta`, `isCompactSummary`,
  `isSidechain`, `<local-command-`, injected system-reminder blocks, interrupts, hook
  output, tool results, continuation summaries. Slash commands come from
  `<command-name>` tags.
- Escape `</` in the embedded JSON payload.
- Never let one corrupt log kill the report: catch per file, list warnings.
- Non-Anthropic models: list them, do not price them.

## Do
- Calibrate against `cost-state` before trusting any number.
- Show findings that update with filters.
- Provide a `claude --resume <session-id>` command in task detail.
- Offer `--redact` for sharing.

## Don't
- Don't add third-party dependencies.
- Don't trust cached price tables; check the live page.
- Don't hide unexplained cost; surface it as a labeled line.
- Don't delete the old version when rewriting; move it to `legacy/`.

## How to start
1. Read `docs/ARCHITECTURE.md`, then `docs/LEARNINGS.md`.
2. Follow `docs/BUILD_PLAN.md` step by step, checking each done-check.
3. `skeleton/` holds a working reference implementation. Refresh `PRICES`
   against the live pricing page before use.
