#!/usr/bin/env python3
"""PreToolUse hook: block whole reads of big files, point Claude to grep, a slice, or file-summarizer.

Read: blocked when no offset/limit and the file is over MIN_LINES lines.
Bash: blocked for a bare `cat|head|tail|less|more <big file>` (pipes and redirects pass).
Exit 0 = allow, exit 2 = block (stderr goes back to Claude). Any internal error allows.
Python port of token-gate (github.com/jcchouinard/token-gate-tutorial), inspired by
spotify/portal-ai-plugins shunt (Apache-2.0).
"""
import json
import os
import re
import shlex
import sys

PAGERS = {"cat", "head", "tail", "less", "more"}


def threshold():
    v = os.environ.get("MIN_LINES", "350")
    return int(v) if v.isdigit() else 350


def count_lines(path, limit):
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
            if n > limit:
                break
    return n


def big(path, cwd, limit):
    p = path if os.path.isabs(path) else os.path.join(cwd, path)
    if not os.path.isfile(p):
        return 0
    n = count_lines(p, limit)
    return n if n > limit else 0


def main():
    data = json.load(sys.stdin)
    tool, ti, cwd = data.get("tool_name", ""), data.get("tool_input") or {}, data.get("cwd") or os.getcwd()
    limit = threshold()
    if tool == "Read":
        if ti.get("offset") is not None or ti.get("limit") is not None:
            return 0
        n = big(ti.get("file_path") or "", cwd, limit)
        if n:
            print(f"File has over {limit} lines. Do not read it whole. Grep for the section you need and "
                  "re-read with offset/limit, or delegate to the file-summarizer subagent.", file=sys.stderr)
            return 2
    elif tool == "Bash":
        cmd = ti.get("command") or ""
        if re.search(r"[|<>;&`$]", cmd):
            return 0
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return 0
        if not parts or parts[0] not in PAGERS:
            return 0
        for arg in parts[1:]:
            if not arg.startswith("-") and big(arg, cwd, limit):
                print(f"File has over {limit} lines. Use grep, Read with offset/limit, or the "
                      "file-summarizer subagent instead of " + parts[0] + ".", file=sys.stderr)
                return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # never break the session because of the gate itself
        sys.exit(0)
