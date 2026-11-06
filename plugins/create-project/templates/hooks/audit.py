#!/usr/bin/env python3
"""Mode 4 PostToolUse hook: append one JSON line per tool call to .claude/audit.jsonl. Never blocks."""
import json
import os
import sys
import time

try:
    data = json.load(sys.stdin)
    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    ti = data.get("tool_input") or {}
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "session": data.get("session_id"),
             "tool": data.get("tool_name"),
             "input": {k: (v[:300] if isinstance(v, str) else v) for k, v in ti.items()
                       if k in ("command", "file_path", "path", "pattern", "description", "url")}}
    with open(os.path.join(root, ".claude", "audit.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
except Exception:
    pass
sys.exit(0)
