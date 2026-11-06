---
name: new
description: Create a new Claude Code project with everything switched off except what its mode allows (low token, git and adversarial review, balanced picks, or locked down), then launch it.
disable-model-invocation: true
argument-hint: "<name or path> [1|2|3|4] [one-line purpose]"
---

# lean-start

The script does all the work. Do not read the templates or scripts, and do not explain them. Keep your own messages to one or two lines.

`LS` below means: `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/lean_start.py"`

## 1. Arguments
- First argument: project name or path. A bare name becomes `./<name>`, or `<projects root>/<name>` if the user set one. Missing: ask "Project name?" in plain text.
- A digit 1 to 4 anywhere in the arguments: the mode (also accept `light` = 1, `git` = 2, `balanced` = 3, `locked` = 4). Remaining words: the purpose.
- `--setup` instead of a name: run step 2 even if already configured, also ask for an optional projects root (`LS setup --projects-root <path|none>`), then stop.

## 2. First run only
Run `LS setup --detect`. If `configured.identities` is empty and the mode is not 1 (or unknown): one AskUserQuestion, multiSelect, header "Accounts": one option per `gh_accounts` entry (label the login, description its `noreply` address) plus one for `git_global` if its email is not already listed. Save each pick:
`LS setup --add-identity <short key> --label "<login>" --git-name "<login or git name>" --git-email "<noreply or git email>" --gh-user "<login or empty>"`
No gh and no git identity: ask for a name and email in plain text.

## 3. Questions (one AskUserQuestion call, skip any already answered)
1. **Mode** (header "Mode"):
   - "1. Low token, no git": smallest context, no MCP, no plugins, no skills, Sonnet medium.
   - "2. Low token + git + review": mode 1 plus branch/PR rules, right account, pr-gate before every push.
   - "3. Balanced (pick)": you choose which MCP servers, plugins and extras to enable.
   - "4. Locked down": confined to the folder, allowlisted commands only, sandbox with no network, audit log.
2. **Account** (header "Account"): one option per identity in `configured.identities` (label), plus "Local only". Ignored for mode 1.
3. **GitHub repo** (header "Remote"): "None for now (Recommended)", "Create private repo and push", "Create public repo and push". Ignored for modes 1 and 4 and for Local only.

## 4. Mode 3 only
Run `LS inventory`. One AskUserQuestion call with up to two multiSelect questions:
- header "Servers": one option per entry in `groups` (label, description `names`). Skip if there are no groups.
- header "Extras": the three `extras`.
Picked group = all its `items`. Join picked items and extra keys with commas for `--enable`.

## 5. Run
`LS new "<name>" --mode <n> --identity <key|none> --remote <none|private|public> [--enable <list>] --purpose "<text>"`
- Picking "Create ... repo" is the user's confirmation to create and push.
- Exit 1 with "already has files": ask once whether to merge, then re-run with `--existing-ok`.
- Exit 2: show the error and stop. Never retry with different flags without asking.

## 6. Launch
Show the script's output lines as-is. On macOS run `open "<project>/.claude/start.command"` (new Terminal window). Elsewhere tell the user to run `<project>/.claude/start.command`. Then say, in one line each:
- the new window is the project session, this one has none of its savings, so continue there;
- accept the folder trust prompt on first launch (mode 4 allows nothing until the folder is trusted);
- `.claude/start.command -c` resumes, `LS doctor <project>` checks the setup.
