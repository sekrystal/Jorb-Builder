You are patching the Jorb {target_kind} repo at {target_repo}.

Task: {task_id}
Title: {title}

Objective:
{objective}

Why it matters:
{why_it_matters}

Allowed files to edit inside Jorb:
{allowlist}

Forbidden files and paths:
{forbidlist}

Implementation constraints:
- Make the smallest robust change set that satisfies the task.
- Preserve existing working behavior unless this task explicitly changes it.
- Keep hot paths deterministic and bounded.
- Do not broaden scope.
- Do not edit anything outside the target repo.
{builder_edit_constraint}
- If a test fails, fix it and rerun until green.
- Do not claim live runtime success unless directly proven.

UX conformance requirements:
{ux_conformance_requirements}

Deterministic acceptance criteria:
{acceptance}

Verification commands you must run:
{verification_commands}

Return exactly:
1. Concise summary of exactly what changed
2. Exact files changed
3. Exact tests added or updated
4. Exact commands run
5. Exact results
6. Honest note on what remains unproven
