#!/usr/bin/env python3
"""Adversarial tests for templates/hooks/lockdown.py. Run: python3 tests/test_lockdown.py"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "hooks", "lockdown.py")


def run(root, tool, ti, cwd=None):
    data = {"tool_name": tool, "tool_input": ti, "cwd": cwd or root}
    r = subprocess.run([sys.executable, "-I", HOOK], input=json.dumps(data), capture_output=True, text=True,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=root))
    return r.returncode


def main():
    root = os.path.realpath(tempfile.mkdtemp())
    os.makedirs(os.path.join(root, "src"))
    open(os.path.join(root, "src", "a.py"), "w").write("x = 1\n")
    os.symlink("/etc", os.path.join(root, "escape"))
    B = lambda cmd: ("Bash", {"command": cmd})
    allow = [
        ("Read", {"file_path": os.path.join(root, "src/a.py")}),
        ("Edit", {"file_path": "src/a.py"}),
        ("Read", {"file_path": ".claude/settings.json"}),
        B("ls -la src"), B("grep -n x src/a.py"), B("git status"), B("git diff --stat"),
        B("python3 src/a.py"), B("pytest -q"), B("cat src/a.py | grep x"), B("git add src/a.py && git commit -m wip"),
        B("echo hi > src/out.txt"), B("find . -name '*.py'"),
    ]
    deny = [
        ("Read", {"file_path": "/etc/passwd"}),
        ("Read", {"file_path": os.path.join(root, "../x")}),
        ("Read", {"file_path": "escape/hosts"}),                 # symlink escape
        ("Read", {"file_path": "~/.ssh/id_rsa"}),
        ("Edit", {"file_path": ".claude/settings.json"}),        # guardrails
        ("Write", {"file_path": ".claude/hooks/lockdown.py"}),
        ("Edit", {"file_path": "CLAUDE.md"}),
        ("Grep", {"pattern": "x", "path": "/Users"}),
        B("cat /etc/passwd"), B("cat ../secret"), B("cat escape/hosts"), B("ls ~"),
        B("curl https://example.com"), B("wget x"), B("ssh host"), B("rm -rf src"), B("sudo ls"),
        B("git push"), B("git push origin main"), B("git remote add x y"), B("git -c core.pager=sh log"),
        B("gh pr create"), B("bash -c 'ls'"), B("sh script.sh"), B("python3 -c 'import os'"),
        B("python3 -m http.server"), B("node -e 'x'"), B("echo $(whoami)"), B("echo `id`"),
        B("ls; curl x"), B("ls && rm x"), B("ls | sh"), B("ls || wget x"), B("FOO=1 ls"),
        B("find . -exec rm {} ;"), B("find . -delete"), B("sed -i s/a/b/ src/a.py"),
        B("echo x > /tmp/out"), B("echo x >> ../out"), B("cat < /etc/hosts"), B("eval ls"), B("exec ls"),
        B("env ls"), B("xargs rm"), B("ls ${HOME}"), B("pip install x"), B("npm install x"),
    ]
    fails = [f"should ALLOW {t} {ti}" for t, ti in allow if run(root, t, ti) != 0]
    fails += [f"should BLOCK {t} {ti}" for t, ti in deny if run(root, t, ti) != 2]
    if run(root, "Read", {"file_path": "src/a.py"}, cwd="/tmp") != 2:
        fails.append("should BLOCK when cwd is outside the project")
    print(f"{len(allow)} allowed, {len(deny) + 1} blocked cases")
    print("\n".join(fails) or "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
