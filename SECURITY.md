# Security Policy

This plugin installs and runs third-party code (skills from ClawHub) on the user's machine. The static audit in `scripts/skill_audit.py` is the first line of defence — if you find a way to bypass it, please report it privately.

## Reporting a vulnerability

Email **igor@viapaineis.com.br** with:

- A clear description of the issue.
- A proof of concept (a minimal skill that exercises the bypass, or the exact patterns that elude the scan).
- The version of the plugin (`package.json`'s `version` field) and OpenClaw you tested on.
- Your assessment of impact and any suggested fix.

Do **not** open a public GitHub issue for bypass reports. Open issues are for feature requests, bugs that don't expose users, and documentation problems.

## Response SLA

- **Acknowledgement**: within 7 days.
- **Fix for high-severity issues**: within 30 days.
- **Coordinated disclosure**: we will agree on a public disclosure date with the reporter before publishing details.

## Threat model

The plugin runs alongside OpenClaw on the user's workstation or server. Trust boundaries:

| Component | Trust |
|---|---|
| The plugin's own code (this repo) | Trusted — vetted by maintainers |
| `scripts/skill_audit.py` | Critical — static gate before installing unknown skills |
| Skills already installed by the user | User-trusted (we don't re-audit on every run) |
| Skills downloaded from ClawHub via `ensure_skills.py` | **Untrusted** until `skill_audit.py` passes |
| The Trello API endpoint | Trusted (TLS) |
| The user's `TRELLO_API_KEY` and `TRELLO_TOKEN` | Sensitive — never logged, never sent anywhere except `api.trello.com` |
| Other agents on the same machine | Per-agent allowlists in `openclaw.json` and `exec-approvals.json` restrict what each can run |

Out of scope (the plugin does not attempt to defend against these):

- A user who installs a skill outside `ensure_skills.py` (e.g. manual `openclaw skills install`).
- A user who weakens or removes the `exec-approvals.json` allowlist.
- A user who downgrades the plugin to a vulnerable older version.
- Compromise of the user's Trello account or token.
- Compromise of the ClawHub registry itself.

## Known limitations of `skill_audit.py`

By design, the audit is a **static scan**, not a runtime sandbox. It catches obvious dangerous patterns (`curl|sh`, `sudo`, `chmod 777`, `rm -rf /`, `eval`/`exec`, plain-HTTP URLs, exotic shebangs) but cannot detect every threat. Specifically, it does not:

- Run the skill in a sandbox to observe behaviour.
- Inspect dependency manifests (`package.json`, `requirements.txt`).
- Verify provenance or signature of the package.
- Defend against a skill that uses entirely legitimate-looking calls to do something harmful at runtime.

Treat the audit as a **filter, not a guarantee**. The user remains the final responsible party for choosing which skills to allow.

See `references/skill-audit-checks.md` for the complete list of static checks and what they cover.
