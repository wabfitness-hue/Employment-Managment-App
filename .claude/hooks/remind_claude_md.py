#!/usr/bin/env python3
"""
PostToolUse hook: after a Bash command that looks like a build/test/verification
step, remind Claude to check whether CLAUDE.md needs updating.

Claude Code can't detect "a feature was implemented and tested" directly (hooks
only see tool events), so this fires on the closest reliable proxy: commands
matching build/test/migration/deploy patterns used in this repo's workflow.
"""
import json
import re
import sys

TRIGGER_PATTERNS = [
    r"npm run build",
    r"npm test",
    r"pytest",
    r"docker compose build",
    r"docker compose up",
    r"alembic upgrade",
    r"docker build .*nginx",
]

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

command = (payload.get("tool_input") or {}).get("command", "") or ""

if any(re.search(p, command, re.IGNORECASE) for p in TRIGGER_PATTERNS):
    print(json.dumps({
        "decision": "block",
        "reason": (
            "Verification step just ran ('" + command.strip()[:120] + "'). "
            "If this completes a new feature (new endpoint, model/migration, "
            "page, service, or workflow) and it's been tested, update "
            "CLAUDE.md now: add/adjust the relevant section (Domain model, "
            "Services, Conventions & gotchas, etc.) so it stays accurate. "
            "If this was just an incremental step or the feature isn't done "
            "yet, ignore this reminder and continue."
        ),
    }))

sys.exit(0)
