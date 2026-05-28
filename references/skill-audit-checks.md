# Skill audit checks (static)

`scripts/skill_audit.py` runs before `openclaw skills install <folder>` whenever `ensure_skills.py` decides to install a clawhub skill. It is a static filter — fast and cheap — not a sandbox or behavioral analysis. It exits 8 on the first failure with a human-readable reason.

## Checks performed

### Structure

- [x] `SKILL.md` exists at the skill root.
- [x] `SKILL.md` starts with `---` YAML frontmatter.
- [x] Frontmatter contains `name` and `description`.
- [x] `SKILL.md` ≤ 1000 lines.
- [x] `scripts/` total size ≤ 2 MB.

### Shebangs

Allowed: `python3`, `bash`, `sh`, `node`, `env`. Anything else fails (`perl`, `ruby`, custom binaries, exotic interpreters).

### Dangerous shell patterns

| Pattern | Reason |
|---|---|
| `curl ... \| sh\|bash\|zsh` | download + execute |
| `wget ... \| sh\|bash\|zsh` | download + execute |
| `sudo` | privilege escalation |
| `chmod 777` | world-writable |
| `rm -rf /`, `rm -rf ~`, `rm -rf $HOME`, `rm -rf ..` | catastrophic delete |
| `:(){ ... }:&` and variants | fork bomb |
| `eval "..."` | dynamic shell eval |
| `nc -e`, `bash -i >&` | reverse shell |

### Dangerous Python patterns (per line, in `.py` files)

| Pattern | Reason |
|---|---|
| `eval(` at start of statement | dynamic eval |
| `exec(` at start of statement | dynamic exec |
| `compile(..., exec, ...)` | compile+exec |
| `__import__('os')` | dynamic os import |
| `subprocess.X(..., shell=True)` | shell injection surface |
| `os.system(` | shell out without arg-list |

### URLs

Any `http://` (non-TLS) URL fails, except `localhost` and `127.0.0.1`. Use `https://` everywhere.

## What is NOT checked

- **Behavior at runtime.** The audit cannot detect "this script does X badly", only that it doesn't contain obvious patterns.
- **Network egress.** A determined script can still reach external hosts via HTTPS — we don't block that.
- **Secrets exfiltration via legitimate-looking calls.** Heuristic regex on hard-coded `api_key=...` strings was considered but produces too many false positives. Trust + reputation (verified author on clawhub) is the better lever here.
- **Dependency manifests.** We don't inspect `package.json` / `requirements.txt`.
- **Source provenance.** Whoever owns the clawhub package owns the trust call.

## When to extend

If you find a class of malicious or buggy skill that this audit misses, add the check in `skill_audit.py` and update the table above. Patterns should be:
- regex-matchable (no AST parsing — keeps the script standalone)
- low false-positive rate (a noisy audit gets ignored)
- accompanied by a clear human-readable fail message
