# lean-start

Start a Claude Code project with everything switched off except what you need. One command, at most three questions, and a new Terminal window opens with Claude running in the project.

- **Low token by default:** no MCP servers, no plugins, no skills, only five built-in tools, Sonnet at medium effort, Haiku subagents. About 75% less context on every request than a default setup.
- **Right account:** commits and pushes go out as the identity you pick (personal or work), without touching your global git config.
- **token-gate:** whole reads of files over 350 lines are blocked and sent to a cheap Haiku subagent.
- **Adversarial review (optional):** pr-gate blocks `git push` and `gh pr create` when the branch would publish secrets, prompt injection, hidden unicode or risky files.
- **Lockdown (optional):** the agent is confined to the folder and an allowlist of commands, inside the OS sandbox with no network, with an audit log.

## Install
In Claude Code (2.1.275 or later):
```
/plugin install lean-start --marketplace jcchouinard/AI-and-LLM-Tools
```
Or in two steps: `/plugin marketplace add jcchouinard/AI-and-LLM-Tools`, then `/plugin install lean-start@ai-and-llm-tools`.

Without the plugin system:
```bash
git clone --depth 1 https://github.com/jcchouinard/AI-and-LLM-Tools
AI-and-LLM-Tools/plugins/lean-start/install.sh      # adds /lean-start, touches nothing else
```
Requirements: Python 3.9+, git (modes 2 to 4), gh (only to create GitHub repos). Linux mode 4 also needs `bubblewrap` and `socat`. macOS and Linux; Windows through WSL2.

## Use
```
/lean-start:new my-app                 # plugin install (clone install: /lean-start my-app)
/lean-start:new my-app 2 "Price tracker for my shop"
```
The first run detects your git and GitHub accounts and asks which to save. Then it asks the mode, the account and whether to create a GitHub repo, creates `./my-app`, and opens it in a new Terminal window. Reopen it any time with `my-app/.claude/start.command` (`-c` to continue the last session).

Change defaults with `/lean-start:new --setup`, for example a projects folder so bare names go to `~/projects/<name>` instead of the current folder.

## Modes
| | 1. Low token | 2. Low token + git + review | 3. Balanced (pick) | 4. Locked down |
|---|---|---|---|---|
| Context on the first request* | 8,454 | 11,642 | 16,121 (playwright picked) | 11,497 |
| MCP servers | none | none | only the ones you pick | none |
| Plugins, claude.ai connectors | off | off | only the ones you pick | off |
| Skills | none | pr-gate only | pr-gate + picked plugins | none |
| Built-in tools | Bash, Read, Edit, Write, Agent | same + Skill | default set, Web and Workflow if picked | Bash, Read, Edit, Write, Agent |
| Git, account, branch and PR rules | no | yes | yes | yes, push and PR blocked |
| token-gate | yes | yes | yes | yes |
| pr-gate | no | yes | yes | yes |
| Folder and command lockdown, sandbox, audit log | no | no | no | yes |

*Measured 2026-11-06 with "reply ok" on Sonnet. A default setup with typical plugins and MCP servers was 34,668. That overhead is sent on every turn (mostly at the cached rate), so the saving repeats all session. Measure your own with `/context`.

## What a project gets
```
.claude/settings.json      mode settings, merged into any existing file (your values win)
.claude/start.command      launches claude with the mode's flags
.claude/hooks/             token_gate.py, and lockdown.py + audit.py in mode 4
.claude/agents/            file-summarizer (Haiku)
.claude/skills/pr-gate/    modes 2 to 4
.claude/lockdown.json      mode 4 command allowlist, edit it to allow more
.claude/mcp.local.json     mode 3 picked servers (gitignored: server configs can hold API keys)
.claude/lean-start.json    manifest of written files, used by doctor and uninstall
CLAUDE.md, .gitignore
```
Nothing is overwritten silently: existing files are merged or backed up as `.bak`, an existing `CLAUDE.md` is left alone (a `CLAUDE.lean-start.md` is written next to it), and the first commit contains only lean-start's files.

## How the account is enforced
- `git config --local user.name/email` in the new repo.
- The remote URL contains the GitHub login (`https://<login>@github.com/...`), so gh's credential helper pushes as that account even when another one is active.
- `CLAUDE.md` tells Claude to run `GH_TOKEN=$(gh auth token -u <login>) gh ...` instead of `gh auth switch`, which would change global state.

## Mode 4, honestly
Layers: the OS sandbox (no network, writes only in the folder), `dontAsk` permissions with deny rules, a hook that blocks any file access outside the folder (symlinks resolved), a hook that only runs allowlisted commands (no `$(...)`, no `bash -c`, no `python -c`, no paths outside the folder), and an audit log of every call and every block in `.claude/audit.jsonl`. Tested against 60+ escape attempts (`tests/test_lockdown.py`).

Limits: a script the agent writes and then runs with an allowed interpreter can do anything the sandbox allows. The person at the keyboard can edit the project settings. Enforcement a user cannot undo needs managed settings deployed by an admin (`allowManagedHooksOnly`), see the Claude Code docs. Accept the folder trust prompt on first launch: until then the allow rules are ignored and mode 4 allows nothing.

## Commands
```
python3 -I <plugin>/scripts/lean_start.py doctor [dir]      check a project
python3 -I <plugin>/scripts/lean_start.py uninstall [dir]   remove lean-start files (keeps CLAUDE.md, .gitignore, settings unless --all)
python3 -I <plugin>/scripts/lean_start.py new my-app --mode 1 --dry-run
```
Config lives in `~/.config/lean-start/config.json` (identities, projects root, extra CLAUDE.md rules such as `--extra-rule "No em dashes."`).

## Tests
```
python3 tests/test_scaffold.py && python3 tests/test_lockdown.py && python3 tests/test_token_gate.py
python3 templates/pr-gate/tests/selftest.py && python3 templates/pr-gate/tests/repo_selftest.py
```

## Credits
token-gate is a Python port of [token-gate-tutorial](https://github.com/jcchouinard/token-gate-tutorial), inspired by [spotify/portal-ai-plugins shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0). MIT licensed.
