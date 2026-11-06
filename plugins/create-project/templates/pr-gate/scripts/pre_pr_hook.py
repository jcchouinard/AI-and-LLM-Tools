#!/usr/bin/env python3
"""Claude Code PreToolUse hook: hard gate on `gh pr create` and `git push`.

Runs scan.py in the command's working directory. HIGH findings block the tool
call (exit 2, report goes back to Claude). Everything else passes untouched.
There is deliberately no agent-settable bypass: a human who has reviewed the
findings can run the command themselves (`! gh pr create ...`).
"""
import json
import os
import re
import subprocess
import sys

GATED = re.compile(r"\bgh\s+pr\s+create\b|\bgit\b(?:\s+-[Cc]\s+\S+)*\s+push\b")
SCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan.py")


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not GATED.search(cmd):
        return 0
    cwd = data.get("cwd") or os.getcwd()
    m = re.search(r"\bgit\s+-C\s+(\S+)", cmd) or re.match(r"\s*cd\s+(\S+)\s*&&", cmd)
    if m:
        cwd = os.path.join(cwd, os.path.expanduser(m.group(1).strip("'\"")))
    r = subprocess.run([sys.executable, "-I", SCAN], cwd=cwd, capture_output=True, text=True)
    if r.returncode == 1:
        print("pr-gate BLOCKED this push/PR. Fix the HIGH findings below (rotate any real credential, "
              "rewrite branch history if it was committed), then run /pr-gate.\n\n" + r.stdout, file=sys.stderr)
        return 2
    if r.returncode == 2:
        print("pr-gate could not scan (not a git repo?): " + r.stderr.strip(), file=sys.stderr)
        return 0  # fail open on tooling errors outside a repo; the skill still applies
    return 0


if __name__ == "__main__":
    sys.exit(main())
