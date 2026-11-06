#!/usr/bin/env python3
"""Redact PII and secrets from a staging directory, verify, and zip it.

Usage: scrub.py STAGING_DIR OUTPUT_ZIP [--term WORD ...]

--term adds extra strings to redact (names, company, domains, project names).
Auto-detects: $HOME path, OS username, git user.name/email, hostname.
Exits 1 (and writes no zip) if anything suspicious remains after redaction.
"""
import getpass
import os
import re
import socket
import subprocess
import sys
import zipfile
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
SKIP_NAMES = {".env", ".DS_Store"}
TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".ts",
            ".tsx", ".jsx", ".html", ".css", ".sh", ".sql", ".cfg", ".ini", ".example", ""}

# Extensions the share target accepts. Text files outside this set are zipped with a ".txt" suffix.
ALLOWED_EXT = {".md", ".mdx", ".markdown", ".txt", ".json", ".jsonc", ".yaml", ".yml", ".toml",
               ".csv", ".tsv", ".mdc", ".ini", ".sh", ".bash", ".py", ".js", ".mjs", ".ts",
               ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def arcname(p, root):
    rel = p.relative_to(root)
    return rel if p.suffix.lower() in ALLOWED_EXT else rel.with_name(rel.name + ".txt")


# (label, regex, replacement)
PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "<PRIVATE_KEY>"),
    ("url-creds", re.compile(r"(\w+://)[^/\s:@]+:[^/\s@]+@"), r"\1<USER>:<PASSWORD>@"),
    ("anthropic/openai", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "<API_KEY>"),
    ("stripe", re.compile(r"\b(?:sk|pk|rk|whsec)_(?:live|test)?_?[A-Za-z0-9]{16,}"), "<STRIPE_KEY>"),
    ("github", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}"), "<GITHUB_TOKEN>"),
    ("aws", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "<AWS_KEY>"),
    ("slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "<SLACK_TOKEN>"),
    ("google", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "<GOOGLE_KEY>"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "<JWT>"),
    ("bearer", re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{16,}"), r"\1 <TOKEN>"),
    ("kv-secret", re.compile(r"(?i)\b([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY|CREDENTIAL)[A-Z0-9_]*)\s*([=:])\s*['\"]?[^\s'\"]{6,}['\"]?"), r"\1\2 <REDACTED>"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
    ("path-mac", re.compile(r"/Users/[^/\s'\"]+"), "<HOME>"),
    ("path-linux", re.compile(r"/home/[^/\s'\"]+"), "<HOME>"),
    ("path-win", re.compile(r"[A-Za-z]:\\Users\\[^\\\s'\"]+"), "<HOME>"),
    ("ipv4", re.compile(r"\b(?!127\.0\.0\.1\b)(?!0\.0\.0\.0\b)(?:\d{1,3}\.){3}\d{1,3}\b"), "<IP>"),
    ("phone", re.compile(r"(?<![\w.])\+?\d{1,2}[\s.\-]?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}\b"), "<PHONE>"),
]


def git(key):
    try:
        return subprocess.check_output(["git", "config", "--global", key], text=True).strip()
    except Exception:
        return ""


def auto_terms():
    terms = {getpass.getuser(), socket.gethostname().split(".")[0], git("user.name"),
             git("user.email"), os.path.expanduser("~")}
    for t in list(terms):
        if t and " " in t:
            terms.update(p for p in t.split() if len(p) > 2)  # first/last name parts
    return sorted((t for t in terms if t and len(t) > 2), key=len, reverse=True)


def scrub(text, terms):
    for _, rx, rep in PATTERNS:
        text = rx.sub(rep, text)
    for t in terms:
        text = re.sub(re.escape(t), "<REDACTED>", text, flags=re.I)
    return text


def files(root):
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.name in SKIP_NAMES or SKIP_DIRS & set(p.parts):
            continue
        yield p


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    root, out = Path(args[0]).resolve(), Path(args[1]).resolve()
    extra = [args[i + 1] for i, a in enumerate(args) if a == "--term" and i + 1 < len(args)]
    terms = sorted(set(auto_terms() + extra), key=len, reverse=True)

    kept, dropped, changed = [], [], 0
    for p in files(root):
        if p.suffix.lower() not in TEXT_EXT:
            dropped.append(p)
            continue
        try:
            raw = p.read_text()
        except UnicodeDecodeError:
            dropped.append(p)
            continue
        clean = scrub(raw, terms)
        if clean != raw:
            p.write_text(clean)
            changed += 1
        kept.append(p)

    # Verification pass: nothing from the term list or high-risk patterns may remain.
    problems = []
    for p in kept:
        text = p.read_text()
        for t in terms:
            if re.search(re.escape(t), text, re.I):
                problems.append(f"{p.relative_to(root)}: term '{t}'")
        for label, rx, _ in PATTERNS:
            if label in {"ipv4", "phone"}:
                continue
            for m in rx.finditer(text):
                if "<" not in m.group(0):
                    problems.append(f"{p.relative_to(root)}: {label}")
    if problems:
        print("FAILED verification, no zip written:\n  " + "\n  ".join(sorted(set(problems))))
        sys.exit(1)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        renamed = []
        for p in kept:
            name = arcname(p, root)
            if name != p.relative_to(root):
                renamed.append((str(name), str(p.relative_to(root))))
            z.write(p, name)
        if renamed:
            z.writestr("RENAMED_FILES.md", "# Renamed files\n\nThese files got a `.txt` suffix because the share target rejects their "
                       "extension. Remove the `.txt` suffix to restore the original.\n\n"
                       + "\n".join(f"- `{n}` -> `{o}`" for n, o in renamed) + "\n")
    print(f"OK: {len(kept)} files zipped ({changed} redacted), {len(dropped)} skipped (binary/unknown)")
    for p in dropped:
        print(f"  skipped: {p.relative_to(root)}")
    print(f"Terms redacted: {len(terms)} (names not shown)")
    print(f"Zip: {out}")


if __name__ == "__main__":
    main()
