# Learnings

## Mistakes in the first version (all verified against real logs)
- **Double counting.** Over half of assistant records were duplicates (one
  record per content block, each repeating usage). Fix: dedupe by
  `(message.id, requestId)`.
- **Missing model prices.** Newer models were absent from the price table, so
  most spend showed as "unknown cost". Fix: full table, list unpriced models
  explicitly.
- **Wrong cache write rate.** Everything priced at 1.25x, but almost all
  writes were 1-hour writes at 2x. Fix: use the 5m/1h split per call.
- **Wrong cache read rate.** Assumed 0.1x everywhere; several models use a
  different multiplier or a flat rate.
- **Subagents ignored.** Their logs are in a separate folder.
- **Forks billed twice.** Forked sessions copy parent calls. Fix: global
  dedupe, oldest file first.

## What worked
- Calibrating against Claude Code's own `cost-state` record per session. Look
  at the error distribution (p10, median), then chase outlier sessions one by
  one. Final match was within about 0.01%.
- Checking the live pricing page instead of a cached reference table: a cached
  table had one model's cache read rate wrong.
- Booking unexplained tracker cost as a visible "Background calls" line.
- Pre-filtering bulky `"api-request` lines before JSON parse: a few hundred MB
  of logs processes in about a second.
- Making the skill a thin wrapper that runs the script and summarizes, instead
  of having the model build charts each time (far cheaper per invocation).
- Testing the dashboard in a real browser (row expansion, tooltips) and CLI
  edge cases (empty filters, missing dir) before calling it done.

## Insights the tool surfaced that are worth keeping as findings
- A large share of spend can come from calls carrying 200K+ tokens of context;
  suggest `/clear` between unrelated tasks.
- A small fraction of tasks typically drives a big share of cost.
- The same tokens re-priced on another model can be notably cheaper or
  pricier; show a what-if table.

## Gotchas
- `%-d` date formatting breaks on Windows.
- Check where the git root is before committing; a parent folder may be the
  repo.
