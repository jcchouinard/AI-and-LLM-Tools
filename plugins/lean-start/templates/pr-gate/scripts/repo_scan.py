#!/usr/bin/env python3
"""pr-gate repo audit: bounded whole-repository scan.

Step 1 is always --estimate: it lists files (git ls-files, or a depth-limited
walk outside git) and stats them. It never opens a file, so it is cheap even
on huge repos, and the listing itself stops at --max-list.

Step 2 scans file contents in priority order (agent files, config/dotfiles,
docs, source, other) and stops on whichever budget hits first: files, total
bytes, or wall-clock time. If a budget stops the scan the verdict is INCOMPLETE,
never PASS.

It also prints a capped "review queue" of files and line ranges for the
agent's adversarial read, so the agent never has to browse the repo itself.

Exit: 0 pass, 1 blocked (HIGH), 2 error, 3 incomplete (budget hit, no HIGH),
      4 refused (repo over the size where a full audit is reasonable; scope with --path)

Usage:
  repo_scan.py --estimate                 # step 1: counts only, no file reads
  repo_scan.py                            # step 2 with default budgets
  repo_scan.py --path src --path config   # scope a big repo
  repo_scan.py --max-files 20000 --time-limit 300
  repo_scan.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("pr_gate_scan", os.path.join(_here, "scan.py"))
core = importlib.util.module_from_spec(_spec)
sys.modules["pr_gate_scan"] = core  # dataclasses need the module registered
_spec.loader.exec_module(core)  # explicit path: works under python -I

# Defaults (normal run) and hard ceilings (no flag can exceed these).
DEFAULTS = dict(max_list=200_000, max_depth=15, max_files=5_000, max_file_bytes=1_000_000,
                max_total_bytes=100_000_000, time_limit=90, review_files=12, review_bytes=60_000)
HARD = dict(max_list=500_000, max_depth=30, max_files=50_000, max_file_bytes=5_000_000,
            max_total_bytes=1_000_000_000, time_limit=600, review_files=40, review_bytes=200_000)
MAX_LINE = 4_000          # longer lines are cut (minified code, regex safety)
MAX_LINES_PER_FILE = 50_000
MAX_FINDINGS = 500
MAX_FINDINGS_PER_FILE = 20
SCAN_MB_PER_SEC = 2.5     # measured ~3 MB/s on an M-series Mac; kept conservative

# Tiers decided from the estimate (scannable text candidates / bytes).
TIERS = [  # (name, max_candidates, max_bytes, advice)
    ("small", 2_000, 50_000_000, "full scan with defaults"),
    ("medium", 20_000, 300_000_000, "priority scan with defaults; may end INCOMPLETE, then raise limits or scope"),
    ("large", 100_000, 2_000_000_000, "scope with --path to the parts that will be published; ask the user first"),
]

EXCLUDE_DIRS = {".git", "node_modules", "bower_components", "vendor", "third_party", ".venv", "venv", "env",
                "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".ruff_cache", "dist", "build", "out",
                "target", ".next", ".nuxt", ".svelte-kit", ".turbo", ".parcel-cache", ".cache", "coverage",
                "htmlcov", "Pods", "DerivedData", ".gradle", ".idea", ".terraform", "site-packages"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".psd", ".svgz", ".avif", ".heic",
              ".mp3", ".mp4", ".mov", ".avi", ".wav", ".flac", ".ogg", ".webm", ".mkv",
              ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z",
              ".rar", ".tar", ".jar", ".war", ".whl", ".egg", ".so", ".dylib", ".dll", ".exe", ".bin", ".o",
              ".a", ".class", ".pyc", ".wasm", ".parquet", ".avro", ".pkl", ".pt", ".onnx", ".h5", ".npy",
              ".npz", ".dmg", ".iso", ".docx", ".xlsx", ".pptx", ".sqlite", ".sqlite3", ".db"}
SKIP_CONTENT = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "Gemfile.lock",
                "composer.lock", "go.sum", "uv.lock", "Pipfile.lock", "bun.lockb"}
SKIP_SUFFIX = (".min.js", ".min.css", ".map", ".bundle.js", ".chunk.js")

AGENT_HINTS = ("CLAUDE.md", "AGENTS.md", "SKILL.md", "GEMINI.md", ".cursorrules", ".windsurfrules",
               "copilot-instructions.md", ".mcp.json")
CONFIG_EXT = {".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml", ".env",
              ".sh", ".bash", ".zsh", ".ps1", ".bat", ".tf", ".tfvars", ".gradle", ".plist", ".npmrc"}
CONFIG_NAMES = {"Dockerfile", "Makefile", "Procfile", "Jenkinsfile", "docker-compose.yml", "docker-compose.yaml"}
DOC_EXT = {".md", ".mdx", ".txt", ".rst", ".html", ".htm", ".adoc"}
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rb", ".php", ".java", ".kt", ".cs",
            ".rs", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".sql", ".ipynb", ".vue", ".svelte", ".lua",
            ".r", ".scala", ".pl", ".ex", ".exs", ".dart"}
PRIORITY_NAMES = ["agent", "config", "docs", "code", "other"]


def clamp(args):
    notes = []
    for k, hard in HARD.items():
        v = getattr(args, k)
        if v is None:
            setattr(args, k, DEFAULTS[k])
        elif v > hard:
            setattr(args, k, hard)
            notes.append(f"{k} clamped to hard ceiling {hard}")
    return notes


# --------------------------------------------------------------------------
# step 1: enumerate + classify (no content reads)
# --------------------------------------------------------------------------
def list_files(root, scopes, max_list, max_depth):
    """Yield repo-relative paths. Stops hard at max_list. Never follows symlinks."""
    is_git = subprocess.run(["git", "-C", root, "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True).stdout.strip() == "true"
    stats = {"source": "git ls-files" if is_git else "filesystem walk", "list_capped": False, "too_deep": 0}
    out = []
    if is_git:
        cmd = ["git", "-C", root, "ls-files", "-z", "--", *(scopes or ["."])]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        buf = b""
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            *parts, buf = buf.split(b"\0")
            for p in parts:
                out.append(p.decode("utf-8", "replace"))
                if len(out) >= max_list:
                    stats["list_capped"] = True
                    proc.kill()
                    break
            if stats["list_capped"]:
                break
        proc.wait()
    else:
        for scope in (scopes or ["."]):
            base = os.path.normpath(os.path.join(root, scope))
            for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
                rel = os.path.relpath(dirpath, root)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS] if depth < max_depth else []
                if depth >= max_depth and filenames:
                    stats["too_deep"] += 1
                for fn in filenames:
                    out.append(os.path.normpath(os.path.join(rel, fn)))
                    if len(out) >= max_list:
                        stats["list_capped"] = True
                        return out, stats
    return out, stats


def priority(path):
    base = os.path.basename(path)
    ext = os.path.splitext(base)[1].lower()
    if base in AGENT_HINTS or "/.claude/" in "/" + path or path.startswith(".github/workflows/") \
            or "/.cursor/" in "/" + path:
        return 0
    if ext in CONFIG_EXT or base in CONFIG_NAMES or base.startswith(".") or base.startswith(".env"):
        return 1
    if ext in DOC_EXT:
        return 2
    if ext in CODE_EXT:
        return 3
    return 4


def classify(root, paths, max_depth, max_file_bytes):
    """Split paths into scan candidates and skip buckets, using lstat only."""
    cands, skipped, skip_bytes = [], Counter(), 0
    total_bytes, dir_counts = 0, Counter()
    for p in paths:
        parts = p.split("/")
        dir_counts[parts[0] if len(parts) > 1 else "(root)"] += 1
        if len(parts) - 1 > max_depth:
            skipped["too deep"] += 1
            continue
        if any(seg in EXCLUDE_DIRS for seg in parts[:-1]):
            skipped["vendored/build dir"] += 1
            continue
        base = parts[-1]
        ext = os.path.splitext(base)[1].lower()
        try:
            st = os.lstat(os.path.join(root, p))
        except OSError:
            skipped["missing on disk"] += 1
            continue
        if stat.S_ISLNK(st.st_mode):
            skipped["symlink (not followed)"] += 1
            continue
        if ext in BINARY_EXT:
            skipped["binary extension"] += 1
            continue
        if base in SKIP_CONTENT or base.endswith(SKIP_SUFFIX):
            skipped["lockfile/minified"] += 1
            continue
        if st.st_size > max_file_bytes:
            skipped["over per-file size cap"] += 1
            skip_bytes += st.st_size
            continue
        total_bytes += st.st_size
        cands.append((priority(p), p.count("/"), st.st_size, p))
    cands.sort()
    return cands, skipped, total_bytes, dir_counts


def tier_for(n, nbytes, capped):
    if capped:
        return "huge", "listing hit --max-list: refuse a full audit; scope with --path"
    for name, mf, mb, advice in TIERS:
        if n <= mf and nbytes <= mb:
            return name, advice
    return "huge", "refuse a full audit; scope with --path to what will actually be published"


# --------------------------------------------------------------------------
# step 2: bounded content scan
# --------------------------------------------------------------------------
def scan_contents(root, cands, args, deny):
    findings, scanned, scanned_bytes, stop = [], [], 0, None
    deadline = time.monotonic() + args.time_limit
    long_lines = 0
    for prio, _d, size, p in cands:
        if len(scanned) >= args.max_files:
            stop = f"max-files ({args.max_files})"
            break
        if scanned_bytes + size > args.max_total_bytes:
            stop = f"max-total-bytes ({args.max_total_bytes:,})"
            break
        if time.monotonic() > deadline:
            stop = f"time-limit ({args.time_limit}s)"
            break
        if len(findings) >= MAX_FINDINGS:
            stop = f"finding cap ({MAX_FINDINGS}): fix the first batch, then rescan"
            break
        try:
            with open(os.path.join(root, p), "rb") as f:
                data = f.read(args.max_file_bytes)
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue  # binary content
        scanned.append(p)
        scanned_bytes += len(data)
        file_findings = []
        for i, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            if i > MAX_LINES_PER_FILE or len(file_findings) >= MAX_FINDINGS_PER_FILE:
                break
            if len(line) > MAX_LINE:
                long_lines += 1
                line = line[:MAX_LINE]
            core.scan_text(line, p, p, i, deny, file_findings)
            if i % 5000 == 0 and time.monotonic() > deadline:
                break
        findings += file_findings
    return findings, scanned, scanned_bytes, stop, long_lines


def review_queue(findings, cands, scanned, args):
    """Capped list of what the agent may read in its adversarial pass."""
    sizes = {p: s for _, _, s, p in cands}
    prios = {p: pr for pr, _, _, p in cands}
    by_file = {}
    for f in findings:
        if f.line is not None and f.where in sizes:
            by_file.setdefault(f.where, []).append(f)
    picks = []
    rank = lambda p: (0 if any(x.severity == core.HIGH for x in by_file[p]) else 1, prios.get(p, 4))
    for p in sorted(by_file, key=rank):
        ranges = []
        for l in sorted({x.line for x in by_file[p]}):
            lo, hi = max(1, l - 10), l + 10
            if ranges and lo <= ranges[-1][1] + 1:
                ranges[-1][1] = hi
            else:
                ranges.append([lo, hi])
        ranges = ranges[:5]
        nlines = sum(hi - lo + 1 for lo, hi in ranges)
        picks.append({"path": p, "reason": ", ".join(sorted({x.rule for x in by_file[p]}))[:80],
                      "read": [f"{lo}-{hi}" for lo, hi in ranges], "bytes": min(sizes[p], nlines * 120)})
    for p in scanned:  # then unflagged agent/config files, which carry the most injection risk
        if prios.get(p, 4) <= 1 and p not in by_file:
            picks.append({"path": p, "reason": PRIORITY_NAMES[prios[p]] + " file",
                          "read": ["whole"] if sizes[p] <= 8_000 else ["1-150"], "bytes": min(sizes[p], 8_000)})
    queue, used = [], 0
    for q in picks:
        if len(queue) >= args.review_files or used + q["bytes"] > args.review_bytes:
            break
        queue.append(q)
        used += q["bytes"]
    return queue, used, len(picks) - len(queue)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estimate", action="store_true", help="step 1: list + stat only, no file reads")
    ap.add_argument("--path", action="append", help="limit to these repo-relative paths (repeatable)")
    for k in DEFAULTS:
        ap.add_argument("--" + k.replace("_", "-"), type=int, dest=k, default=None)
    ap.add_argument("--force", action="store_true", help="scan a 'huge' repo anyway (still bounded by budgets)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    notes = clamp(args)

    root = os.path.abspath(args.root)
    top = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode == 0:
        root = top.stdout.strip()
    if not os.path.isdir(root):
        print(f"repo_scan: not a directory: {root}", file=sys.stderr)
        return 2
    for s in args.path or []:
        if os.path.isabs(s) or ".." in s.split("/"):
            print(f"repo_scan: --path must be repo-relative: {s}", file=sys.stderr)
            return 2

    t0 = time.monotonic()
    paths, lstats = list_files(root, args.path, args.max_list, args.max_depth)
    cands, skipped, cand_bytes, dir_counts = classify(root, paths, args.max_depth, args.max_file_bytes)
    if lstats["too_deep"]:
        skipped["too deep"] += lstats["too_deep"]
    tier, advice = tier_for(len(cands), cand_bytes, lstats["list_capped"])
    risky = []
    for p in paths:  # filename checks are free: run them on everything listed
        if any(core.path_matches(p, s) for s in core.SAFE_FILES):
            continue
        for pat, sev, why in core.RISKY_FILES:
            if core.path_matches(p, pat):
                risky.append(core.Finding(sev, "risky-file", "risky-file", p, None, why))
                break
    ignore = core.load_lines(os.path.join(root, core.IGNORE_FILE))
    risky = [f for f in risky if not any(core.path_matches(f.where, g) for g in ignore)]
    cands = [c for c in cands if not any(core.path_matches(c[3], g) for g in ignore)]
    cap_n = min(len(cands), args.max_files)
    cap_bytes = min(cand_bytes, args.max_total_bytes)
    est = {
        "root": root, "source": lstats["source"], "listed": len(paths),
        "listed_is_lower_bound": lstats["list_capped"], "scan_candidates": len(cands),
        "candidate_bytes": cand_bytes, "skipped": dict(skipped),
        "by_priority": dict(Counter(PRIORITY_NAMES[c[0]] for c in cands)),
        "top_dirs": dict(dir_counts.most_common(8)),
        "tier": tier, "advice": advice,
        "would_scan_files": cap_n, "would_scan_bytes": cap_bytes,
        "est_script_seconds": round(cap_bytes / (SCAN_MB_PER_SEC * 1e6) + 0.5, 1),
        "agent_review_budget": f"<= {args.review_files} files, <= {args.review_bytes:,} bytes (~{args.review_bytes // 4:,} tokens)",
        "limits": {k: getattr(args, k) for k in DEFAULTS}, "notes": notes,
        "estimate_seconds": round(time.monotonic() - t0, 2),
    }

    if args.estimate:
        if args.json:
            print(json.dumps({"estimate": est}, indent=2))
        else:
            lb = "≥" if est["listed_is_lower_bound"] else ""
            print(f"repo estimate ({est['source']}, {est['estimate_seconds']}s, no file contents read)")
            print(f"  listed {lb}{est['listed']:,} files | scan candidates {est['scan_candidates']:,} "
                  f"({cand_bytes / 1e6:.1f} MB) | by priority {est['by_priority']}")
            print(f"  skipped: {est['skipped'] or 'none'}")
            print(f"  top dirs: {est['top_dirs']}")
            print(f"  tier: {tier.upper()}: {advice}")
            print(f"  with current limits: scan {cap_n:,} files / {cap_bytes / 1e6:.1f} MB, ~{est['est_script_seconds']}s script time "
                  f"(0 model tokens); agent review {est['agent_review_budget']}")
            if risky:
                print(f"  risky file names already visible: {len(risky)} (e.g. {risky[0].where})")
            for n in notes:
                print("  note:", n)
        return 4 if tier == "huge" and not args.path else 0

    if tier == "huge" and not args.force:
        print(f"repo_scan: REFUSED. {advice}. Listed {'≥' if lstats['list_capped'] else ''}{len(paths):,} files. "
              "Run --estimate, then --path <dir>, or --force (still bounded).", file=sys.stderr)
        return 4

    deny = core.load_lines(os.path.join(root, core.DENY_FILE)) + core.load_lines(core.GLOBAL_DENY)
    findings, scanned, scanned_bytes, stop, long_lines = scan_contents(root, cands, args, deny)
    findings = risky + findings
    findings.sort(key=lambda f: (f.severity != core.HIGH, f.category, f.where, f.line or 0))
    high = [f for f in findings if f.severity == core.HIGH]
    warn = [f for f in findings if f.severity == core.WARN]
    unscanned = len(cands) - len(scanned)
    complete = stop is None and not lstats["list_capped"]
    verdict = "BLOCKED" if high else ("INCOMPLETE" if not complete else ("PASS with warnings" if warn else "PASS"))
    queue, qbytes, q_dropped = review_queue(findings, cands, scanned, args)
    coverage = {"scanned_files": len(scanned), "scanned_bytes": scanned_bytes, "unscanned_candidates": unscanned,
                "stopped_by": stop, "skipped": dict(skipped), "long_lines_truncated": long_lines,
                "seconds": round(time.monotonic() - t0, 1)}

    if args.json:
        print(json.dumps({"verdict": verdict, "estimate": est, "coverage": coverage,
                          "findings": [asdict(f) for f in findings],
                          "review_queue": queue, "review_queue_dropped": q_dropped}, indent=2))
    else:
        print(f"repo scan: {root} | tier {tier} | scanned {len(scanned):,}/{len(cands):,} candidates "
              f"({scanned_bytes / 1e6:.1f} MB) in {coverage['seconds']}s")
        if stop:
            print(f"  STOPPED by {stop}: {unscanned:,} lower-priority files not scanned")
        print(f"  skipped (not scanned by design): {dict(skipped) or 'none'}")
        for f in findings[:200]:
            loc = f"{f.where}:{f.line}" if f.line else f.where
            print(f"  [{f.severity}] {f.category}/{f.rule}  {loc}\n         {f.excerpt}")
        if len(findings) > 200:
            print(f"  ... {len(findings) - 200} more (use --json)")
        print(f"review queue for the agent ({len(queue)} files, ~{qbytes // 4:,} tokens; {q_dropped} dropped by budget):")
        for q in queue:
            print(f"  {q['path']}  lines {','.join(q['read'])}  [{q['reason']}]")
        print(f"verdict: {verdict}  ({len(high)} high, {len(warn)} warn)")
    return 1 if high else (3 if not complete else 0)


if __name__ == "__main__":
    sys.exit(main())
