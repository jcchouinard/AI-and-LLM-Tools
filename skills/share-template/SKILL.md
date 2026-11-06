---
name: share-template
description: Turn a project directory and its Claude Code conversation history into a public, PII-free template zip (CLAUDE.md plus supporting md files) that another Claude agent can use to recreate a similar project. Use when the user asks to share, publish, templatize, or export a project's learnings as a template or zip.
---

# share-template

Build a shareable template from a project's conversations and files, with all personal data removed.

Argument: optional project directory (default: current working directory).

## Steps

### 1. Scope (one short question, only if unclear)
Confirm: project directory, template name, and any extra terms to redact (real names, company, internal domains, product or customer names). Do not ask more than this.

### 2. Gather sources
- Project files: read the directory structure, README, config, key source files. Ignore `.git`, `node_modules`, `.env*`, build output.
- Conversations: session logs live in `~/.claude/projects/<path-with-slashes-as-dashes>/*.jsonl`. Find the folder for the project path. Skim user messages and assistant conclusions to extract: goals, architecture decisions and why, conventions, gotchas and bugs hit, commands that worked, things to avoid, workflow that worked.
- Project memory in `~/.claude/projects/<folder>/memory/*.md` if present.
- Do not copy transcripts. Distill them. Never quote raw conversation text verbatim when it may hold personal data.

### 3. Write the template into a fresh staging dir
Use `mktemp -d` for staging, outside the project and outside `~/.claude`. Generate:

- `CLAUDE.md`: the main file. Sections: Project purpose, Tech stack, Directory layout, Commands (build/test/run), Conventions, Architecture decisions (with why), Known gotchas, Do and Don't, How to start (first steps for a new agent).
- `README.md`: what the template is, how to use it (copy into a new project, tell Claude to read CLAUDE.md and recreate).
- `docs/ARCHITECTURE.md`: components and data flow, if the project warrants it.
- `docs/LEARNINGS.md`: distilled lessons from the conversations (mistakes, fixes, what worked).
- `docs/BUILD_PLAN.md`: ordered steps another agent should follow to recreate the project from scratch, each with a done-check.
- `skeleton/`: optional stripped starter files (config, scaffolding, `.env.example` with placeholder keys only). Include only what helps recreation, no real data.

Write generically: use placeholders like `<PROJECT_NAME>`, `<YOUR_DOMAIN>`, `<API_KEY>`, `/path/to/project`. Keep the instructions addressed to an agent ("Do X", "Check Y"). Keep each file focused and short.

### 4. Scrub, verify, zip
```bash
python3 -I ~/.claude/skills/share-template/scripts/scrub.py <STAGING_DIR> <OUTPUT_ZIP> --term "Real Name" --term "company.com"
```
The script redacts emails, home paths, API keys, tokens, JWTs, private keys, URL credentials, IPs, phone numbers, plus auto-detected OS username, git name/email, and hostname and every `--term`. It then re-verifies and refuses to write the zip if anything remains. Default output: `~/Desktop/<template-name>-template.zip`.

The share target only accepts these extensions: .md, .mdx, .markdown, .txt, .json, .jsonc, .yaml, .yml, .toml, .csv, .tsv, .mdc, .ini, .sh, .bash, .py, .js, .mjs, .ts, .png, .jpg, .jpeg, .gif, .webp. The script automatically appends `.txt` to any other text file (for example `index.html` becomes `index.html.txt`) and adds a `RENAMED_FILES.md` to the zip listing the originals. In the generated README, tell the agent to strip the `.txt` suffix when recreating those files.

If it fails, fix the listed files (rewrite the passage generically), then rerun.

### 5. Manual review gate (required)
Before telling the user it is safe, read through every file in the staging dir once for what regex cannot catch: people's names, employer or client names, internal URLs and hostnames, ticket IDs, business-sensitive numbers, unreleased product details. Fix and rerun the script. Then report:
- zip path and file list
- what categories were redacted
- anything you were unsure about and removed

Never claim the zip is guaranteed free of personal data. Tell the user to skim it before publishing.

## Rules
- Never include `.env`, credentials, session logs, raw transcripts, or memory files verbatim.
- Do not upload or publish the zip. Only create it locally.
- Do not use em dashes in generated files (user preference).
