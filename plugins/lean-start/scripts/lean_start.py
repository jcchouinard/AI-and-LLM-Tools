#!/usr/bin/env python3
"""lean-start: create a Claude Code project switched off as much as possible. Stdlib only, Python 3.10+.

Subcommands (run with python3 -I):
  setup      detect or save identities and the default location (~/.config/lean-start/config.json)
  inventory  list MCP servers, plugins and extras that mode 3 can enable (JSON)
  new        scaffold a project
  doctor     check a project against its mode
  uninstall  remove the files lean-start wrote (from the manifest)
Exit codes: 0 ok, 1 bad input or refused, 2 git/gh/IO error.
"""
import argparse
import datetime
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys

VERSION = "1.0.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "templates")
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "lean-start", "config.json")
HOME = os.path.realpath(os.path.expanduser("~"))
REFUSED = [HOME, "/", os.path.join(HOME, "Documents"), os.path.join(HOME, "Desktop"),
           os.path.join(HOME, "Downloads"), os.path.join(HOME, ".claude")]
GITIGNORE = [".env", ".env.*", "!.env.example", ".claude/settings.local.json", ".claude/audit.jsonl",
             ".claude/mcp.local.json",
             "logs/", "*.har", "*.pem", "*.key", ".DS_Store",
             ".venv/", "venv/", "__pycache__/", "*.pyc", "node_modules/", "dist/"]
BROWSER = re.compile(r"playwright|chrome|browser|puppeteer|selenium", re.I)

log = []


def say(msg):
    log.append(msg)


def run(cmd, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"`{' '.join(cmd[:3])}` failed: {r.stderr.strip()[:300]}")
    return r


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        if default is not None:
            return default
        raise


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def config():
    return load_json(CONFIG, {"version": 1, "projects_root": None, "identities": {}, "extra_rules": []})


# ---------------------------------------------------------------- setup
def gh_accounts():
    if not shutil.which("gh"):
        return []
    r = run(["gh", "auth", "status"], check=False)
    return re.findall(r"Logged in to github\.com account (\S+)", r.stdout + r.stderr)


def gh_noreply(user):
    tok = run(["gh", "auth", "token", "-u", user], check=False)
    if tok.returncode != 0:
        return None
    r = run(["gh", "api", "user", "--jq", ".id"], env=dict(os.environ, GH_TOKEN=tok.stdout.strip()), check=False)
    return f"{r.stdout.strip()}+{user}@users.noreply.github.com" if r.returncode == 0 and r.stdout.strip() else None


def cmd_setup(a):
    cfg = config()
    if a.detect:
        g = lambda k: run(["git", "config", "--global", k], check=False).stdout.strip()
        out = {"config_path": CONFIG, "configured": cfg,
               "git_global": {"name": g("user.name"), "email": g("user.email")},
               "gh_accounts": [{"login": u, "noreply": gh_noreply(u)} for u in gh_accounts()]}
        print(json.dumps(out, indent=2))
        return 0
    if a.add_identity:
        if not (a.git_name and a.git_email):
            print("--add-identity needs --git-name and --git-email")
            return 1
        cfg["identities"][a.add_identity] = {
            "label": a.label or a.add_identity, "git_name": a.git_name, "git_email": a.git_email,
            "gh_user": a.gh_user or "", "gh_owner": a.gh_owner or a.gh_user or ""}
    if a.remove_identity:
        cfg["identities"].pop(a.remove_identity, None)
    if a.projects_root is not None:
        cfg["projects_root"] = None if a.projects_root in ("", "none", ".") else os.path.abspath(os.path.expanduser(a.projects_root))
    if a.extra_rule:
        cfg["extra_rules"] = [r for r in cfg.get("extra_rules", []) if r not in a.extra_rule] + a.extra_rule
    save_json(CONFIG, cfg)
    print(f"saved {CONFIG}")
    print(json.dumps(cfg, indent=2))
    return 0


