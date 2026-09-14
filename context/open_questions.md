# open_questions - unresolved questions

Owns: open questions with their status and next step. Does NOT hold decisions (context/decisions.md) or tasks (context/todo.md).
Maintain: resolve a question by checking it and dating the outcome; do not delete.
Entry format: `- [ ] question (status: open|blocked) - next step`  /  resolved: `- [x] question (resolved YYYY-MM-DD) - outcome`
- [x] Where do the "119 fleet policies" come from, and what are their `policy_id`/`title`/`rule_text`/`level` values? (resolved 2026-09-13) - moot: the 2026-09-13 restart dropped the RFC-2119 policy engine entirely (no `policies` table in the new Python schema). Fleet-wide conventions stay in `CLAUDE.md`, not in Fleetcom.
