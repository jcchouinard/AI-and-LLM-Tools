#!/usr/bin/env python3
"""Tests for templates/hooks/token_gate.py. Run: python3 tests/test_token_gate.py"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "hooks", "token_gate.py")


def rc(data, env=None):
    raw = data if isinstance(data, str) else json.dumps(data)
    return subprocess.run([sys.executable, "-I", HOOK], input=raw, capture_output=True, text=True,
                          env=dict(os.environ, **(env or {}))).returncode


d = tempfile.mkdtemp()
open(os.path.join(d, "big.txt"), "w").write("x\n" * 400)
open(os.path.join(d, "small.txt"), "w").write("x\n" * 10)
big, small = os.path.join(d, "big.txt"), os.path.join(d, "small.txt")
cases = [
    (2, {"tool_name": "Read", "tool_input": {"file_path": big}}),
    (0, {"tool_name": "Read", "tool_input": {"file_path": big, "limit": 20}}),
    (0, {"tool_name": "Read", "tool_input": {"file_path": big, "offset": 0}}),
    (0, {"tool_name": "Read", "tool_input": {"file_path": small}}),
    (0, {"tool_name": "Read", "tool_input": {"file_path": os.path.join(d, "missing")}}),
    (2, {"tool_name": "Bash", "cwd": d, "tool_input": {"command": "cat big.txt"}}),
    (2, {"tool_name": "Bash", "cwd": d, "tool_input": {"command": "head -n 400 big.txt"}}),
    (0, {"tool_name": "Bash", "cwd": d, "tool_input": {"command": "cat big.txt | grep x"}}),
    (0, {"tool_name": "Bash", "cwd": d, "tool_input": {"command": "cat small.txt"}}),
    (0, {"tool_name": "Bash", "cwd": d, "tool_input": {"command": "ls"}}),
    (0, "not json"),
]
fails = [f"expected {want} for {data}" for want, data in cases if rc(data) != want]
if rc({"tool_name": "Read", "tool_input": {"file_path": big}}, {"MIN_LINES": "500"}) != 0:
    fails.append("MIN_LINES=500 should allow a 400-line file")
print("\n".join(fails) or "PASS")
sys.exit(1 if fails else 0)
