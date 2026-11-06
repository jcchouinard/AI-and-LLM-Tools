#!/usr/bin/env python3
"""End-to-end tests for scripts/create_project.py in a throwaway HOME. Run: python3 tests/test_scaffold.py"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "create_project.py")
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def main():
    home = os.path.realpath(tempfile.mkdtemp())
    work = os.path.join(home, "work")
    os.makedirs(os.path.join(home, ".claude"))
    os.makedirs(work)
    json.dump({"mcpServers": {"playwright": {}, "chrome-devtools": {}, "grok": {}}},
              open(os.path.join(home, ".claude.json"), "w"))
    json.dump({"enabledPlugins": {"stripe@official": True, "old@x": False}},
              open(os.path.join(home, ".claude", "settings.json"), "w"))
    env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=os.path.join(home, ".config"),
               GIT_CONFIG_GLOBAL=os.path.join(home, ".gitconfig"), GIT_CONFIG_NOSYSTEM="1")

    def ls(*args, cwd=work):
        r = subprocess.run([sys.executable, "-I", SCRIPT] + list(args), cwd=cwd, env=env,
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def settings(name):
        return json.load(open(os.path.join(work, name, ".claude", "settings.json")))

    rc, _ = ls("setup", "--add-identity", "personal", "--git-name", "tester",
               "--git-email", "1+tester@users.noreply.github.com", "--gh-user", "tester")
    check(rc == 0, "setup failed")

    # refusals
    check(ls("new", home)[0] == 1, "must refuse HOME")
    check(ls("new", os.path.join(home, ".claude", "x"))[0] == 1, "must refuse inside ~/.claude")
    check(ls("new", "m1x", "--mode", "1", "--remote", "private")[0] == 1, "mode 1 cannot create a remote")
    check(ls("new", "bad", "--identity", "nobody")[0] == 1, "unknown identity must fail")

    # dry run writes nothing
    rc, out = ls("new", "dry", "--mode", "2", "--identity", "personal", "--dry-run")
    check(rc == 0 and not os.path.exists(os.path.join(work, "dry")), "dry run must not write")

    for m in "1234":
        args = ["new", f"m{m}", "--mode", m] + ([] if m == "1" else ["--identity", "personal"])
        if m == "3":
            args += ["--enable", "mcp:playwright,web"]
        rc, out = ls(*args)
        check(rc == 0, f"mode {m} failed: {out[-300:]}")
        rc, out = ls("doctor", os.path.join(work, f"m{m}"))
        check(rc == 0, f"doctor mode {m}: {out}")
        cm = open(os.path.join(work, f"m{m}", "CLAUDE.md")).read()
        check(len(cm.split()) < 230, f"mode {m} CLAUDE.md too long: {len(cm.split())} words")
        launch = open(os.path.join(work, f"m{m}", ".claude", "start.command")).read()
        check(os.access(os.path.join(work, f"m{m}", ".claude", "start.command"), os.X_OK), f"mode {m} launcher not executable")
        if m in "124":
            check("--strict-mcp-config" in launch and "--setting-sources project,local" in launch, f"mode {m} launcher not lean")

    s1 = settings("m1")
    check("mcp__*" in s1["permissions"]["deny"], "mode 1 must deny all MCP")
    check(s1["enabledPlugins"] == {"stripe@official": False}, f"mode 1 plugins: {s1.get('enabledPlugins')}")
    check(not os.path.exists(os.path.join(work, "m1", ".git")), "mode 1 must not create git")
    check(not os.path.exists(os.path.join(work, "m1", ".claude", "skills")), "mode 1 has no pr-gate")

    s2 = settings("m2")
    check(os.path.exists(os.path.join(work, "m2", ".claude", "skills", "pr-gate", "scripts", "scan.py")), "mode 2 pr-gate missing")
    email = subprocess.run(["git", "config", "--local", "user.email"], cwd=os.path.join(work, "m2"),
                           capture_output=True, text=True, env=env).stdout.strip()
    check(email == "1+tester@users.noreply.github.com", f"mode 2 git email: {email}")
    log = subprocess.run(["git", "log", "--format=%an"], cwd=os.path.join(work, "m2"), capture_output=True, text=True, env=env).stdout.strip()
    check(log == "tester", f"mode 2 commit author: {log}")
    hooks = json.dumps(s2["hooks"])
    check("token_gate.py" in hooks and "pre_pr_hook.py" in hooks, "mode 2 hooks")

    s3 = settings("m3")
    d3 = s3["permissions"]["deny"]
    check("mcp__grok__*" in d3 and "mcp__chrome-devtools__*" in d3 and "mcp__playwright__*" not in d3, f"mode 3 mcp denies: {d3}")
    check("WebFetch" not in d3 and "Workflow" in d3, "mode 3 extras")
    check(s3.get("enabledPlugins") == {"stripe@official": False} and s3.get("disableClaudeAiConnectors") is True, "mode 3 plugins/connectors")

    mcp_local = os.path.join(work, "m3", ".claude", "mcp.local.json")
    check(os.path.exists(mcp_local) and list(json.load(open(mcp_local))["mcpServers"]) == ["playwright"], "mode 3 mcp.local.json")
    check("--mcp-config .claude/mcp.local.json" in open(os.path.join(work, "m3", ".claude", "start.command")).read(), "mode 3 launcher mcp-config")
    tracked3 = subprocess.run(["git", "ls-files"], cwd=os.path.join(work, "m3"), capture_output=True, text=True, env=env).stdout
    check("mcp.local.json" not in tracked3, "mcp.local.json must never be committed")

    s4 = settings("m4")
    check(s4["permissions"]["defaultMode"] == "dontAsk" and s4["sandbox"]["enabled"], "mode 4 permissions/sandbox")
    check("lockdown.py" in json.dumps(s4["hooks"]) and "audit.py" in json.dumps(s4["hooks"]), "mode 4 hooks")
    check(os.path.exists(os.path.join(work, "m4", ".claude", "lockdown.json")), "mode 4 allowlist file")

    # existing folder: refused without flag, merged with it, user values kept, rerun is a no-op
    ex = os.path.join(work, "ex")
    os.makedirs(os.path.join(ex, ".claude"))
    json.dump({"model": "opus", "permissions": {"deny": ["Bash(rm *)"]}}, open(os.path.join(ex, ".claude", "settings.json"), "w"))
    open(os.path.join(ex, "CLAUDE.md"), "w").write("# mine\n")
    open(os.path.join(ex, "notes.txt"), "w").write("private\n")
    check(ls("new", "ex", "--mode", "2", "--identity", "personal")[0] == 1, "existing folder must need --existing-ok")
    rc, out = ls("new", "ex", "--mode", "2", "--identity", "personal", "--existing-ok")
    check(rc == 0, f"existing merge failed: {out}")
    se = settings("ex")
    check(se["model"] == "opus" and "Bash(rm *)" in se["permissions"]["deny"] and "mcp__*" in se["permissions"]["deny"], "merge must keep user values")
    check(open(os.path.join(ex, "CLAUDE.md")).read() == "# mine\n", "existing CLAUDE.md must be untouched")
    tracked = subprocess.run(["git", "ls-files"], cwd=ex, capture_output=True, text=True, env=env).stdout
    check("notes.txt" not in tracked, "first commit must not include pre-existing files")
    snap = open(os.path.join(ex, ".claude", "settings.json")).read()
    rc, out = ls("new", "ex", "--mode", "2", "--identity", "personal", "--existing-ok")
    check(rc == 0 and open(os.path.join(ex, ".claude", "settings.json")).read() == snap and "replaced" not in out, f"rerun must be a no-op: {out}")

    # uninstall keeps user-editable files by default
    rc, out = ls("uninstall", os.path.join(work, "m1"))
    check(rc == 0 and os.path.exists(os.path.join(work, "m1", "CLAUDE.md")) and
          not os.path.exists(os.path.join(work, "m1", ".claude", "start.command")), f"uninstall: {out}")

    # projects_root
    root = os.path.join(home, "projects")
    ls("setup", "--projects-root", root)
    rc, _ = ls("new", "rooted", "--mode", "1")
    check(rc == 0 and os.path.isdir(os.path.join(root, "rooted")), "projects_root not used for bare names")

    print("\n".join(fails) or "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
