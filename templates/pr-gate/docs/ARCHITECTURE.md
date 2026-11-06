# Architecture

## Components
- Rule engine (`scan.py`): table of regex rules, file-name rules, entropy check, hidden-unicode check, denylist loader.
- PR collector (`scan.py`): finds merge-base with main or master, lists commits, gets each commit patch, parses added lines with file and line number, also scans staged changes and commit messages.
- Repo auditor (`repo_scan.py`): imports the rule engine, lists files (`git ls-files` or depth-limited walk), estimates, then scans in risk order under hard budgets and emits a capped review queue.
- Hook (`pre_pr_hook.py`): reads the tool call JSON on stdin, matches `gh pr create` and `git push`, runs `scan.py` in the command's directory, exits 2 on HIGH.
- Skill (`SKILL.md`): tells the agent when to run which script, how to read results, and the exact verdict format.

## Data flow
PR mode: git history -> per-commit added lines -> rules -> findings (HIGH/WARN) -> exit code -> agent adversarial read of the diff -> verdict.

Audit mode: file list -> estimate and tier -> (small/medium) bounded scan in risk order -> findings + review queue -> agent reads queue only -> verdict (PASS, BLOCK or INCOMPLETE).

## Size tiers (audit)
small (<= 2,000 files, <= 50 MB): scan. medium (<= 20,000 files, <= 300 MB): scan, ask before raising limits. large (<= 100,000 files): ask user for `--path`. huge: refuse.
