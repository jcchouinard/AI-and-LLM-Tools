# Build plan

1. Create folder layout from CLAUDE.md. Done when: tree matches.
2. Write `scripts/scan.py` rule table (credentials, prompt injection, agent config, local leaks) and file-name rules. Done when: `python3 -I scripts/scan.py --help` runs.
3. Add PR collector: merge-base detection, per-commit patches, staged changes, commit messages. Done when: a branch with a planted token exits 1.
4. Add masking, entropy check for generic secrets, placeholder filter, hidden-unicode check, ignore and denylist files, allow marker reporting. Done when: decoys produce no HIGH.
5. Write `tests/selftest.py` (plants and decoys in a temp git repo, fake secrets built at runtime). Done when: all pass.
6. Write `scripts/repo_scan.py`: `--estimate`, tiers, hard ceilings, risk-ordered scan, review queue, exit codes 0 to 4. Done when: `repo_selftest.py` passes and a 25,000-file tree estimates in a couple of seconds.
7. Write `scripts/pre_pr_hook.py` and register it as a PreToolUse hook for Bash in user settings. Done when: a staged fake token blocks `git push` and a clean push passes.
8. Write `SKILL.md` with frontmatter, both modes, verdict format, fixing guidance, tuning rules. Done when: the skill is listed in a new session.
9. Add `templates/` and symlink to `~/.claude/skills/pr-gate`. Done when: `/pr-gate` runs in any repo.
10. Run a repo audit on an existing repo and tune `.pr-gate-ignore`. Done when: only real findings remain.
