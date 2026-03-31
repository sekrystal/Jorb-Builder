You are debugging a failed Jorb task in {product_repo}.

Task: {task_id}
Title: {title}

Failure summary:
{failure_summary}

Allowed files to edit inside Jorb:
{allowlist}

Forbidden files and paths:
{forbidlist}

Requirements:
- Reproduce or inspect the failure first if needed.
- Patch narrowly.
- Narrow to the true failure boundary, not just the easiest visible symptom.
- Rerun the failing verification first.
- Then rerun the full required verification.
- Stop only when green or when you identify a real blocker.
- Do not broaden beyond the declared task contract.
- Do not claim success if UI behavior, backend semantics, and persistence still disagree for a product task.
- Do not claim runtime success you did not prove.

Verification commands:
{verification_commands}

Return exactly:
1. Concise summary of exactly what changed
2. Exact files changed
3. Exact tests added or updated
4. Exact commands run
5. Exact results
6. Honest note on what remains unproven
