#!/usr/bin/env python3
"""claude_usage.py: see exactly where your Claude Code money goes.

    python3 claude_usage.py            # everything, opens an interactive dashboard
    python3 claude_usage.py --days 7   # last week
    python3 claude_usage.py --project .  # just the project you're standing in

No installs, no API keys, nothing leaves your machine. Reads the session logs
Claude Code already writes to ~/.claude/projects and prices every API call at
Anthropic's published list prices.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

VERSION = "2.0.0"
PRICING_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICING_CHECKED = "2026-11-06"

# ---------------------------------------------------------------------------
# Pricing, $ per million tokens, from the official pricing page.
# in = base input, w5 = 5-minute cache write, w1 = 1-hour cache write,
# read = cache hit, out = output. Fast mode and long-context tiers below.
# ---------------------------------------------------------------------------
def _p(inp, out, read_mult=0.1):
    return {"in": inp, "out": out, "w5": inp * 1.25, "w1": inp * 2.0, "read": inp * read_mult}

PRICES = {
    "claude-fable-5-1": dict(_p(10, 50), read=0.25),
    "claude-mythos-5-1": dict(_p(10, 50), read=0.25),
    "claude-fable-5": _p(10, 50),
    "claude-mythos-5": _p(10, 50),
    "claude-opus-5-5": _p(4, 20, 0.05),
    "claude-opus-5": _p(5, 25),
    "claude-opus-4-8": _p(5, 25),
    "claude-opus-4-7": _p(5, 25),
    "claude-opus-4-6": _p(5, 25),
    "claude-opus-4-5": _p(5, 25),
    "claude-opus-4-1": _p(15, 75),
    "claude-opus-4": _p(15, 75),
    "claude-sonnet-5-5": _p(2, 10, 0.05),
    "claude-sonnet-5": _p(2, 10),
    "claude-sonnet-4-6": _p(3, 15),
    "claude-sonnet-4-5": _p(3, 15),
    "claude-sonnet-4": _p(3, 15),
    "claude-3-7-sonnet": _p(3, 15),
    "claude-3-5-sonnet": _p(3, 15),
    "claude-haiku-5-5": _p(0.10, 0.50),
    "claude-haiku-4-5": _p(1, 5),
    "claude-3-5-haiku": _p(0.80, 4),
    "claude-3-opus": _p(15, 75),
    "claude-3-haiku": _p(0.25, 1.25),
}
# Haiku 5.5 bills a request whose prompt (input + cache reads + cache writes)
# exceeds 100K tokens at 5x the rates, for the whole request.
LONG_PROMPT_TIER = {"claude-haiku-5-5": (100_000, _p(0.50, 2.50))}
# Fast mode replaces base in/out; cache multipliers stack on top.
FAST_MODE = {
    "claude-opus-5-5": _p(8, 40, 0.05),
    "claude-opus-5": _p(10, 50),
    "claude-opus-4-8": _p(10, 50),
}
# Current-generation lineup for the dashboard's "what if it all ran on X" table.
WHATIF_MODELS = ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
US_ONLY_MULT = 1.1  # inference_geo "us" on 4.6+ models
WEB_SEARCH_PER_REQUEST = 10 / 1000

_DATE_SUFFIX = re.compile(r"-\d{8}$")


def canonical_model(model):
    return _DATE_SUFFIX.sub("", model or "unknown")


def display_model(model):
    m = canonical_model(model)
    hit = re.match(r"claude-(?:(\d)-(\d)-)?([a-z]+)(?:-(\d+))?(?:-(\d+))?$", m)
    if not hit:
        return m
    old_major, old_minor, family, major, minor = hit.groups()
    if old_major:  # claude-3-5-sonnet
        return f"{family.title()} {old_major}.{old_minor}"
    ver = major + (f".{minor}" if minor else "") if major else ""
    return f"{family.title()} {ver}".strip()


def rates_for(model, usage):
    m = canonical_model(model)
    base = PRICES.get(m)
    if base is None:
        return None
    if usage.get("speed") == "fast" and m in FAST_MODE:
        base = FAST_MODE[m]
    if m in LONG_PROMPT_TIER:
        limit, tier = LONG_PROMPT_TIER[m]
        if prompt_tokens(usage) > limit:
            base = tier
    if usage.get("inference_geo") == "us":
        base = {k: v * US_ONLY_MULT for k, v in base.items()}
    return base


def token_parts(u):
    """(input, output, cache_read, write_5m, write_1h) for one API call."""
    cc = u.get("cache_creation") or {}
    w_total = u.get("cache_creation_input_tokens") or 0
    w5 = cc.get("ephemeral_5m_input_tokens") or 0
    w1 = cc.get("ephemeral_1h_input_tokens") or 0
    if not cc:  # older logs: no split, assume the 5-minute default
        w5 = w_total
    return (u.get("input_tokens") or 0, u.get("output_tokens") or 0,
            u.get("cache_read_input_tokens") or 0, w5, w1)


def prompt_tokens(u):
    i, _, r, w5, w1 = token_parts(u)
    return i + r + w5 + w1


def call_cost(model, u):
    r = rates_for(model, u)
    if r is None:
        return None
    i, o, cr, w5, w1 = token_parts(u)
    searches = ((u.get("server_tool_use") or {}).get("web_search_requests") or 0)
    return (i * r["in"] + o * r["out"] + cr * r["read"] + w5 * r["w5"] + w1 * r["w1"]) / 1e6 \
        + searches * WEB_SEARCH_PER_REQUEST


# ---------------------------------------------------------------------------
# Prompt classification. Deterministic keyword rules; good enough to answer
# "what kind of work am I spending on" without any ML dependency.
# ---------------------------------------------------------------------------
# Anchored types win outright; the rest pick whichever intent word appears
# first in the prompt ("create X so I can test Y" is a build, not a test).
ANCHORED_TYPES = [
    ("Slash command", re.compile(r"^/\S")),
    ("Follow-up / confirm", re.compile(
        r"^(y|yes|yep|ok|okay|go|go ahead|sure|do it|proceed|continue|next|done|thanks?|great|perfect|lgtm|"
        r"approved?|i approve|finish|keep going|that('s| is) (good|great|fine)|looks good|sounds good|"
        r"stop|try again|again|retry|[0-9])\b"), 80),
]
INTENT_TYPES = [
    ("Fix / debug", r"\b(fix|bug|errors?|broken|fail(s|ing|ed)?|crash(es|ed)?|traceback|exception|debug|"
                    r"not working|(isn'?t|aren'?t|doesn'?t|don'?t|won'?t|can'?t) (work(s|ing)?|show(s|ing)?|load(s|ing)?|see|find)|"
                    r"not when|it'?s not there|wrong|missing|still (not|broken|shows?))\b"),
    ("Tweak / improve", r"\b(improve|tweak|adjust|too (small|big|large|much|long|short|many)|design|layout|"
                        r"styl(e|ing)|clearer|polish|better|should (be|have|always|show|not)|instead)\b"),
    ("Refactor / cleanup", r"\b(refactor|clean ?up|simplify|rename|restructure|rethink|reorganize|optimi[sz]e|"
                           r"remove|delete|dedupe)\b"),
    ("Git / ship", r"\b(commit|push|pull request|pr|merge|rebase|deploy|release|publish|ship|upload)\b"),
    ("Review / test", r"\b(review|tests?|verify|audit|lint|validate)\b"),
    ("Docs / writing", r"\b(readme|docs?|documentation|blog|post|linkedin|email|write ?up|article|"
                       r"summary|summari[sz]e|handover)\b"),
    ("Research / lookup", r"\b(find|look (at|for|into)|search|investigate|analy[sz]e|compare|research|"
                          r"give me|show me|get me|list|check)\b"),
    ("Build / feature", r"\b(add|create|build|implement|make|scaffold|generate|set ?up|new|integrate|support|"
                        r"i want|i'?d like|i need|allow|enable)\b"),
    ("Question / explain", r"(\?|^(what|why|how|can|could|does|do|is|are|where|which|explain|tell me)\b)"),
]
INTENT_RX = [(n, re.compile(rx)) for n, rx in INTENT_TYPES]
TASK_TYPE_NAMES = [a[0] for a in ANCHORED_TYPES] + [n for n, _ in INTENT_TYPES] + ["Other"]


def classify(text):
    t = " ".join((text or "").strip().lower().split())
    if t.startswith("/"):
        return "Slash command"
    _, rx, maxlen = ANCHORED_TYPES[1]
    if len(t) <= maxlen and rx.search(t):
        return "Follow-up / confirm"
    best, best_pos = "Other", None
    for name, rx in INTENT_RX:
        m = rx.search(t)
        if m and (best_pos is None or m.start() < best_pos):
            best, best_pos = name, m.start()
    return best


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------
SYNTHETIC = ("<local-command-", "<command-message>", "[Request interrupted", "<system-reminder>",
             "Caveat:", "<user-prompt-submit-hook>", "<bash-stdout>", "<bash-stderr>")
CONTINUATION = ("<task-notification>", "This session is being continued")
PASTED_RX = re.compile(r"<pasted_content\b[^>]*>(?:.*?</pasted_content>|.*$)", re.S)
CMD_RX = re.compile(r"<command-name>\s*(/?[^<\s]+)\s*</command-name>(?:.*?<command-args>(.*?)</command-args>)?", re.S)


def prompt_text(rec):
    """Return (text, kind) for a user record a human actually typed, else (None, reason)."""
    if rec.get("isMeta") or rec.get("isCompactSummary") or rec.get("isSidechain"):
        return None, "meta"
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, list):
        texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
        if not texts:
            return None, "tool_result"
        c = "\n".join(texts)
    if not isinstance(c, str) or not c.strip():
        return None, "empty"
    s = c.strip()
    m = CMD_RX.search(s)
    if m:
        name = m.group(1) if m.group(1).startswith("/") else "/" + m.group(1)
        args = (m.group(2) or "").strip()
        return (f"{name} {args}".strip()), "command"
    if s.startswith(CONTINUATION):
        return None, "continuation"
    if s.startswith(SYNTHETIC):
        return None, "synthetic"
    s = PASTED_RX.sub("[pasted text] ", s)
    s = re.sub(r"<system-reminder>.*?</system-reminder>", "", s, flags=re.S).strip()
    return (s or "[pasted text]"), "prompt"


def parse_ts(ts):
    if not ts:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def iter_records(path):
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            # Cheap pre-filter: skip the bulky request-blob records unparsed.
            if '"api-request' in line[:80]:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


class Task:
    __slots__ = ("id", "session", "ts", "end", "text", "kind", "calls", "sub_calls", "subagents",
                 "tools", "errors", "ctx_peak", "models", "ctx_buckets", "unpriced")

    def __init__(self, tid, session, ts, text, kind):
        self.id, self.session, self.ts, self.end = tid, session, ts, ts
        self.text, self.kind = text, kind
        self.calls = self.sub_calls = 0
        self.subagents = Counter()
        self.tools = defaultdict(lambda: [0, 0])  # name -> [calls, errors]
        self.errors = 0
        self.ctx_peak = 0
        self.models = defaultdict(lambda: [0.0, 0, 0, 0, 0, 0, 0])  # cost,in,out,read,w5,w1,calls
        self.ctx_buckets = [[0, 0.0] for _ in CTX_BUCKETS]
        self.unpriced = Counter()

    @property
    def cost(self):
        return sum(v[0] for v in self.models.values())


CTX_BUCKETS = [(0, 50_000, "< 50K"), (50_000, 100_000, "50K to 100K"), (100_000, 200_000, "100K to 200K"),
               (200_000, 400_000, "200K to 400K"), (400_000, float("inf"), "400K +")]


def ctx_bucket(n):
    for i, (lo, hi, _) in enumerate(CTX_BUCKETS):
        if lo <= n < hi:
            return i
    return len(CTX_BUCKETS) - 1


def add_call(task, model, usage, ts, sub=False):
    cost = call_cost(model, usage)
    m = canonical_model(model)
    parts = token_parts(usage)
    row = task.models[m]
    if cost is None:
        task.unpriced[m] += 1
        cost = 0.0
    row[0] += cost
    for k in range(5):
        row[1 + k] += parts[k]
    row[6] += 1
    ctx = prompt_tokens(usage)
    task.ctx_peak = max(task.ctx_peak, ctx)
    b = task.ctx_buckets[ctx_bucket(ctx)]
    b[0] += 1
    b[1] += cost
    if sub:
        task.sub_calls += 1
    else:
        task.calls += 1
    if ts and (task.end is None or ts > task.end):
        task.end = ts


def parse_session(path, seen=None):
    """Parse one main session file plus its subagent logs into a session dict and task list.

    `seen` is shared across files: forked/continued sessions copy earlier
    messages into the new transcript, so an API call is only billed once."""
    seen = set() if seen is None else seen

    def first_time(key):
        if key[0] is None:
            return True
        if key in seen:
            return False
        seen.add(key)
        return True

    sid = os.path.basename(path)[:-6]
    sess = {"id": sid, "cwd": Counter(), "title": None, "ai_title": None, "branch": None, "version": None,
            "prs": [], "cc_cost": None, "cc_models": {}, "lines_add": 0, "lines_del": 0, "entry": None}
    tasks, by_prompt_id = [], {}
    current = None
    calls = {}          # (msg id, request id) -> (task, model, usage, ts); last record wins
    tool_owner = {}     # tool_use id -> (task, tool name)

    def new_task(key, ts, text, kind):
        nonlocal current
        current = Task(key, sid, ts, text, kind)
        tasks.append(current)
        if key:
            by_prompt_id[key] = current
        return current

    for rec in iter_records(path):
        t = rec.get("type")
        if t == "ai-title":
            sess["ai_title"] = rec.get("aiTitle")
        elif t == "custom-title":
            sess["title"] = rec.get("customTitle")
        elif t == "pr-link" and rec.get("prUrl"):
            if rec["prUrl"] not in sess["prs"]:
                sess["prs"].append(rec["prUrl"])
        elif t == "cost-state":
            sess["cc_cost"] = rec.get("totalCostUSD")
            sess["cc_models"] = rec.get("modelUsage") or {}
            sess["lines_add"] = rec.get("totalLinesAdded") or 0
            sess["lines_del"] = rec.get("totalLinesRemoved") or 0
        if t not in ("user", "assistant"):
            continue
        if rec.get("cwd"):
            sess["cwd"][rec["cwd"]] += 1
        sess["branch"] = rec.get("gitBranch") or sess["branch"]
        sess["version"] = rec.get("version") or sess["version"]
        sess["entry"] = sess["entry"] or rec.get("entrypoint")
        ts = parse_ts(rec.get("timestamp"))
        msg = rec.get("message") or {}

        if t == "user":
            text, kind = prompt_text(rec)
            pid = rec.get("promptId")
            if text is not None:
                if pid and pid in by_prompt_id:
                    current = by_prompt_id[pid]
                    if current.kind == "command" and kind == "prompt":
                        current.text, current.kind = text, kind
                else:
                    new_task(pid, ts, text, kind)
            elif pid and pid in by_prompt_id:
                current = by_prompt_id[pid]
            content = msg.get("content")
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                        owner = tool_owner.get(b.get("tool_use_id"))
                        if owner:
                            owner[0].tools[owner[1]][1] += 1
                            owner[0].errors += 1
        else:
            if current is None:
                new_task(None, ts, "(session resumed or started without a prompt)", "other")
            key = (msg.get("id"), rec.get("requestId"))
            calls[key] = (current, msg.get("model"), msg.get("usage") or {}, ts)
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") not in tool_owner:
                    name = b.get("name") or "unknown"
                    tool_owner[b.get("id")] = (current, name)
                    current.tools[name][0] += 1

    copied = defaultdict(float)  # cost of calls this file inherited from a parent session
    for key, (task, model, usage, ts) in calls.items():
        if model == "<synthetic>":
            continue
        if not first_time(key):
            copied[canonical_model(model)] += call_cost(model, usage) or 0
            continue
        add_call(task, model, usage, ts)

    # Subagents: their records carry the promptId of the task that launched them.
    sub_dir = os.path.join(os.path.dirname(path), sid, "subagents")
    for spath in sorted(glob.glob(os.path.join(sub_dir, "*.jsonl"))):
        agent_type = "subagent"
        try:
            with open(spath[:-6] + ".meta.json") as fh:
                agent_type = json.load(fh).get("agentType") or agent_type
        except Exception:
            pass
        owner, scalls = None, {}
        for rec in iter_records(spath):
            if owner is None and rec.get("promptId") in by_prompt_id:
                owner = by_prompt_id[rec["promptId"]]
            if rec.get("type") == "assistant":
                msg = rec.get("message") or {}
                scalls[(msg.get("id"), rec.get("requestId"))] = (msg.get("model"), msg.get("usage") or {},
                                                                 parse_ts(rec.get("timestamp")), msg)
        if not scalls:
            continue
        if owner is None:
            owner = tasks[-1] if tasks else new_task(None, None, "(subagent with no parent prompt)", "other")
        owner.subagents[agent_type] += 1
        seen_tools = set()
        for key, (model, usage, ts, msg) in scalls.items():
            if model == "<synthetic>":
                continue
            if not first_time(key):
                copied[canonical_model(model)] += call_cost(model, usage) or 0
                continue
            add_call(owner, model, usage, ts, sub=True)
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") not in seen_tools:
                    seen_tools.add(b.get("id"))
                    owner.tools[b.get("name") or "unknown"][0] += 1

    # Some calls never get a transcript record (session titles, "while you were
    # away" recaps, classifiers), but Claude Code's own cost tracker counts them.
    # Book the difference per model as a separate background line so totals
    # reconcile without inflating any real task.
    sess["background"] = 0.0
    sess["copied"] = sum(copied.values())
    if sess["cc_models"] and tasks:
        # Claude Code's tracker carries a parent's cost into a fork, so compare
        # like for like: this file's calls including the copied ones.
        ours = defaultdict(lambda: [0.0, 0, 0, 0, 0])
        for m, c in copied.items():
            ours[m][0] += c
        for tk in tasks:
            for m, v in tk.models.items():
                o = ours[m]
                o[0] += v[0]; o[1] += v[1]; o[2] += v[2]; o[3] += v[3]; o[4] += v[4] + v[5]
        bg = None
        for m, u in sess["cc_models"].items():
            m = canonical_model(m)
            delta = (u.get("costUSD") or 0) - ours[m][0]
            if delta <= 0.0005:
                continue
            if bg is None:
                end = max((tk.end for tk in tasks if tk.end), default=None)
                bg = Task(None, sid, end, "(Background calls: titles, away recaps, compaction)", "background")
                tasks.append(bg)
            row = bg.models[m]
            row[0] += delta
            row[1] += max(0, (u.get("inputTokens") or 0) - ours[m][1])
            row[2] += max(0, (u.get("outputTokens") or 0) - ours[m][2])
            row[3] += max(0, (u.get("cacheReadInputTokens") or 0) - ours[m][3])
            row[5] += max(0, (u.get("cacheCreationInputTokens") or 0) - ours[m][4])
            sess["background"] += delta
    return sess, tasks


def find_session_files(base):
    """Oldest first, so the original session owns any calls a fork copied."""
    def born(p):
        st = os.stat(p)
        return getattr(st, "st_birthtime", st.st_mtime)
    return sorted(glob.glob(os.path.join(base, "*", "*.jsonl")), key=born)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def short_path(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home) else path


def build(base, since=None, until=None, project=None, redact=False):
    files = find_session_files(base)
    sessions, tasks, warnings = [], [], []
    seen = set()
    for f in files:
        try:
            s, ts = parse_session(f, seen)
        except Exception as e:  # never let one corrupt log kill the report
            warnings.append(f"skipped {os.path.basename(f)}: {e}")
            continue
        if not ts:
            continue
        s["path"] = s["cwd"].most_common(1)[0][0] if s["cwd"] else os.path.basename(os.path.dirname(f))
        sessions.append(s)
        tasks.extend(ts)

    # project filter
    if project:
        want = os.path.abspath(os.path.expanduser(project)) if (project in (".", "..") or "/" in project or project.startswith("~")) else None
        def keep(s):
            if want:
                return s["path"] == want or s["path"].startswith(want.rstrip("/") + "/")
            return project.lower() in s["path"].lower()
        ids = {s["id"] for s in sessions if keep(s)}
        sessions = [s for s in sessions if s["id"] in ids]
        tasks = [t for t in tasks if t.session in ids]

    if since or until:
        def in_range(t):
            if t.ts is None:
                return False
            return (since is None or t.ts >= since) and (until is None or t.ts <= until)
        tasks = [t for t in tasks if in_range(t)]
        live = {t.session for t in tasks}
        sessions = [s for s in sessions if s["id"] in live]

    # project names: basename, disambiguated with parent dir when needed
    paths = sorted({s["path"] for s in sessions})
    base_count = Counter(os.path.basename(p.rstrip("/")) or p for p in paths)
    proj_name = {}
    for p in paths:
        b = os.path.basename(p.rstrip("/")) or p
        proj_name[p] = b if base_count[b] == 1 else "/".join(p.rstrip("/").split("/")[-2:])
    projects = [{"name": proj_name[p], "path": short_path(p)} for p in paths]
    pidx = {p: i for i, p in enumerate(paths)}

    # model ordering by total cost decides color slots (stable for the whole report)
    model_cost = Counter()
    model_calls = Counter()
    for t in tasks:
        for m, v in t.models.items():
            model_cost[m] += v[0]
            model_calls[m] += v[6]
    model_ids = sorted(model_cost, key=lambda m: (-model_cost[m], -model_calls[m]))
    models = []
    for i, m in enumerate(model_ids):
        priced = m in PRICES
        models.append({"id": m, "name": display_model(m) if priced or m.startswith("claude") else m,
                       "priced": priced, "rates": PRICES.get(m)})
    midx = {m: i for i, m in enumerate(model_ids)}

    sidx = {}
    out_sessions = []
    for s in sorted(sessions, key=lambda s: s["id"]):
        sidx[s["id"]] = len(out_sessions)
        title = None if redact else (s["title"] or s["ai_title"])
        out_sessions.append({
            "id": s["id"], "p": pidx[s["path"]], "title": title, "branch": s["branch"],
            "prs": s["prs"], "cc": s["cc_cost"], "add": s["lines_add"], "del": s["lines_del"],
            "bg": round(s["background"], 6), "v": s["version"],
        })

    out_tasks = []
    for t in sorted(tasks, key=lambda t: t.ts or datetime.min.replace(tzinfo=timezone.utc)):
        text = t.text or ""
        out_tasks.append({
            "s": sidx[t.session],
            "ts": t.ts.isoformat() if t.ts else None,
            "dur": round((t.end - t.ts).total_seconds()) if (t.ts and t.end) else 0,
            "text": (("[redacted]" if t.kind == "prompt" else text.split(" ")[0]) if redact and t.kind in ("prompt", "command")
                     else text[:400]),
            "cat": {"command": "Slash command", "background": "Background"}.get(t.kind) or classify(text),
            "bg": 1 if t.kind == "background" else 0,
            "calls": t.calls, "sub": t.sub_calls, "agents": dict(t.subagents),
            "errs": t.errors, "ctx": t.ctx_peak,
            "tools": {k: v for k, v in t.tools.items()},
            "m": {str(midx[m]): [round(v[0], 6)] + v[1:] for m, v in t.models.items()},
            "cb": [[c, round(x, 6)] for c, x in t.ctx_buckets],
        })

    # Reconciliation against Claude Code's own tracker, for sessions fully in scope
    recon = None
    if not (since or until):
        ours = defaultdict(float)
        for t in tasks:
            ours[t.session] += t.cost
        pairs = [(ours[s["id"]] + s["copied"], s["cc_cost"]) for s in sessions if s["cc_cost"]]
        if pairs:
            a, b = sum(x for x, _ in pairs), sum(y for _, y in pairs)
            recon = {"sessions": len(pairs), "ours": a, "claude_code": b,
                     "background": sum(s["background"] for s in sessions)}

    return {
        "meta": {
            "version": VERSION, "generated": datetime.now(timezone.utc).isoformat(),
            "data_dir": short_path(base), "files": len(files),
            "since": since.isoformat() if since else None, "until": until.isoformat() if until else None,
            "project_filter": project, "redacted": redact,
            "pricing_source": PRICING_SOURCE, "pricing_checked": PRICING_CHECKED,
            "warnings": warnings[:20], "recon": recon,
            "ctx_buckets": [b[2] for b in CTX_BUCKETS],
            "whatif": [{"id": m, "name": display_model(m), "rates": PRICES[m]} for m in WHATIF_MODELS],
        },
        "models": models, "projects": projects, "sessions": out_sessions, "tasks": out_tasks,
    }


# ---------------------------------------------------------------------------
# Terminal report
# ---------------------------------------------------------------------------
class C:
    on = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    B = "\033[1m" if on else ""
    D = "\033[2m" if on else ""
    G = "\033[32m" if on else ""
    Y = "\033[33m" if on else ""
    CY = "\033[36m" if on else ""
    R = "\033[0m" if on else ""


def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def money(x):
    if x >= 1000:
        return f"${x:,.0f}"
    if x >= 100:
        return f"${x:,.1f}"
    return f"${x:,.2f}"


def bar(frac, width=18):
    full = frac * width
    n = int(full)
    rem = "▏▎▍▌▋▊▉"[int((full - n) * 7)] if full - n > 0.07 and n < width else ""
    return ("█" * n + rem).ljust(width)


def trunc(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def summarize(data):
    """Python-side rollups used by the terminal report and --json."""
    models, projects, sessions, tasks = data["models"], data["projects"], data["sessions"], data["tasks"]
    by_model = defaultdict(lambda: [0.0, 0])
    by_proj = defaultdict(lambda: {"cost": 0.0, "tasks": 0, "sessions": set(), "models": Counter()})
    days = set()
    cache = [0, 0, 0]  # read, uncached input, writes
    sub_cost = 0.0
    turns = []
    for t in tasks:
        cost = sum(v[0] for v in t["m"].values())
        p = by_proj[sessions[t["s"]]["p"]]
        p["cost"] += cost
        p["tasks"] += 1
        p["sessions"].add(t["s"])
        for mi, v in t["m"].items():
            by_model[int(mi)][0] += v[0]
            by_model[int(mi)][1] += v[6]
            p["models"][int(mi)] += v[0]
            cache[0] += v[3]
            cache[1] += v[1]
            cache[2] += v[4] + v[5]
        if t["ts"]:
            days.add(datetime.fromisoformat(t["ts"]).astimezone().date())
        total_calls = t["calls"] + t["sub"]
        if total_calls and t["sub"]:
            # approximate subagent share of this task's cost by call share
            sub_cost += cost * t["sub"] / total_calls
        if t["calls"] and not t.get("bg") and t["text"] and not t["text"].startswith("("):
            turns.append(t["calls"])
    total = sum(v[0] for v in by_model.values())
    return {
        "total": total, "days": sorted(days), "by_model": by_model, "by_proj": by_proj,
        "cache_hit": cache[0] / max(1, sum(cache)), "sub_cost": sub_cost,
        "median_turns": statistics.median(turns) if turns else 0,
        "p90_turns": sorted(turns)[int(len(turns) * 0.9)] if turns else 0,
    }


def print_report(data, out_path):
    S = summarize(data)
    models, projects, sessions, tasks = data["models"], data["projects"], data["sessions"], data["tasks"]
    total = S["total"]
    days = S["days"]
    w = 78
    rule = C.D + "─" * w + C.R
    span = f"{days[0]:%b} {days[0].day} to {days[-1]:%b} {days[-1].day}, {days[-1].year}" if days else "no activity"
    scope = []
    if data["meta"]["project_filter"]:
        scope.append(f"project ~ {data['meta']['project_filter']}")
    print()
    n_tasks = sum(1 for t in tasks if not t.get("bg"))
    print(f"{C.B}Claude Code usage{C.R}  {C.D}{span} · {plural(len(sessions), 'session')} · {plural(n_tasks, 'task')}"
          f"{' · ' + ', '.join(scope) if scope else ''}{C.R}")
    print(rule)
    per_day = total / max(1, len(days))
    print(f"  {C.B}{money(total)}{C.R} total    {money(per_day)} per active day ({plural(len(days), 'day')})    "
          f"~{money(per_day * 21)}/month at 21 working days")
    recon = data["meta"]["recon"]
    note = "API list-price equivalent, every call priced individually."
    if recon and recon["claude_code"]:
        diff = (recon["ours"] - recon["claude_code"]) / recon["claude_code"] * 100
        note += (f" Matches Claude Code's own tracker within {abs(diff):.1f}% on {recon['sessions']} sessions"
                 f" (incl. {money(recon['background'])} of background calls).")
    print(f"  {C.D}{note}{C.R}")

    print(f"\n{C.B}BY MODEL{C.R}{' ' * 34}{C.D}cost   share    calls   $/call{C.R}")
    for mi, (c, n) in sorted(S["by_model"].items(), key=lambda kv: -kv[1][0])[:8]:
        m = models[mi]
        if not m["priced"] and c < 0.01:
            continue
        share = c / total if total else 0
        print(f"  {trunc(m['name'], 16):<16} {C.CY}{bar(share)}{C.R} {money(c):>9} {share:>6.1%} {n:>8,}  "
              f"{money(c / n) if n else '':>7}")

    print(f"\n{C.B}BY PROJECT{C.R}{' ' * 32}{C.D}cost   share  sessions  tasks   $/task{C.R}")
    for pi, p in sorted(S["by_proj"].items(), key=lambda kv: -kv[1]["cost"])[:10]:
        share = p["cost"] / total if total else 0
        print(f"  {trunc(projects[pi]['name'], 16):<16} {C.CY}{bar(share)}{C.R} {money(p['cost']):>9} {share:>6.1%}"
              f" {len(p['sessions']):>8} {p['tasks']:>6}  {money(p['cost'] / max(1, p['tasks'])):>7}")
    if len(S["by_proj"]) > 10:
        print(f"  {C.D}+ {len(S['by_proj']) - 10} more in the dashboard{C.R}")

    print(f"\n{C.B}COSTLIEST TASKS{C.R}  {C.D}(one prompt and everything Claude did for it){C.R}")
    top = sorted((t for t in tasks if not t.get("bg")), key=lambda t: -sum(v[0] for v in t["m"].values()))[:8]
    for t in top:
        c = sum(v[0] for v in t["m"].values())
        proj = projects[sessions[t["s"]]["p"]]["name"]
        dt = datetime.fromisoformat(t["ts"]).astimezone() if t["ts"] else None
        day = f"{dt:%b} {dt.day}" if dt else ""
        turns = f"{t['calls']} turns" + (f" +{t['sub']} sub" if t["sub"] else "")
        print(f"  {money(c):>8}  {turns:<16} {trunc(proj, 14):<14} {C.D}{day:>6}{C.R}  \"{trunc(t['text'], 30)}\"")

    print(f"\n{C.B}WHAT STANDS OUT{C.R}")
    for line in insights_text(data, S):
        print(f"  {C.Y}•{C.R} {line}")
    print(rule)
    if out_path:
        print(f"  Dashboard: {C.B}{out_path}{C.R}")
    if data["meta"]["warnings"]:
        print(f"  {C.D}{len(data['meta']['warnings'])} log file(s) skipped; see the dashboard footer.{C.R}")
    print()


def insights_text(data, S):
    models, tasks = data["models"], data["tasks"]
    total = S["total"] or 1
    out = []
    if S["by_model"]:
        mi, (c, _) = max(S["by_model"].items(), key=lambda kv: kv[1][0])
        out.append(f"{models[mi]['name']} is {c / total:.0%} of spend ({money(c)}).")
    costs = sorted((sum(v[0] for v in t["m"].values()) for t in tasks if not t.get("bg")), reverse=True)
    if len(costs) >= 20:
        top = max(1, len(costs) // 20)
        out.append(f"Your top 5% of tasks ({top}) cost {sum(costs[:top]) / total:.0%} of the total. "
                   f"The median task costs {money(statistics.median(costs))}.")
    if S["median_turns"]:
        out.append(f"A typical task takes {S['median_turns']:.0f} turns; 1 in 10 takes {S['p90_turns']}+.")
    big = sum(t["cb"][i][1] for t in tasks for i in (3, 4))
    if big / total > 0.15:
        out.append(f"{big / total:.0%} of spend came from calls carrying 200K+ tokens of context. "
                   f"Use /clear between unrelated tasks to stop re-reading old context.")
    if S["sub_cost"] / total > 0.05:
        out.append(f"Subagents account for roughly {S['sub_cost'] / total:.0%} of spend.")
    out.append(f"{S['cache_hit']:.1%} of input tokens were cache hits (billed at 5 to 10% of the input rate).")
    return out


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def write_html(data, path):
    here = os.path.dirname(os.path.abspath(__file__))
    tpl_path = os.path.join(here, "dashboard.html")
    with open(tpl_path, encoding="utf-8") as fh:
        tpl = fh.read()
    payload = json.dumps(data, separators=(",", ":"), default=str).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", payload)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)


def parse_day(s, end=False):
    dt = parse_ts(s)
    if dt is None:
        raise argparse.ArgumentTypeError(f"not a date: {s!r} (use YYYY-MM-DD)")
    if end and len(s) <= 10:
        dt = dt + timedelta(days=1) - timedelta(microseconds=1)
    if len(s) <= 10:  # bare date means local midnight
        dt = dt.replace(tzinfo=None).astimezone()
    return dt


def main():
    ap = argparse.ArgumentParser(
        prog="claude_usage.py",
        description="See where your Claude Code money goes: cost by model, project, task, and day.",
        epilog="Examples:\n  python3 claude_usage.py\n  python3 claude_usage.py --days 7\n"
               "  python3 claude_usage.py --project . --since 2026-10-01\n"
               "  python3 claude_usage.py --json usage.json --no-open",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=float, help="only the last N days")
    ap.add_argument("--since", type=parse_day, help="start date, YYYY-MM-DD")
    ap.add_argument("--until", type=lambda s: parse_day(s, end=True), help="end date, YYYY-MM-DD (inclusive)")
    ap.add_argument("--project", help="'.' for the current folder, a path, or part of a project name")
    ap.add_argument("--out", default=os.path.expanduser("~/.claude/usage-report.html"),
                    help="where to write the dashboard (default: ~/.claude/usage-report.html)")
    ap.add_argument("--no-open", action="store_true", help="don't open the dashboard in a browser")
    ap.add_argument("--no-html", action="store_true", help="terminal summary only")
    ap.add_argument("--json", metavar="PATH", help="also write the raw data as JSON ('-' for stdout)")
    ap.add_argument("--redact", action="store_true", help="hide prompt text (safe to share the dashboard)")
    ap.add_argument("--dir", default=None, help="Claude Code projects dir (default: ~/.claude/projects)")
    args = ap.parse_args()

    base = args.dir or os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")), "projects")
    if not os.path.isdir(base):
        sys.exit(f"No Claude Code logs found at {base}. Use --dir to point at your projects folder.")
    since = args.since
    if since is None and args.days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)

    quiet_json = args.json == "-"
    if not quiet_json and sys.stderr.isatty():
        print(f"{C.D}Reading {short_path(base)} …{C.R}", file=sys.stderr, end="\r")
    if not find_session_files(base):
        sys.exit(f"No Claude Code sessions found in {base}. Run Claude Code at least once, or use --dir.")
    data = build(base, since=since, until=args.until, project=args.project, redact=args.redact)
    if not data["tasks"]:
        sys.exit("No activity matches those filters.")

    if args.json:
        blob = json.dumps(data, indent=1, default=str)
        if quiet_json:
            print(blob)
            return
        with open(args.json, "w") as fh:
            fh.write(blob)

    out = None
    if not args.no_html:
        out = os.path.abspath(os.path.expanduser(args.out))
        write_html(data, out)
    print_report(data, out)
    if out and not args.no_open:
        webbrowser.open("file://" + out)


if __name__ == "__main__":
    main()
