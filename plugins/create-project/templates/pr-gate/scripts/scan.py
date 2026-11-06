#!/usr/bin/env python3
"""pr-gate scanner: deterministic first pass before any PR.

Scans what a PR would publish (every line added on the branch, every commit
message, every added file name) for credentials, prompt injection, hidden
unicode, risky files, agent-config risks and local/PII leaks.

Stdlib only. Never prints a full secret: matches are masked.

Exit codes: 0 = pass (warnings possible), 1 = blocked, 2 = usage/git error.

Usage:
  scan.py                 # auto: branch vs merge-base with main/master + staged
  scan.py --base origin/main
  scan.py --staged        # only staged changes (pre-commit use)
  (whole-repo audits: use repo_scan.py, which is bounded)
  scan.py --strict        # warnings block too
  scan.py --json
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict

HIGH, WARN = "HIGH", "WARN"
ALLOW_MARK = "pr-gate: allow"
IGNORE_FILE = ".pr-gate-ignore"
DENY_FILE = ".pr-gate-denylist"
GLOBAL_DENY = os.path.expanduser("~/.claude/pr-gate-denylist")

# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------
# (id, severity, category, regex, flags)
LINE_RULES = [
    # --- credentials ------------------------------------------------------
    ("aws-access-key", HIGH, "credential", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", 0),
    ("aws-secret", HIGH, "credential", r"aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}", re.I),
    ("github-token", HIGH, "credential", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}", 0),
    ("gitlab-token", HIGH, "credential", r"\bglpat-[A-Za-z0-9_\-]{20,}", 0),
    ("slack-token", HIGH, "credential", r"\bxox[abposr]-[A-Za-z0-9-]{10,}", 0),
    ("slack-webhook", HIGH, "credential", r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+", 0),
    ("discord-webhook", HIGH, "credential", r"discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]{20,}", 0),
    ("stripe-live", HIGH, "credential", r"\b[sr]k_live_[A-Za-z0-9]{16,}", 0),
    ("stripe-test", WARN, "credential", r"\b[sr]k_test_[A-Za-z0-9]{16,}", 0),
    ("stripe-webhook", HIGH, "credential", r"\bwhsec_[A-Za-z0-9]{20,}", 0),
    ("anthropic-key", HIGH, "credential", r"\bsk-ant-[A-Za-z0-9_\-]{20,}", 0),
    ("openai-key", HIGH, "credential", r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{32,}", 0),
    ("google-api-key", HIGH, "credential", r"\bAIza[0-9A-Za-z_\-]{35}\b", 0),
    ("google-oauth-secret", HIGH, "credential", r"\bGOCSPX-[A-Za-z0-9_\-]{20,}", 0),
    ("gcp-service-account", HIGH, "credential", r"\"type\"\s*:\s*\"service_account\"", 0),
    ("private-key", HIGH, "credential", r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY(?: BLOCK)?-----", 0),
    ("huggingface-token", HIGH, "credential", r"\bhf_[A-Za-z0-9]{34,}\b", 0),
    ("npm-token", HIGH, "credential", r"\bnpm_[A-Za-z0-9]{36}\b", 0),
    ("pypi-token", HIGH, "credential", r"\bpypi-AgE[A-Za-z0-9_\-]{50,}", 0),
    ("sendgrid-key", HIGH, "credential", r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b", 0),
    ("telegram-bot", HIGH, "credential", r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b", 0),
    ("jwt", HIGH, "credential", r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", 0),
    ("bearer-header", HIGH, "credential", r"authorization['\"]?\s*[:=]\s*['\"]?bearer\s+[A-Za-z0-9._\-~+/]{20,}", re.I),
    ("url-credentials", HIGH, "credential", r"\b[a-z][a-z0-9+.\-]*://[^/\s:@'\"]+:([^/\s:@'\"]{3,})@[^\s'\"]+", re.I),
    # --- prompt injection -------------------------------------------------
    ("pi-override", HIGH, "prompt-injection",
     r"\b(?:ignore|disregard|forget|override|bypass)\b[^\n]{0,40}\b(?:previous|prior|above|earlier|all|any|your|system|developer)\b[^\n]{0,30}\b(?:instructions?|prompts?|rules|directions|guidelines|guardrails|policies)\b", re.I),
    ("pi-conceal", HIGH, "prompt-injection",
     r"\b(?:do not|don't|never)\s+(?:tell|inform|mention|reveal|show|alert|notify)\b[^\n]{0,30}\b(?:the user|the human|anyone|the developer|the operator)\b", re.I),
    ("pi-exfil", HIGH, "prompt-injection",
     r"\b(?:send|post|upload|exfiltrate|forward|email|transmit|curl)\b[^\n]{0,60}\b(?:api[_ \-]?keys?|credentials|secrets|tokens|\.env|ssh[_ ]keys?|passwords|cookies|env(?:ironment)? var(?:iable)?s)\b[^\n]{0,40}\b(?:to|at)\b\s+\S*(?:https?://|@)", re.I),
    ("pi-role-hijack", WARN, "prompt-injection",
     r"\byou are now\b|\bnew (?:system )?instructions\s*:|\bfrom now on,? you (?:will|must)\b|\b(?:developer|god|jailbreak|DAN) mode\b", re.I),
    ("pi-fake-turn", WARN, "prompt-injection",
     r"<\s*/?\s*(?:system|assistant|im_start|im_end|system-reminder|instructions)\s*>|<\|im_(?:start|end)\|>|\[/?INST\]|^\s*(?:Human|Assistant|SYSTEM)\s*:\s", re.I),
    ("pi-agent-directive", WARN, "prompt-injection",
     r"\b(?:AI|LLM|assistant|agent|claude|chatgpt|copilot|cursor|gemini)s?\b[^\n]{0,40}\b(?:must|should|shall|will|are required to)\b[^\n]{0,20}\b(?:ignore|execute|run|delete|send|approve|merge|disable|skip)\b", re.I),
    ("pi-html-comment", WARN, "prompt-injection",
     r"<!--(?:(?!-->)[^\n]){0,200}?\b(?:ignore|instruction|assistant|AI agent|LLM|claude|system prompt|you must)\b", re.I),
    # --- agent / supply-chain config ---------------------------------------
    ("pipe-to-shell", WARN, "agent-config", r"\b(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b", re.I),
    ("bypass-permissions", WARN, "agent-config", r"dangerously-skip-permissions|bypassPermissions|--no-verify\b", 0),
    ("broad-bash-allow", WARN, "agent-config", r"\"Bash(?:\(\*\))?\"\s*[,\]]", 0),
    # --- local / PII leaks --------------------------------------------------
    ("home-path", WARN, "local-leak", r"(?:/Users/|/home/)(?!runner/|user/|username/|you/|me/|<)[A-Za-z0-9._\-]+/|C:\\\\?Users\\\\?(?!Public)[A-Za-z0-9._\-]+", 0),
    ("private-ip", WARN, "local-leak", r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b", 0),
    ("email", WARN, "pii", r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", 0),
]

GENERIC_SECRET = re.compile(
    r"(?i)\b([\w\-]*(?:api[_\-]?key|secret|token|passw(?:or)?d|pwd|access[_\-]?key|client[_\-]?secret|private[_\-]?key|auth[_\-]?key|credential)s?[\w\-]*)"
    r"['\"]?\s*(?::=|=>|[:=])\s*['\"]([^'\"\s]{8,})['\"]"
)
PLACEHOLDER = re.compile(
    r"(?i)your|xxx|example|sample|dummy|placeholder|changeme|change_me|redacted|replace|<|>|\$\{|\{\{|%s|"
    r"process\.env|os\.environ|getenv|env\[|secrets\.|\*\*\*|\.\.\.|test|fake|mock|todo|none|null|true|false"
)
EMAIL_OK = re.compile(r"(?i)noreply|no-reply|@example\.(?:com|org|net)|@users\.noreply\.github\.com|@localhost|@test\.|@email\.com|@domain\.com|git@github\.com")
URL_CRED_OK = re.compile(r"(?i)^(?:password|pass|passwd|pwd|secret|changeme|xxx+|\*+|\$\{?\w+\}?|<[^>]+>|user|admin)$")

# Invisible / bidi / tag characters (Trojan Source, ASCII smuggling).
HIDDEN_UNICODE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\u00ad\ufeff\U000e0000-\U000e007f]")
EMOJI_ZWJ = re.compile("(?<=[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F])\u200d(?=[\U0001F000-\U0001FAFF\u2600-\u27BF])")  # emoji joiners are fine
BASE64_BLOB = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{200,}={0,2}")

# File names: (glob, severity, reason). Matched on basename and full path.
RISKY_FILES = [
    (".env", HIGH, "dotenv file"),
    (".env.*", HIGH, "dotenv file"),
    ("*.pem", HIGH, "key/cert material"),
    ("*.key", HIGH, "key material"),
    ("*.p12", HIGH, "keystore"), ("*.pfx", HIGH, "keystore"),
    ("*.jks", HIGH, "keystore"), ("*.keystore", HIGH, "keystore"),
    ("*.ppk", HIGH, "PuTTY private key"),
    ("id_rsa*", HIGH, "SSH key"), ("id_ed25519*", HIGH, "SSH key"),
    ("id_ecdsa*", HIGH, "SSH key"), ("id_dsa*", HIGH, "SSH key"),
    (".netrc", HIGH, "stored credentials"), (".pypirc", HIGH, "stored credentials"),
    (".htpasswd", HIGH, "password hashes"), ("*.kdbx", HIGH, "password vault"),
    ("credentials", HIGH, "cloud credentials"), ("*credentials*.json", HIGH, "credentials file"),
    ("*service-account*.json", HIGH, "GCP service account"), ("*serviceaccount*.json", HIGH, "GCP service account"),
    ("client_secret*.json", HIGH, "OAuth client secret"), ("token.json", HIGH, "OAuth token"),
    ("*.tfstate", HIGH, "Terraform state (holds secrets)"), ("*.tfstate.backup", HIGH, "Terraform state"),
    ("*.har", HIGH, "HAR capture (cookies, auth headers)"), ("cookies.txt", HIGH, "browser cookies"),
    ("secrets.*", HIGH, "secrets file"), ("*.secret", HIGH, "secrets file"),
    (".npmrc", WARN, "may contain registry token"), (".dockercfg", HIGH, "registry creds"),
    ("*/.docker/config.json", HIGH, "registry creds"),
    (".claude/settings.local.json", WARN, "personal Claude settings (local permissions, paths)"),
    ("*.sqlite", WARN, "database file"), ("*.sqlite3", WARN, "database file"), ("*.db", WARN, "database file"),
    ("*.dump", WARN, "database dump"), ("*.bak", WARN, "backup file"),
    ("*.log", WARN, "log file (may contain tokens/PII)"),
    ("*.ipynb", WARN, "notebook (check outputs for data/keys)"),
    ("*.csv", WARN, "data file (check for real customer/PII data)"),
    ("*.xlsx", WARN, "data file (check for real customer/PII data)"),
]
SAFE_FILES = [".env.example", ".env.sample", ".env.template", ".env.dist", "*.pub", "*.example"]

AGENT_FILES = ("CLAUDE.md", "AGENTS.md", "SKILL.md", ".cursorrules", ".windsurfrules", "copilot-instructions.md",
               ".mcp.json", "settings.json", "GEMINI.md")


@dataclass
class Finding:
    severity: str
    rule: str
    category: str
    where: str
    line: int | None
    excerpt: str


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout if r.returncode == 0 else ""


def mask(s: str) -> str:
    s = s.strip()
    if len(s) <= 8:
        return s[:2] + "***"
    return f"{s[:4]}…{s[-2:]} ({len(s)} chars)"


def entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def load_lines(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
    except OSError:
        return []


def path_matches(path: str, pattern: str) -> bool:
    base = os.path.basename(path)
    return fnmatch.fnmatch(base, pattern) or fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, "*/" + pattern)


# --------------------------------------------------------------------------
# collecting what the PR would publish
# --------------------------------------------------------------------------
def default_base() -> str | None:
    for ref in ("origin/main", "origin/master", "main", "master"):
        if git("rev-parse", "--verify", "--quiet", ref, check=False).strip():
            mb = git("merge-base", "HEAD", ref, check=False).strip()
            head = git("rev-parse", "HEAD", check=False).strip()
            if mb and mb != head:
                return mb
            if mb == head:
                return mb  # nothing committed on top; staged still scanned
    return None  # new repo / no main: scan full history


def parse_patch(patch: str, source: str):
    """Yield (path, lineno, text) for every added line in a unified diff."""
    path, lineno, commit = None, 0, source
    for raw in patch.splitlines():
        if raw.startswith("COMMIT:"):
            commit = raw[7:15]
            continue
        if raw.startswith("+++ "):
            p = raw[4:]
            path = None if p == "/dev/null" else (p[2:] if p.startswith("b/") else p)
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
            continue
        if path is None:
            continue
        if raw.startswith("+"):
            yield path, lineno, raw[1:], commit
            lineno += 1
        elif raw.startswith(" "):
            lineno += 1


def collect(args):
    """Return (added_lines, file_paths, commit_messages, label)."""
    lines, files, messages = [], set(), []
    label = []
    if not args.staged:
        base = args.base or default_base()
        rng = f"{base}..HEAD" if base else "HEAD"
        has_head = bool(git("rev-parse", "--verify", "--quiet", "HEAD", check=False).strip())
        if has_head:
            # Per-commit patches so a secret added then deleted on the branch is still caught.
            patch = git("log", "-p", "--no-color", "--no-ext-diff", "-U0", "--format=COMMIT:%H", rng)
            lines += list(parse_patch(patch, "commit"))
            files |= set(filter(None, git("log", "--name-only", "--format=", "--diff-filter=AMR", rng).splitlines()))
            for msg in git("log", "--format=%H%x00%B%x1e", rng).split("\x1e"):
                if "\x00" in msg:
                    h, body = msg.strip().split("\x00", 1)
                    messages.append((h[:8], body))
            label.append(f"commits {rng}")
    staged = git("diff", "--cached", "--no-color", "--no-ext-diff", "-U0")
    lines += list(parse_patch(staged, "staged"))
    files |= set(filter(None, git("diff", "--cached", "--name-only", "--diff-filter=AMR").splitlines()))
    label.append("staged changes")
    return lines, files, messages, " + ".join(label)


# --------------------------------------------------------------------------
# scanning
# --------------------------------------------------------------------------
COMPILED = [(rid, sev, cat, re.compile(rx, fl)) for rid, sev, cat, rx, fl in LINE_RULES]


def scan_text(text: str, path: str, where: str, lineno, deny, out: list):
    if ALLOW_MARK in text:
        out.append(Finding(WARN, "allow-marker", "suppressed", where, lineno,
                           "line suppressed by allow marker: confirm a human added it"))
        return
    seen = set()
    is_agent_file = os.path.basename(path) in AGENT_FILES or "/.claude/" in "/" + path

    probe = EMOJI_ZWJ.sub("", text[1:] if lineno == 1 and text.startswith("\ufeff") else text)
    if HIDDEN_UNICODE.search(probe):
        chars = sorted({f"U+{ord(c):04X}" for c in HIDDEN_UNICODE.findall(probe)})
        out.append(Finding(HIGH, "hidden-unicode", "prompt-injection", where, lineno,
                           "invisible/bidi chars: " + ", ".join(chars[:6])))

    for rid, sev, cat, rx in COMPILED:
        m = rx.search(text)
        if not m:
            continue
        val = m.group(0)
        if rid == "email" and EMAIL_OK.search(val):
            continue
        if rid == "email" and re.match(r"(?i)\s*co-authored-by:", text):
            continue
        if rid == "url-credentials" and URL_CRED_OK.match(m.group(1)):
            continue
        if rid == "openai-key" and val.startswith("sk-ant-"):
            continue
        if rid == "broad-bash-allow" and not is_agent_file:
            continue
        if cat == "prompt-injection" and is_agent_file and sev == WARN:
            sev = HIGH  # agent-instruction files are read as instructions: stricter
        key = (cat, rid)
        if key in seen:
            continue
        seen.add(key)
        shown = mask(val) if cat == "credential" else val.strip()[:120]
        out.append(Finding(sev, rid, cat, where, lineno, shown))

    for m in GENERIC_SECRET.finditer(text):
        name, value = m.group(1), m.group(2)
        if PLACEHOLDER.search(value) or ("credential", "generic") in seen:
            continue
        if any(k[0] == "credential" for k in seen):
            continue
        if re.fullmatch(r"[a-z][a-z\-_. ]*", value):
            continue  # word-like values: same-origin, new-password, correct-horse
        e = entropy(value)
        if e < 3.5:
            continue
        sev = HIGH if (e >= 3.8 and len(value) >= 16) else WARN
        seen.add(("credential", "generic"))
        out.append(Finding(sev, "generic-secret", "credential", where, lineno,
                           f"{name} = {mask(value)} (entropy {e:.1f})"))

    for blob in BASE64_BLOB.findall(text):
        if "data:image" in text or "data:font" in text or "sha512-" in text or "integrity" in text:
            break
        out.append(Finding(WARN, "base64-blob", "obfuscation", where, lineno,
                           f"{len(blob)}-char base64 blob (decode and inspect)"))
        break

    for term in deny:
        try:
            if re.search(term, text, re.I):
                out.append(Finding(HIGH, "denylist", "confidential", where, lineno, f"matches denylisted term /{term}/"))
        except re.error:
            if term.lower() in text.lower():
                out.append(Finding(HIGH, "denylist", "confidential", where, lineno, f"matches denylisted term '{term}'"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        root = git("rev-parse", "--show-toplevel").strip()
        os.chdir(root)
        lines, files, messages, label = collect(args)
    except RuntimeError as e:
        print(f"pr-gate: {e}", file=sys.stderr)
        return 2

    ignore = load_lines(IGNORE_FILE)
    deny = load_lines(DENY_FILE) + load_lines(GLOBAL_DENY)
    ignored = lambda p: any(path_matches(p, g) for g in ignore)

    findings: list[Finding] = []
    for path in sorted(files):
        if ignored(path):
            continue
        if any(path_matches(path, s) for s in SAFE_FILES):
            continue
        for pat, sev, why in RISKY_FILES:
            if path_matches(path, pat):
                findings.append(Finding(sev, "risky-file", "risky-file", path, None, why))
                break

    for path, lineno, text, src in lines:
        if ignored(path):
            continue
        where = path if src in ("tree", "staged") else f"{path} (commit {src})"
        scan_text(text, path, where, lineno, deny, findings)

    for h, body in messages:
        for i, t in enumerate(body.splitlines(), 1):
            scan_text(t, "", f"commit-message {h}", i, deny, findings)

    # de-duplicate identical findings (same rule, file, excerpt) across commits
    uniq, keyset = [], set()
    for f in findings:
        k = (f.rule, f.where.split(" (commit")[0], f.excerpt)
        if k not in keyset:
            keyset.add(k)
            uniq.append(f)
    findings = sorted(uniq, key=lambda f: (f.severity != HIGH, f.category, f.where, f.line or 0))

    high = [f for f in findings if f.severity == HIGH]
    warn = [f for f in findings if f.severity == WARN]
    blocked = bool(high) or (args.strict and bool(warn))

    if args.json:
        print(json.dumps({"scope": label, "blocked": blocked, "high": len(high), "warn": len(warn),
                          "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        print(f"pr-gate scan: {label} | {len(files)} files, {len(lines)} added lines, {len(messages)} commit messages")
        for f in findings:
            loc = f"{f.where}:{f.line}" if f.line else f.where
            print(f"  [{f.severity}] {f.category}/{f.rule}  {loc}\n         {f.excerpt}")
        verdict = "BLOCKED" if blocked else ("PASS with warnings" if warn else "PASS")
        print(f"verdict: {verdict}  ({len(high)} high, {len(warn)} warn)")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