# ---------------------------------------------------------------- inventory
def mcp_definitions():
    """name -> server config, from user scope, this folder's local scope and ./.mcp.json."""
    cj = load_json(os.path.expanduser("~/.claude.json"), {})
    defs = dict(cj.get("mcpServers", {}))
    cwd = os.path.realpath(os.getcwd())
    for p, v in cj.get("projects", {}).items():
        if os.path.realpath(p) == cwd:
            defs.update((v or {}).get("mcpServers", {}))
    defs.update(load_json(os.path.join(cwd, ".mcp.json"), {}).get("mcpServers", {}))
    return defs


def inventory():
    servers = set(mcp_definitions())
    us = load_json(os.path.expanduser("~/.claude/settings.json"), {})
    plugins = sorted(k for k, v in us.get("enabledPlugins", {}).items() if v)
    items = [f"mcp:{s}" for s in sorted(servers)] + [f"plugin:{p}" for p in plugins]
    groups = []
    browser = [i for i in items if i.startswith("mcp:") and BROWSER.search(i)]
    other = [i for i in items if i.startswith("mcp:") and i not in browser]
    plug = [i for i in items if i.startswith("plugin:")]
    for key, label, members in (("browser", "Browser MCP", browser), ("mcp", "Other MCP servers", other),
                                ("plugins", "Plugins", plug)):
        if members:
            groups.append({"key": key, "label": label, "items": members,
                           "names": ", ".join(m.split(":", 1)[1].split("@")[0] for m in members)})
    extras = [{"key": "connectors", "label": "claude.ai connectors"},
              {"key": "web", "label": "Web search and fetch"},
              {"key": "workflow", "label": "Workflow and DesignSync (can spend a lot)"}]
    return {"items": items, "groups": groups, "extras": extras}


def cmd_inventory(a):
    print(json.dumps(inventory(), indent=2))
    return 0


# ---------------------------------------------------------------- new
def merge(base, add):
    """Union lists, recurse into dicts, keep existing scalars (the user's values win)."""
    for k, v in add.items():
        if k.startswith("_"):
            continue
        if k not in base:
            base[k] = v
        elif isinstance(base[k], dict) and isinstance(v, dict):
            merge(base[k], v)
        elif isinstance(base[k], list) and isinstance(v, list):
            base[k] += [x for x in v if x not in base[k]]
        elif base[k] != v:
            say(f"kept your existing value for '{k}'")
    return base


def add_hook(settings, event, matcher, command):
    lst = settings.setdefault("hooks", {}).setdefault(event, [])
    if any(h.get("command") == command for e in lst for h in e.get("hooks", [])):
        return
    lst.append({"matcher": matcher, "hooks": [{"type": "command", "command": command}]})


def hook_cmd(name):
    return f'python3 -I "$CLAUDE_PROJECT_DIR/.claude/hooks/{name}"'


class Writer:
    """Writes files, records them in the manifest, backs up anything it replaces."""

    def __init__(self, proj, dry):
        self.proj, self.dry, self.files = proj, dry, []

    def path(self, rel):
        return os.path.join(self.proj, rel)

    def text(self, rel, content, mode=None, keep_existing=False):
        p = self.path(rel)
        if os.path.exists(p):
            with open(p) as f:
                old = f.read()
            if old == content:
                self.files.append(rel)
                return
            if keep_existing:
                return False
            if not self.dry:
                shutil.copy2(p, p + ".bak")
            say(f"replaced {rel} (backup: {rel}.bak)")
        self.files.append(rel)
        if self.dry:
            say(f"would write {rel}")
            return True
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
        if mode:
            os.chmod(p, mode)
        return True

    def copy(self, src, rel, mode=None):
        with open(src) as f:
            return self.text(rel, f.read(), mode)


def resolve_target(name):
    cfg = config()
    p = os.path.expanduser(name)
    if not (os.path.isabs(p) or "/" in name or name.startswith(".")) and cfg.get("projects_root"):
        p = os.path.join(cfg["projects_root"], name)
    return os.path.realpath(os.path.abspath(p))


def refuse(proj):
    if proj in REFUSED:
        return f"refusing to scaffold {proj} itself. Use a subfolder."
    if proj.startswith(os.path.join(HOME, ".claude") + os.sep):
        return "refusing to scaffold inside ~/.claude."
    return None


