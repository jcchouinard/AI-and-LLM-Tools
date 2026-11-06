# Build plan

1. **Inspect real logs.** Open a few `~/.claude/projects/*/*.jsonl` files and
   list record types and `usage` fields.
   Done when: you can name the fields for input, output, cache read, 5m and 1h
   writes, and have found `cost-state`, `ai-title`, and subagent folders.
2. **Pricing table.** Write `PRICES` from the live pricing page, plus fast
   mode, long-prompt tiers, US-only multiplier, web search fee, and a checked date.
   Done when: `call_cost` returns a value for every Claude model in your logs.
3. **Parser with dedupe.** Implement `parse_session` keyed by
   `(message.id, requestId)`, human-prompt detection, tool and error counts.
   Done when: call count equals unique message ids, not record count.
4. **Subagents and forks.** Attribute subagent files by `promptId`; add a
   shared `seen` set across files sorted oldest first.
   Done when: no call id is billed in two sessions.
5. **Calibrate.** Compare per-session totals with `cost-state.totalCostUSD`.
   Done when: aggregate gap is well under 1% and outliers are explained.
6. **Background line.** Book per-model remaining tracker cost as a separate task.
   Done when: totals reconcile and no real task is inflated.
7. **Aggregation and filters.** `build()` with `--days/--since/--until/--project/--redact`.
   Done when: `--project .` and date filters change totals as expected and
   `--json -` prints valid JSON.
8. **Terminal report.** Totals, by model, by project, costliest tasks, findings.
   Done when: output fits 80 columns and is readable without color.
9. **Dashboard.** Template with `/*__DATA__*/null`, client-side filters, cards
   listed in ARCHITECTURE.md, light/dark, accessible palette.
   Done when: every card updates on every filter and task rows expand.
10. **Edge cases.** Missing dir, no sessions, no matching activity, corrupt
    lines, Windows-safe dates.
    Done when: each exits with a clear one-line message.
11. **Skill (optional).** Thin `SKILL.md` that runs the script and replies in
    3 to 5 sentences with dollar figures, plus `evals/evals.json`.
    Done when: evals pass.
12. **README.** One command at the top, options, how numbers are computed.
