# open_questions - unresolved questions

Owns: open questions with their status and next step. Does NOT hold decisions (context/decisions.md) or tasks (context/todo.md).
Maintain: resolve a question by checking it and dating the outcome; do not delete.
Entry format: `- [ ] question (status: open|blocked) - next step`  /  resolved: `- [x] question (resolved YYYY-MM-DD) - outcome`
- [ ] Where do the "119 fleet policies" come from, and what are their `policy_id`/`title`/`rule_text`/`level` values? (status: blocked) - the `policies` table and CRUD (`CreatePolicy`/`GetPolicy`/`ListPolicies`) are implemented and tested, but no source for 119 concrete policy rows was found in this repo or `~/Claude/development/orchestrator` (its `dev/features/policy.md` only has a 6-item seed ruleset). Not fabricating policy content; need the source document or export before seeding.