def apply_picks(settings, mode_cfg, picks, inv):
    """Mode 3: deny everything that was not picked."""
    deny = settings.setdefault("permissions", {}).setdefault("deny", [])
    for item in inv["items"]:
        kind, name = item.split(":", 1)
        if kind == "plugin":
            settings.setdefault("enabledPlugins", {})[name] = item in picks
        elif item not in picks:
            rule = f"mcp__{name}__*"
            if rule not in deny:
                deny.append(rule)
    if "connectors" not in picks:
        settings["disableClaudeAiConnectors"] = True
    if "web" not in picks:
        deny += [t for t in ("WebSearch", "WebFetch") if t not in deny]
    if "workflow" not in picks:
        deny += [t for t in ("Workflow", "DesignSync") if t not in deny]
    say("enabled: " + (", ".join(sorted(picks)) or "nothing extra"))


def git_rules(ident, mode_cfg, main, pr_gate):
    if not mode_cfg["_git"]:
        return "- No git in this project unless the user asks for it."
    lines = [f"- Never commit to `{main}`. Branch first: `git switch -c <type>/<short-desc>` (feat, fix, docs, chore).",
             "- Small commits, imperative subject under 72 chars. Commit only when asked."]
    if ident:
        lines.insert(0, f"- Identity is set in this repo's local git config ({ident['git_name']}). Do not override it.")
    if mode_cfg["_lockdown"]:
        lines.append("- Push and PRs are blocked here. The user runs them.")
    elif ident and ident.get("gh_user"):
        u = ident["gh_user"]
        lines.append(f"- Ask before any push or PR. GitHub account: `{u}`. Run gh as `GH_TOKEN=$(gh auth token -u {u}) gh ...`, never `gh auth switch`.")
        lines.append(f"- PR: `GH_TOKEN=$(gh auth token -u {u}) gh pr create --base {main} --fill`" +
                     (". Run /pr-gate first." if pr_gate else "."))
    else:
        lines.append("- Ask before any push or PR" + (". Run /pr-gate first." if pr_gate else "."))
    return "\n".join(lines)


def launcher(mode, flags):
    q = " ".join(shlex.quote(x) for x in flags)
    return ("#!/bin/bash\n"
            f"# lean-start mode {mode}: launches Claude Code in this project with everything else switched off.\n"
            "# Extra arguments pass through, for example: .claude/start.command -c\n"
            'cd "$(dirname "$0")/.." || exit 1\n'
            f'exec claude {q} "$@"\n')


def setup_git(proj, ident, main, files):
    top = run(["git", "rev-parse", "--show-toplevel"], proj, check=False)
    if not (top.returncode == 0 and os.path.realpath(top.stdout.strip()) == proj):
        if top.returncode == 0:
            say(f"note: inside another repo ({top.stdout.strip()}), created a nested repo")
        run(["git", "init", "-q", "-b", main], proj)
    if ident:
        run(["git", "config", "--local", "user.name", ident["git_name"]], proj)
        run(["git", "config", "--local", "user.email", ident["git_email"]], proj)
        say(f"git identity (this repo only): {ident['git_name']} <{ident['git_email']}>")
    if run(["git", "rev-parse", "--verify", "HEAD"], proj, check=False).returncode != 0:
        run(["git", "add", "--"] + [f for f in files if os.path.exists(os.path.join(proj, f)) and not f.endswith(".local.json")], proj)
        run(["git", "commit", "-q", "-m", "chore: scaffold with lean-start"], proj)
        say(f"first commit on {main} (lean-start files only)")


