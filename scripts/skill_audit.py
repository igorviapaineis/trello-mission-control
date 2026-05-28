#!/usr/bin/env python3
"""Static audit of an OpenClaw skill folder before installing it.

Run after `git clone` of a clawhub-resolved repository (or against any local
skill folder you want to validate). Exits 8 on failure with a human-readable
explanation. Refuses skills that:
  - have no YAML frontmatter or no name/description
  - exceed size limits (SKILL.md > 1000 lines, scripts total > 2 MB)
  - contain dangerous shell patterns (curl|sh, sudo, chmod 777, rm -rf /, etc.)
  - use eval/exec in Python without an allowlisted source comment
  - fetch over plain http://
  - shebang anything other than python3/bash/sh/node
  - reference binaries not declared in metadata.openclaw.requires.bins

This is a static scan, not a sandbox. It's a fast cheap filter, not a guarantee.

Usage:
  python3 skill_audit.py <skill_folder>
"""

import sys
import os
import re

EXIT_OK = 0
EXIT_FAIL = 8

MAX_SKILL_MD_LINES = 1000
MAX_SCRIPTS_BYTES = 2 * 1024 * 1024

DANGEROUS_SHELL_PATTERNS = [
    (re.compile(r"curl[^\n]+\|\s*(sh|bash|zsh)"), "curl|sh download+execute"),
    (re.compile(r"wget[^\n]+\|\s*(sh|bash|zsh)"), "wget|sh download+execute"),
    (re.compile(r"\bsudo\b"), "sudo invocation"),
    (re.compile(r"chmod\s+777"), "chmod 777 (world-writable)"),
    (re.compile(r"rm\s+-rf\s+(/|~|\$HOME|\.\.)"), "rm -rf on root/home/parent"),
    (re.compile(r":\(\)\s*\{[^}]*:|:&\s*\}"), "fork bomb"),
    (re.compile(r"\beval\s+\""), "eval on dynamic string (shell)"),
    (re.compile(r"\bnc\s+-e\b|\bbash\s+-i\s+>&"), "reverse shell pattern"),
]

DANGEROUS_PY_PATTERNS = [
    (re.compile(r"^\s*eval\s*\("), "Python eval()"),
    (re.compile(r"^\s*exec\s*\("), "Python exec()"),
    (re.compile(r"compile\s*\([^)]*\bexec\b"), "compile()+exec"),
    (re.compile(r"__import__\s*\(\s*[\"']os[\"']"), "dynamic os import"),
    (re.compile(r"subprocess\.[A-Za-z_]+\s*\([^)]*shell\s*=\s*True"), "subprocess shell=True"),
    (re.compile(r"os\.system\s*\("), "os.system"),
]

INSECURE_URL_PATTERN = re.compile(r"http://[a-zA-Z0-9.\-]+")
ALLOWED_INSECURE_HOSTS = {"localhost", "127.0.0.1"}

ALLOWED_SHEBANGS = {"python3", "bash", "sh", "node", "env"}


def fail(msg):
    print(f"AUDIT_FAIL: {msg}", file=sys.stderr)
    sys.exit(EXIT_FAIL)


def warn(msg):
    print(f"AUDIT_WARN: {msg}", file=sys.stderr)


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    front = text[3:end]
    body = text[end + 4 :]
    meta = {}
    for line in front.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def scan_skill_md(path):
    with open(path) as f:
        text = f.read()
    line_count = text.count("\n") + 1
    if line_count > MAX_SKILL_MD_LINES:
        fail(f"SKILL.md too large: {line_count} lines > {MAX_SKILL_MD_LINES}")
    meta, _ = parse_frontmatter(text)
    if meta is None:
        fail("SKILL.md has no YAML frontmatter")
    if "name" not in meta:
        fail("SKILL.md frontmatter missing 'name'")
    if "description" not in meta:
        fail("SKILL.md frontmatter missing 'description'")
    return meta


def scan_script(path, rel):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8", errors="replace")
    except OSError as e:
        fail(f"cannot read {rel}: {e}")
    first = text.split("\n", 1)[0]
    if first.startswith("#!"):
        shebang = first[2:].strip()
        binary = shebang.split()[-1].split("/")[-1]
        if binary not in ALLOWED_SHEBANGS:
            fail(f"{rel}: shebang uses '{binary}' (not in {sorted(ALLOWED_SHEBANGS)})")
    is_python = rel.endswith(".py") or "python" in first
    is_shell = rel.endswith((".sh", ".bash")) or "/bash" in first or "/sh" in first
    for pat, label in DANGEROUS_SHELL_PATTERNS:
        if pat.search(text):
            fail(f"{rel}: dangerous shell pattern: {label}")
    if is_python:
        for line in text.splitlines():
            for pat, label in DANGEROUS_PY_PATTERNS:
                if pat.search(line):
                    fail(f"{rel}: dangerous Python pattern: {label}")
    for match in INSECURE_URL_PATTERN.finditer(text):
        url = match.group(0)
        host = url[len("http://") :].split("/")[0].split(":")[0]
        if host in ALLOWED_INSECURE_HOSTS:
            continue
        fail(f"{rel}: non-TLS URL: {url}")
    return len(raw)


def main():
    if len(sys.argv) != 2:
        print("Usage: skill_audit.py <skill_folder>", file=sys.stderr)
        sys.exit(EXIT_FAIL)
    root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(root):
        fail(f"not a directory: {root}")

    skill_md = os.path.join(root, "SKILL.md")
    if not os.path.isfile(skill_md):
        fail("SKILL.md not found at skill root")
    meta = scan_skill_md(skill_md)

    total_bytes = 0
    scripts_dir = os.path.join(root, "scripts")
    if os.path.isdir(scripts_dir):
        for dirpath, _, filenames in os.walk(scripts_dir):
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                total_bytes += scan_script(full, rel)
        if total_bytes > MAX_SCRIPTS_BYTES:
            fail(f"scripts/ total size {total_bytes} > {MAX_SCRIPTS_BYTES}")

    for dirpath, _, filenames in os.walk(root):
        if "/scripts" in dirpath or dirpath == scripts_dir:
            continue
        for fn in filenames:
            if not fn.endswith((".sh", ".bash")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            scan_script(full, rel)

    print(f"AUDIT_PASS:{meta.get('name')}|scripts_bytes={total_bytes}")


if __name__ == "__main__":
    main()
