---
description: Summarize what was done this session and how, adapting to the kind of work (code vs. docs)
---

Produce a concise "ship" summary of the work done in **this session**. First figure
out what kind of work it was, then report accordingly. Do not start new work — only
summarize what has already happened.

## 1. Detect the type of work

Look at what actually changed this session:
- If a git repo is present, run `git status --short` and `git diff --stat` (and
  `git diff` for detail) to see concrete changes.
- Otherwise, rely on the files you created/edited during this session.

Decide whether the session was primarily **code** or **document/prose** work (or
both), and shape the summary to match.

## 2. Write the summary

Always start with a one-line **TL;DR** of what was accomplished.

**If it was code work**, include:
- **What changed** — features/fixes/refactors, grouped logically (not a raw file dump).
- **How** — the approach taken, key decisions, and any notable trade-offs.
- **Files touched** — the important ones, as clickable links, with a short note each.
- **Verification** — what was run to confirm it works (builds, tests, migrations,
  manual checks) and the result. If nothing was verified, say so plainly.
- **Follow-ups** — anything left incomplete, TODOs, or known risks.

**If it was document/prose work**, include:
- **What changed** — sections added/edited/removed and the substance of the change.
- **How** — the angle, structure, or tone decisions made.
- **Files touched** — as clickable links.
- **Open questions** — anything ambiguous or left for the author to decide.

## 3. Keep it honest and tight

- Report only what genuinely happened this session — don't pad or invent.
- If tests failed or a step was skipped, say so.
- Prefer bullets over prose. No preamble like "Here is the summary" — just deliver it.

If the user passed extra context after the command, treat it as focus/scope:
$ARGUMENTS