def setup_remote(proj, ident, remote, main):
    if remote == "none":
        return
    if not ident or not ident.get("gh_user"):
        raise RuntimeError("creating a GitHub repo needs an identity with a gh_user (run setup)")
    if run(["git", "remote", "get-url", "origin"], proj, check=False).returncode == 0:
        say("remote origin already set, left untouched")
        return
    tok = run(["gh", "auth", "token", "-u", ident["gh_user"]], proj, check=False)
    if tok.returncode != 0:
        raise RuntimeError(f"gh has no login for {ident['gh_user']}: run `gh auth login`")
    env = dict(os.environ, GH_TOKEN=tok.stdout.strip())
    repo = f"{ident['gh_owner'] or ident['gh_user']}/{os.path.basename(proj)}"
    run(["gh", "repo", "create", repo, f"--{remote}", "--source", ".", "--remote", "origin"], proj, env=env)
    # The username in the URL makes gh's credential helper push as this account.
    run(["git", "remote", "set-url", "origin", f"https://{ident['gh_user']}@github.com/{repo}.git"], proj)
    run(["git", "push", "-q", "-u", "origin", main], proj, env=env)
    say(f"created {remote} repo github.com/{repo} as {ident['gh_user']} and pushed {main}")


def cmd_new(a):
    mode_cfg = load_json(os.path.join(TPL, "modes", f"{a.mode}.json"))
    cfg = config()
    proj = resolve_target(a.name)
    why = refuse(proj)
    if why:
        print("REFUSED: " + why)
        return 1
    if os.path.isdir(proj) and [f for f in os.listdir(proj) if f != ".git"] and not a.existing_ok:
        print(f"REFUSED: {proj} already has files. Re-run with --existing-ok to merge (nothing is overwritten without a .bak).")
        return 1
    ident = {}
    if a.identity != "none":
        ident = cfg["identities"].get(a.identity)
        if not ident:
            print(f"unknown identity '{a.identity}'. Known: {', '.join(cfg['identities']) or 'none, run setup'}")
            return 1
    if not mode_cfg["_git"] and a.remote != "none":
        print("mode 1 has no git; pick mode 2 or 3 for a GitHub repo")
        return 1
    if not a.dry_run:
        os.makedirs(proj, exist_ok=True)
    w = Writer(proj, a.dry_run)

    # settings
    sp = w.path(".claude/settings.json")
    settings = load_json(sp, {}) if os.path.exists(sp) else {}
    before = json.dumps(settings, sort_keys=True)
    merge(settings, mode_cfg)
    if mode_cfg.get("_disable_user_plugins"):
        us = load_json(os.path.expanduser("~/.claude/settings.json"), {})
        for k, v in us.get("enabledPlugins", {}).items():
            if v:
                settings.setdefault("enabledPlugins", {}).setdefault(k, False)
    launch = list(mode_cfg["_launch"])
    if mode_cfg.get("_picker"):
        picks = set(filter(None, a.enable.split(",")))
        apply_picks(settings, mode_cfg, picks, inventory())
        defs = mcp_definitions()
        chosen = {n: defs[n] for n in sorted(defs) if f"mcp:{n}" in picks}
        if chosen:
            # Local-only file: server configs can hold API keys. Gitignored, never committed.
            w.text(".claude/mcp.local.json", json.dumps({"mcpServers": chosen}, indent=2) + "\n", 0o600)
            launch += ["--mcp-config", ".claude/mcp.local.json"]
        # Connectors are controlled by disableClaudeAiConnectors; no --strict-mcp-config so picked plugins keep their MCP.

    # token-gate (all modes)
    w.copy(os.path.join(TPL, "hooks", "token_gate.py"), ".claude/hooks/token_gate.py", 0o755)
    w.copy(os.path.join(TPL, "agents", "file-summarizer.md"), ".claude/agents/file-summarizer.md")
    add_hook(settings, "PreToolUse", "Read", hook_cmd("token_gate.py"))
    add_hook(settings, "PreToolUse", "Bash", hook_cmd("token_gate.py"))
    say("token-gate: whole reads of files over 350 lines are blocked, Haiku file-summarizer does them")

    pr_gate = mode_cfg["_pr_gate"] and not a.no_pr_gate
    if pr_gate:
        src = os.path.join(TPL, "pr-gate")
        w.copy(os.path.join(src, "SKILL.md"), ".claude/skills/pr-gate/SKILL.md")
        for s in ("scan.py", "repo_scan.py", "pre_pr_hook.py"):
            w.copy(os.path.join(src, "scripts", s), f".claude/skills/pr-gate/scripts/{s}", 0o755)
        w.text(".pr-gate-ignore", open(os.path.join(src, "pr-gate-ignore")).read(), keep_existing=True)
        add_hook(settings, "PreToolUse", "Bash", 'python3 -I "$CLAUDE_PROJECT_DIR/.claude/skills/pr-gate/scripts/pre_pr_hook.py"')
        say("pr-gate: git push and gh pr create are blocked on HIGH findings, /pr-gate adds an adversarial read")

    if mode_cfg["_lockdown"]:
        w.copy(os.path.join(TPL, "hooks", "lockdown.py"), ".claude/hooks/lockdown.py", 0o755)
        w.copy(os.path.join(TPL, "hooks", "audit.py"), ".claude/hooks/audit.py", 0o755)
        sys.path.insert(0, os.path.join(TPL, "hooks"))
        import lockdown  # noqa: E402  (only for its default allowlist)
        w.text(".claude/lockdown.json", json.dumps({"allowed_commands": lockdown.DEFAULT_ALLOW}, indent=2) + "\n",
               keep_existing=True)
        add_hook(settings, "PreToolUse", "*", hook_cmd("lockdown.py"))
        add_hook(settings, "PostToolUse", "*", hook_cmd("audit.py"))
        say("lockdown: folder-only file access, command allowlist (.claude/lockdown.json), sandbox with no network, audit log")
        if platform.system() == "Linux" and not (shutil.which("bwrap") and shutil.which("socat")):
            say("WARNING: sandbox needs bubblewrap and socat on Linux (apt install bubblewrap socat). Claude will refuse to start without them.")

    if json.dumps(settings, sort_keys=True) != before or not os.path.exists(sp):
        w.text(".claude/settings.json", json.dumps(settings, indent=2) + "\n")
    else:
        w.files.append(".claude/settings.json")

    # CLAUDE.md
    rules = mode_cfg["_claude_md_rules"] + cfg.get("extra_rules", [])
    fills = {"PROJECT": os.path.basename(proj), "PURPOSE": a.purpose or "Purpose: (one line, fill in).",
             "GIT_RULES": git_rules(ident, mode_cfg, a.main, pr_gate), "MODE": a.mode,
             "MODE_LABEL": mode_cfg["_label"], "RULES": "\n".join(f"- {r}" for r in rules)}
    body = open(os.path.join(TPL, "CLAUDE.md.tmpl")).read()
    for k, v in fills.items():
        body = body.replace("{{" + k + "}}", v)
    cm = w.path("CLAUDE.md")
    if os.path.exists(cm) and "lean-start mode" not in open(cm).read():
        w.text("CLAUDE.lean-start.md", body)
        say("you already had a CLAUDE.md: wrote CLAUDE.lean-start.md, merge it by hand")
    else:
        w.text("CLAUDE.md", body)

    # .gitignore
    gp = w.path(".gitignore")
    have = open(gp).read().splitlines() if os.path.exists(gp) else []
    missing = [x for x in GITIGNORE if x not in have]
    if missing:
        w.text(".gitignore", "\n".join(have + ([""] if have else []) + missing) + "\n")
    else:
        w.files.append(".gitignore")

    # launcher + manifest
    w.text(".claude/start.command", launcher(a.mode, launch), 0o755)
    manifest = {"tool": "lean-start", "version": VERSION, "mode": a.mode, "identity": a.identity,
                "created": datetime.date.today().isoformat(), "files": sorted(set(w.files + [".claude/lean-start.json"]))}
    w.text(".claude/lean-start.json", json.dumps(manifest, indent=2) + "\n")

    if a.dry_run:
        print(f"DRY RUN {proj} (mode {a.mode}: {mode_cfg['_label']})")
        print("\n".join("- " + m for m in log))
        return 0
    try:
        if mode_cfg["_git"]:
            setup_git(proj, ident, a.main, manifest["files"])
            setup_remote(proj, ident, a.remote, a.main)
    except RuntimeError as e:
        print("ERROR: " + str(e))
        print("\n".join("- " + m for m in log))
        return 2
    print(f"OK {proj} (mode {a.mode}: {mode_cfg['_label']})")
    print("\n".join("- " + m for m in log))
    print(f"Start: {os.path.join(proj, '.claude', 'start.command')}")
    return 0


