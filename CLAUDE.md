# AI-and-LLM-Tools

Public repo for AI search, LLM, and AI agent tools, plus reusable Claude Code skills and project templates.

## Layout
- `skills/<name>/`: public-ready Claude Code skills (each has a `SKILL.md`). Copy a folder to `~/.claude/skills/` to install.
- `templates/<name>/`: public CLAUDE.md templates (CLAUDE.md, README.md, docs/, skeleton/) another agent can use to recreate a project.
- `ai_agents/`, `chatgpt-query-fanout-analyzer.js`: existing tools. Do not move or rename.

## Rules
- Nothing goes into `skills/` or `templates/` until it has no credentials, personal data, employer names, or internal URLs. Run `skills/share-template/scripts/scrub.py` on new templates and skim the result.
- `.gitignore` excludes `*.json` and `*.txt`. Add a negation for any JSON a template needs.
- Never use em dashes in any output. Use a comma, colon, parentheses, or separate sentences.

## Git identity
Always make git commits in this project with:

User name: jcchouinard
User email: 40404922+jcchouinard@users.noreply.github.com

Do not use any other identity (e.g. the global git config or a work email). Pass the identity explicitly on every commit, for example:

```
git -c user.name="jcchouinard" -c user.email="40404922+jcchouinard@users.noreply.github.com" commit -m "..."
```

Do not modify the global git config.

## Git workflow
- Always start new work by creating a new branch off main.
- Open a pull request to merge the work; never commit directly to main.
- Never force push to main (no --force or --force-with-lease on main).
- When asked to commit something, also push the branch and open a pull request (use `gh pr create`) unless told otherwise.
- When asked to "push", that means push the branch and open a pull request. Never push to main.
