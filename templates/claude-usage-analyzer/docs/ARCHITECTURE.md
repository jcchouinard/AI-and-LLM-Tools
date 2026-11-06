# Architecture

## Components
1. **Log discovery** (`find_session_files`): `<projects_dir>/*/*.jsonl`,
   sorted oldest first by birth time (falls back to mtime).
2. **Session parser** (`parse_session`): streams records, builds tasks.
   - `user` records that a human typed start a task (keyed by `promptId`).
   - `assistant` records are API calls, keyed by `(message.id, requestId)`;
     last record wins (dedupes per-content-block records).
   - `tool_use` blocks count tools; `tool_result` with `is_error` counts errors.
   - Metadata records: `ai-title`, `custom-title`, `pr-link`, `cost-state`.
   - Subagent files under `<session>/subagents/` are attributed by `promptId`.
   - A shared `seen` set across files bills each call once.
   - Background line: per-model gap between `cost-state.modelUsage` and parsed calls.
3. **Pricing** (`PRICES`, `rates_for`, `call_cost`): per call, applying fast
   mode, long-prompt tier, US-only multiplier, web search fee.
4. **Aggregation** (`build`): applies project and date filters, assigns stable
   indices for models (by cost), projects, sessions; emits a compact JSON:
   `meta`, `models`, `projects`, `sessions`, `tasks`.
   Each task: `s` session idx, `ts`, `dur`, `text`, `cat`, `calls`, `sub`,
   `agents`, `errs`, `ctx` peak, `tools`, `m` = {model idx: [cost, in, out,
   read, w5, w1, calls]}, `cb` context-bucket [calls, cost].
5. **Terminal report** (`print_report`): totals, per-day, monthly projection,
   by model, by project, costliest tasks, findings. ANSI color only on a TTY,
   respects `NO_COLOR`.
6. **HTML writer** (`write_html`): replaces `/*__DATA__*/null` in the
   template with the JSON payload.
7. **Dashboard** (`dashboard.html`): filters (date presets/range, project,
   model, task type, prompt search) slice the task list; every card re-renders
   from the slice. Cards: KPIs, cost per day stacked by model, by model, by
   project, turns histogram, cost by task type, cost by context size, what-if
   repricing on current models, findings, sortable task/session/tool tables,
   task detail with resume command. Light and dark mode.

## Data flow
```
~/.claude/projects/**.jsonl ─▶ parse_session ─▶ Task objects ─▶ build() JSON
                                                         ├─▶ terminal report
                                                         ├─▶ --json file
                                                         └─▶ dashboard.html (embedded) ─▶ browser filters
```