# ---------------------------------------------------------------- doctor / uninstall
def cmd_doctor(a):
    proj = os.path.realpath(a.dir)
    man = load_json(os.path.join(proj, ".claude", "lean-start.json"), {})
    if not man:
        print("not a lean-start project (no .claude/lean-start.json)")
        return 1
    problems = []
    for f in man["files"]:
        if not os.path.exists(os.path.join(proj, f)):
            problems.append(f"missing {f}")
    for f in (".claude/start.command", ".claude/hooks/token_gate.py"):
        p = os.path.join(proj, f)
        if os.path.exists(p) and not os.access(p, os.X_OK):
            problems.append(f"not executable: {f}")
    try:
        load_json(os.path.join(proj, ".claude", "settings.json"))
    except (OSError, ValueError):
        problems.append(".claude/settings.json is missing or not valid JSON")
    warnings = [] if shutil.which("claude") else ["claude is not on PATH (install Claude Code to launch the project)"]
    mode_cfg = load_json(os.path.join(TPL, "modes", f"{man['mode']}.json"), {})
    if mode_cfg.get("_git") and man.get("identity", "none") != "none":
        ident = config()["identities"].get(man["identity"], {})
        got = run(["git", "config", "--local", "user.email"], proj, check=False).stdout.strip()
        if ident and got != ident.get("git_email"):
            problems.append(f"git email is '{got}', expected '{ident.get('git_email')}'")
    print(f"mode {man['mode']}, lean-start {man['version']}, {len(man['files'])} files")
    print("\n".join(["- " + p for p in problems] + ["- warning: " + w for w in warnings]) or "OK")
    return 1 if problems else 0


