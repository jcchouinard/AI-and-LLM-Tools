#!/usr/bin/env python3
"""Mode 4 PreToolUse hook: keep the agent inside the project folder and on an allowlist of commands.

- File tools: the resolved real path (symlinks followed) must be inside the project.
  Edit/Write on .claude/ or CLAUDE.md is blocked, so the agent cannot weaken its own guardrails.
- Bash: every command in the line must start with an allowed program (.claude/lockdown.json),
  with no command substitution, no interpreter one-liners, no dangerous flags, and every
  path-looking argument inside the project.
Exit 0 = allow, 2 = block. Fails CLOSED: any parsing doubt blocks.
"""
import json
import os
import shlex
import sys

FILE_KEYS = ("file_path", "notebook_path", "path")
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n"}
REDIRECTS = {">", ">>", "<", "<<", ">&", "&>", "<>", ">|"}
INTERPRETER_FLAGS = {"python": {"-c", "-m"}, "python3": {"-c", "-m"}, "node": {"-e", "-p", "--eval"},
                     "ruby": {"-e"}, "perl": {"-e", "-E"}}
BAD_FLAGS = {"find": {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint"},
             "sed": {"-i", "--in-place"}, "git": {"-c", "--exec-path", "--git-dir", "--work-tree"}}
DEFAULT_ALLOW = ["ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "find", "sed", "sort", "uniq",
                 "cut", "tr", "diff", "echo", "mkdir", "touch", "python3", "pytest", "node",
                 "npm test", "npm run", "git status", "git diff", "git log", "git show", "git add",
                 "git commit", "git switch", "git branch", "git restore", "git stash"]


AUDIT = {}


def block(msg):
    print("lockdown: " + msg + " Ask the user to run it themselves if it is really needed.", file=sys.stderr)
    if AUDIT.get("root"):  # record denials too, so the audit log shows attempts, not just successes
        try:
            import time
            with open(os.path.join(AUDIT["root"], ".claude", "audit.jsonl"), "a") as f:
                f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": AUDIT.get("tool"),
                                    "blocked": msg, "input": AUDIT.get("input")}) + "\n")
        except OSError:
            pass
    return 2


def inside(path, root, cwd):
    p = os.path.expanduser(path)
    p = p if os.path.isabs(p) else os.path.join(cwd, p)
    real = os.path.realpath(p)
    return real == root or real.startswith(root + os.sep)


def load_allow(root):
    try:
        with open(os.path.join(root, ".claude", "lockdown.json")) as f:
            return json.load(f).get("allowed_commands", DEFAULT_ALLOW)
    except (OSError, ValueError):
        return DEFAULT_ALLOW


def check_file_tool(tool, ti, root, cwd):
    for k in FILE_KEYS:
        v = ti.get(k)
        if not v:
            continue
        if not inside(v, root, cwd):
            return block(f"{tool} on '{v}' is outside the project folder.")
        rel = os.path.relpath(os.path.realpath(os.path.join(cwd, os.path.expanduser(v))), root)
        if tool in WRITE_TOOLS and (rel == "CLAUDE.md" or rel == ".claude" or rel.startswith(".claude" + os.sep)):
            return block(f"{tool} on '{rel}' is blocked: guardrail files are edited by the user only.")
    return 0


def segments(cmd):
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>")
    lex.whitespace_split = True
    lex.commenters = ""
    seg = []
    for tok in lex:
        if tok in SEPARATORS or set(tok) <= set(";&|") and tok:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(tok)
    if seg:
        yield seg


def check_bash(cmd, root, cwd):
    if any(x in cmd for x in ("$(", "`", "<(", ">(", "${")):
        return block("command substitution and process substitution are not allowed.")
    try:
        segs = list(segments(cmd))
    except ValueError:
        return block("could not parse the command.")
    allow = [a.split() for a in load_allow(root)]
    for seg in segs:
        while seg and "=" in seg[0] and not seg[0].startswith("="):
            return block("environment variable assignments are not allowed.")
        if not seg:
            continue
        prog = os.path.basename(seg[0])
        if not any(seg[:len(a)] == a or ([prog] + seg[1:len(a)] == a) for a in allow):
            return block(f"'{' '.join(seg[:2])}' is not on the allowlist (.claude/lockdown.json).")
        flags = set(seg[1:])
        for name, bad in INTERPRETER_FLAGS.items():
            if prog == name and flags & bad:
                return block(f"{prog} {sorted(flags & bad)[0]} (inline code) is not allowed. Write a script file.")
        if prog in BAD_FLAGS and (flags & BAD_FLAGS[prog] or any(f.startswith("-i") for f in flags if prog == "sed")):
            return block(f"{prog} with {sorted(flags & BAD_FLAGS[prog]) or ['-i']} is not allowed.")
        expect_target = False
        for arg in seg[1:]:
            if arg in REDIRECTS:
                expect_target = True
                continue
            looks_path = expect_target or "/" in arg or arg.startswith(("~", ".."))
            if looks_path and not arg.startswith("-") and not inside(arg, root, cwd):
                return block(f"'{arg}' is outside the project folder.")
            expect_target = False
    return 0


def main():
    data = json.load(sys.stdin)
    root = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    cwd = data.get("cwd") or root
    tool, ti = data.get("tool_name", ""), data.get("tool_input") or {}
    AUDIT.update(root=root, tool=tool, input={k: v[:300] for k, v in ti.items()
                                              if isinstance(v, str) and k in ("command", "file_path", "path", "notebook_path")})
    if not inside(cwd, root, root):
        return block("working directory is outside the project folder.")
    if tool == "Bash":
        return check_bash(ti.get("command") or "", root, cwd)
    return check_file_tool(tool, ti, root, cwd)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # fail closed
        print(f"lockdown: internal error ({type(e).__name__}), blocking to be safe.", file=sys.stderr)
        sys.exit(2)