def cmd_uninstall(a):
    proj = os.path.realpath(a.dir)
    man = load_json(os.path.join(proj, ".claude", "lean-start.json"), {})
    if not man:
        print("not a lean-start project")
        return 1
    for f in man["files"]:
        p = os.path.join(proj, f)
        if f in ("CLAUDE.md", ".gitignore", ".claude/settings.json") and not a.all:
            print(f"kept {f} (may hold your edits, use --all to remove)")
            continue
        if os.path.exists(p):
            os.remove(p) if not a.dry_run else None
            print(("would remove " if a.dry_run else "removed ") + f)
    return 0


def main():
    p = argparse.ArgumentParser(prog="lean-start")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--detect", action="store_true")
    s.add_argument("--add-identity")
    s.add_argument("--remove-identity")
    s.add_argument("--label")
    s.add_argument("--git-name")
    s.add_argument("--git-email")
    s.add_argument("--gh-user")
    s.add_argument("--gh-owner")
    s.add_argument("--projects-root")
    s.add_argument("--extra-rule", action="append")
    sub.add_parser("inventory")
    n = sub.add_parser("new")
    n.add_argument("name")
    n.add_argument("--mode", choices=["1", "2", "3", "4"], default="1")
    n.add_argument("--identity", default="none")
    n.add_argument("--remote", choices=["none", "private", "public"], default="none")
    n.add_argument("--enable", default="", help="mode 3: comma list of inventory items and extras")
    n.add_argument("--purpose", default="")
    n.add_argument("--main", default="main")
    n.add_argument("--no-pr-gate", action="store_true")
    n.add_argument("--existing-ok", action="store_true")
    n.add_argument("--dry-run", action="store_true")
    d = sub.add_parser("doctor")
    d.add_argument("dir", nargs="?", default=".")
    u = sub.add_parser("uninstall")
    u.add_argument("dir", nargs="?", default=".")
    u.add_argument("--all", action="store_true")
    u.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    try:
        return {"setup": cmd_setup, "inventory": cmd_inventory, "new": cmd_new,
                "doctor": cmd_doctor, "uninstall": cmd_uninstall}[a.cmd](a)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
