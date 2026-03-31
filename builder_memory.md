# Builder Memory

## Purpose
This is the durable short memory for the external Jorb builder.

## Stable truths
- The builder lives outside the Jorb repo.
- Codex in VS Code is the only implementation worker for v1.
- Every task must be bounded, verified, and resumable.
- `/leads` is known to be fast again and should not be destabilized casually.
- Discovery usefulness and discovery status truth are the current highest-value product risks.
- JORB-V1-001 is accepted based on Ubuntu VM runtime proof, including a real completed discovery cycle and correct zero-yield discovery-status surfacing.
- JORB-V1-002 is the next selected task now that JORB-V1-001 is accepted.
- JORB-INFRA-001 is queued as pending builder-side infrastructure work to automate the packet-to-VM execution loop while keeping the builder external to JORB.
- JORB-INFRA-001 is now active so builder automation can be hardened first; JORB-V1-002 is preserved but intentionally paused.
- JORB-INFRA-001 was restored from blocked to retry_ready using its existing packet at /Users/samuelkrystal/projects/jorb-builder/run_logs/2026-03-24T224108Z/codex_prompt.md.
- JORB-INFRA-001 is still retryable after the stale builder dirty-repo block and should stay active until the hardened automation path is re-exercised cleanly.
- JORB-INFRA-001 is accepted for v1 scope because the intended human_gated loop now pauses and resumes truthfully; true callable executor integration is a separate follow-on infra task.
- JORB-V1-002 is restored as the next active product task and should now run through the hardened builder loop.
- JORB-INFRA-002 is accepted: builder now has a real callable executor path via codex exec, and JORB-V1-003 is the first fresh product task to prove that live path.
- JORB-V1-005 is accepted and the current backlog has no remaining ready tasks; builder idle is now expected until new tasks are added.

## Update rule
Only add short bullets that materially change future task selection or reduce ambiguity.

- JORB-V1-001 was abandoned manually at 2026-03-24T18:44:49.996841+00:00. Reason: Clearing stale bootstrap state after operator-script validation

## Product Grounding

All tasks must align with jorb_product_spec.md.

Priority order:
1. Opportunity discovery quality
2. Opportunity intelligence (scoring, filtering, freshness)
3. Runtime correctness and observability
4. Strategy layer (lightweight, non-generative)

Explicitly deprioritize:
- coaching systems
- resume generation
- content generation

## Scope Filter
Does this directly improve:
- opportunity quality
- decision quality
- system reliability

- JORB-V1-002 blocked by automated loop via BLK-JORB-V1-002.yml. History: 2026-03-24T223418Z-JORB-V1-002.yml

- JORB-INFRA-001 refined by automated loop. History: 2026-03-24T224227Z-JORB-INFRA-001.yml

- JORB-INFRA-001 blocked by automated loop via BLK-JORB-INFRA-001.yml. History: 2026-03-24T225211Z-JORB-INFRA-001.yml

- JORB-INFRA-001 blocked by automated loop via BLK-JORB-INFRA-001.yml. History: 2026-03-24T231033Z-JORB-INFRA-001.yml

- JORB-INFRA-001 blocked by automated loop via BLK-JORB-INFRA-001.yml. History: 2026-03-24T232244Z-JORB-INFRA-001.yml

- JORB-INFRA-001 blocked by automated loop via BLK-JORB-INFRA-001.yml. History: 2026-03-24T232329Z-JORB-INFRA-001.yml

- JORB-INFRA-001 blocked by automated loop via BLK-JORB-INFRA-001.yml. History: 2026-03-24T232451Z-JORB-INFRA-001.yml

- JORB-V1-002 blocked by automated loop via BLK-JORB-V1-002.yml. History: 2026-03-25T000049Z-JORB-V1-002.yml

- JORB-V1-002 refined by automated loop. History: 2026-03-25T000544Z-JORB-V1-002.yml

- JORB-V1-002 blocked by automated loop via BLK-JORB-V1-002.yml. History: 2026-03-25T001531Z-JORB-V1-002.yml

- JORB-V1-002 blocked by automated loop via BLK-JORB-V1-002.yml. History: 2026-03-25T002156Z-JORB-V1-002.yml

- JORB-V1-002 refined by automated loop. History: 2026-03-25T002710Z-JORB-V1-002.yml

- JORB-V1-002 refined by automated loop. History: 2026-03-25T003113Z-JORB-V1-002.yml

- JORB-V1-002 refined by automated loop. History: 2026-03-25T003437Z-JORB-V1-002.yml

- JORB-V1-002 refined by automated loop. History: 2026-03-25T003828Z-JORB-V1-002.yml

- JORB-V1-002 refined by automated loop. History: 2026-03-25T004709Z-JORB-V1-002.yml

- JORB-V1-002 accepted by automated loop. History: 2026-03-25T010836Z-JORB-V1-002.yml

- JORB-V1-003 blocked by automated loop via BLK-JORB-V1-003.yml. History: 2026-03-25T013237Z-JORB-V1-003.yml

- JORB-V1-003 accepted by automated loop. History: 2026-03-25T013805Z-JORB-V1-003.yml

- JORB-V1-004 accepted by automated loop. History: 2026-03-25T022627Z-JORB-V1-004.yml

- JORB-V1-005 accepted by automated loop. History: 2026-03-25T023410Z-JORB-V1-005.yml

- JORB-V1-006 accepted by automated loop. History: 2026-03-25T043340Z-JORB-V1-006.yml

- JORB-V1-007 blocked by automated loop via BLK-JORB-V1-007.yml. History: 2026-03-25T050715Z-JORB-V1-007.yml

- JORB-V1-007 blocked by automated loop via BLK-JORB-V1-007.yml. History: 2026-03-25T050925Z-JORB-V1-007.yml

- JORB-V1-007 blocked by automated loop via BLK-JORB-V1-007.yml. History: 2026-03-25T054335Z-JORB-V1-007.yml

- JORB-V1-007 blocked by automated loop via BLK-JORB-V1-007.yml. History: 2026-03-25T062744Z-JORB-V1-007.yml

- JORB-V1-007 interrupted by operator. History: 2026-03-25T065648Z-JORB-V1-007.yml

- JORB-V1-007 blocked by automated loop via BLK-JORB-V1-007.yml. History: 2026-03-25T065849Z-JORB-V1-007.yml

- JORB-V1-007 accepted by automated loop. History: 2026-03-25T071246Z-JORB-V1-007.yml

- JORB-V1-008 accepted by automated loop. History: 2026-03-25T071753Z-JORB-V1-008.yml

- JORB-V1-009 accepted by automated loop. History: 2026-03-25T072618Z-JORB-V1-009.yml

- JORB-V1-010 accepted by automated loop. History: 2026-03-25T141943Z-JORB-V1-010.yml

- JORB-V1-011 accepted by automated loop. History: 2026-03-25T142611Z-JORB-V1-011.yml

- JORB-V1-012 accepted by automated loop. History: 2026-03-25T143952Z-JORB-V1-012.yml

- JORB-V1-014 accepted by automated loop. History: 2026-03-25T144323Z-JORB-V1-014.yml

- JORB-INFRA-003 blocked by automated loop via BLK-JORB-INFRA-003.yml. History: 2026-03-25T165554Z-JORB-INFRA-003.yml

- JORB-INFRA-003 accepted by automated loop. History: 2026-03-25T170522Z-JORB-INFRA-003.yml

- JORB-INFRA-004 accepted by automated loop. History: 2026-03-25T171455Z-JORB-INFRA-004.yml

- JORB-V1-013 accepted by automated loop. History: 2026-03-25T181726Z-JORB-V1-013.yml

- JORB-V1-015 accepted by automated loop. History: 2026-03-25T182056Z-JORB-V1-015.yml

- JORB-INFRA-005 accepted by automated loop. History: 2026-03-25T183336Z-JORB-INFRA-005.yml

- JORB-V1-016 accepted by automated loop. History: 2026-03-25T183805Z-JORB-V1-016.yml

- JORB-V1-017 accepted by automated loop. History: 2026-03-25T191959Z-JORB-V1-017.yml

- JORB-V1-018 accepted by automated loop. History: 2026-03-25T192410Z-JORB-V1-018.yml

- JORB-V2-001 accepted by automated loop. History: 2026-03-25T210316Z-JORB-V2-001.yml

- JORB-V2-002 accepted by automated loop. History: 2026-03-25T210740Z-JORB-V2-002.yml

- JORB-V2-008 blocked by automated loop via BLK-JORB-V2-008.yml. History: 2026-03-25T235939Z-JORB-V2-008.yml

- JORB-V2-008 accepted by automated loop. History: 2026-03-26T001143Z-JORB-V2-008.yml

- JORB-V2-009 accepted by automated loop. History: 2026-03-26T001929Z-JORB-V2-009.yml

- JORB-V2-005 accepted by automated loop. History: 2026-03-26T170821Z-JORB-V2-005.yml

- JORB-V2-010 accepted by automated loop. History: 2026-03-26T171736Z-JORB-V2-010.yml

- JORB-V2-011 accepted by automated loop. History: 2026-03-26T172931Z-JORB-V2-011.yml

- JORB-V2-012 refined by automated loop. History: 2026-03-26T173306Z-JORB-V2-012.yml

- JORB-V2-019 blocked by automated loop via BLK-JORB-V2-019.yml. History: 2026-03-26T175332Z-JORB-V2-019.yml

- JORB-V2-019 accepted by automated loop. History: 2026-03-26T180103Z-JORB-V2-019.yml

- JORB-V2-020 accepted by automated loop. History: 2026-03-26T180803Z-JORB-V2-020.yml

- JORB-V2-021 accepted by automated loop. History: 2026-03-26T181653Z-JORB-V2-021.yml

- JORB-V2-022 accepted by automated loop. History: 2026-03-26T182228Z-JORB-V2-022.yml

- JORB-V2-023 accepted by automated loop. History: 2026-03-26T183107Z-JORB-V2-023.yml

- JORB-V2-024 accepted by automated loop. History: 2026-03-26T183418Z-JORB-V2-024.yml

- JORB-V2-025 accepted by automated loop. History: 2026-03-26T184329Z-JORB-V2-025.yml

- JORB-V2-027 accepted by automated loop. History: 2026-03-26T185411Z-JORB-V2-027.yml

- JORB-V2-026 refined by automated loop. History: 2026-03-26T191001Z-JORB-V2-026.yml

- JORB-V2-026 refined by automated loop. History: 2026-03-26T192013Z-JORB-V2-026.yml

- JORB-V2-026 refined by automated loop. History: 2026-03-26T192146Z-JORB-V2-026.yml

- JORB-V2-026 refined by automated loop. History: 2026-03-26T193228Z-JORB-V2-026.yml

- JORB-V2-026 accepted by automated loop. History: 2026-03-26T194907Z-JORB-V2-026.yml

- JORB-INFRA-006 blocked by automated loop via BLK-JORB-INFRA-006.yml. History: 2026-03-26T200006Z-JORB-INFRA-006.yml

- JORB-INFRA-006 accepted by automated loop. History: 2026-03-26T201958Z-JORB-INFRA-006.yml

- JORB-V2-012 accepted by automated loop. History: 2026-03-26T211929Z-JORB-V2-012.yml

- JORB-V2-013 accepted by automated loop. History: 2026-03-26T212519Z-JORB-V2-013.yml

- JORB-V2-014 refined by automated loop. History: 2026-03-26T213828Z-JORB-V2-014.yml

- JORB-V2-014 refined by automated loop. History: 2026-03-26T214929Z-JORB-V2-014.yml

- JORB-V2-014 refined by automated loop. History: 2026-03-26T214933Z-JORB-V2-014.yml

- JORB-V2-014 accepted by automated loop. History: 2026-03-26T215712Z-JORB-V2-014.yml

- JORB-V2-015 accepted by automated loop. History: 2026-03-26T220310Z-JORB-V2-015.yml

- JORB-V2-016 accepted by automated loop. History: 2026-03-26T221635Z-JORB-V2-016.yml

- JORB-V2-018 accepted by automated loop. History: 2026-03-26T222153Z-JORB-V2-018.yml

- JORB-V2-003 accepted by automated loop. History: 2026-03-26T233019Z-JORB-V2-003.yml

- JORB-V2-004 accepted by automated loop. History: 2026-03-26T233301Z-JORB-V2-004.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T001005Z-JORB-V2-006.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T021707Z-JORB-V2-006.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T040557Z-JORB-V2-006.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T043051Z-JORB-V2-006.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T044741Z-JORB-V2-006.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T051656Z-JORB-V2-006.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T052837Z-JORB-V2-006.yml

- JORB-V2-006 blocked by automated loop via BLK-JORB-V2-006.yml. History: 2026-03-27T062655Z-JORB-V2-006.yml

- JORB-V2-017 blocked by automated loop via BLK-JORB-V2-017.yml. History: 2026-03-27T144426Z-JORB-V2-017.yml

- JORB-V2-017 accepted by automated loop. History: 2026-03-27T144908Z-JORB-V2-017.yml

- JORB-V2-006 refined by automated loop. History: 2026-03-27T164859Z-JORB-V2-006.yml

- JORB-V2-006 accepted by automated loop. History: 2026-03-27T165646Z-JORB-V2-006.yml

- JORB-V2-007 accepted by automated loop. History: 2026-03-27T170330Z-JORB-V2-007.yml

- JORB-V3-001 blocked by automated loop via BLK-JORB-V3-001.yml. History: 2026-03-29T190200Z-JORB-V3-001.yml

- JORB-V3-001 blocked by automated loop via BLK-JORB-V3-001.yml. History: 2026-03-29T193807Z-JORB-V3-001.yml

- JORB-V3-001 blocked by automated loop via BLK-JORB-V3-001.yml. History: 2026-03-29T194236Z-JORB-V3-001.yml

- JORB-V3-001 interrupted by operator. History: 2026-03-29T211401Z-JORB-V3-001.yml

- JORB-V3-001 accepted by automated loop. History: 2026-03-29T212218Z-JORB-V3-001.yml

- JORB-INFRA-007 blocked by automated loop via BLK-JORB-INFRA-007.yml. History: 2026-03-29T212406Z-JORB-INFRA-007.yml

- JORB-INFRA-007 interrupted by operator. History: 2026-03-29T212609Z-JORB-INFRA-007.yml

- JORB-INFRA-007 accepted by automated loop. History: 2026-03-29T213725Z-JORB-INFRA-007.yml

- JORB-INFRA-008 blocked by automated loop via BLK-JORB-INFRA-008.yml. History: 2026-03-29T214102Z-JORB-INFRA-008.yml

- JORB-INFRA-008 accepted by automated loop. History: 2026-03-29T215204Z-JORB-INFRA-008.yml

- JORB-INFRA-009 accepted by automated loop. History: 2026-03-29T220236Z-JORB-INFRA-009.yml

- JORB-V3-002 blocked by automated loop via BLK-JORB-V3-002.yml. History: 2026-03-29T222718Z-JORB-V3-002.yml

- JORB-V3-002 refined by automated loop. History: 2026-03-29T225834Z-JORB-V3-002.yml

- JORB-V3-002 refined by automated loop. History: 2026-03-29T230243Z-JORB-V3-002.yml

- JORB-V3-002 refined by automated loop. History: 2026-03-29T230400Z-JORB-V3-002.yml

- JORB-V3-002 refined by automated loop. History: 2026-03-29T231820Z-JORB-V3-002.yml

- JORB-V3-002 accepted by automated loop. History: 2026-03-29T232733Z-JORB-V3-002.yml

- JORB-V3-003 refined by automated loop. History: 2026-03-29T233141Z-JORB-V3-003.yml

- JORB-V3-003 refined by automated loop. History: 2026-03-29T234656Z-JORB-V3-003.yml

- JORB-V3-003 refined by automated loop. History: 2026-03-30T021844Z-JORB-V3-003.yml

- JORB-V3-003 refined by automated loop. History: 2026-03-30T021855Z-JORB-V3-003.yml

- JORB-V3-003 interrupted by operator. History: 2026-03-30T060618Z-JORB-V3-003.yml

- JORB-V3-003 accepted by automated loop. History: 2026-03-30T061508Z-JORB-V3-003.yml

- JORB-V3-004 accepted by automated loop. History: 2026-03-30T062021Z-JORB-V3-004.yml

- JORB-V3-005 accepted by automated loop. History: 2026-03-30T062735Z-JORB-V3-005.yml

- JORB-V3-011 accepted by automated loop. History: 2026-03-30T063344Z-JORB-V3-011.yml

- JORB-V3-012 accepted by automated loop. History: 2026-03-30T064845Z-JORB-V3-012.yml

- JORB-V3-006 refined by automated loop. History: 2026-03-30T065705Z-JORB-V3-006.yml

- JORB-V3-006 accepted by automated loop. History: 2026-03-30T070629Z-JORB-V3-006.yml

- JORB-V3-007 accepted by automated loop. History: 2026-03-30T071326Z-JORB-V3-007.yml

- JORB-V3-008 accepted by automated loop. History: 2026-03-30T072400Z-JORB-V3-008.yml

- JORB-V3-009 accepted by automated loop. History: 2026-03-30T072836Z-JORB-V3-009.yml

- JORB-V3-010 accepted by automated loop. History: 2026-03-30T075316Z-JORB-V3-010.yml

- JORB-INFRA-010 blocked by automated loop via BLK-JORB-INFRA-010.yml. History: 2026-03-30T192337Z-JORB-INFRA-010.yml

- JORB-INFRA-010 blocked by automated loop via BLK-JORB-INFRA-010.yml. History: 2026-03-30T200223Z-JORB-INFRA-010.yml

- JORB-INFRA-010 interrupted by operator. History: 2026-03-30T200609Z-JORB-INFRA-010.yml

- JORB-INFRA-010 accepted by automated loop. History: 2026-03-30T202150Z-JORB-INFRA-010.yml

- DRAFT-JORB-INFRA-STATUS-TRUTH blocked by automated loop via BLK-DRAFT-JORB-INFRA-STATUS-TRUTH.yml. History: 2026-03-30T204723Z-DRAFT-JORB-INFRA-STATUS-TRUTH.yml

- DRAFT-JORB-INFRA-STATUS-TRUTH blocked by automated loop via BLK-DRAFT-JORB-INFRA-STATUS-TRUTH.yml. History: 2026-03-30T205825Z-DRAFT-JORB-INFRA-STATUS-TRUTH.yml

- DRAFT-JORB-INFRA-STATUS-TRUTH accepted by automated loop. History: 2026-03-30T211404Z-DRAFT-JORB-INFRA-STATUS-TRUTH.yml

- JORB-INFRA-023 accepted by automated loop. History: 2026-03-30T222211Z-JORB-INFRA-023.yml

- JORB-INFRA-024 accepted by automated loop. History: 2026-03-30T225059Z-JORB-INFRA-024.yml

- JORB-INFRA-025 accepted by automated loop. History: 2026-03-30T233831Z-JORB-INFRA-025.yml

- JORB-INFRA-026 accepted by automated loop. History: 2026-03-30T234923Z-JORB-INFRA-026.yml

- JORB-INFRA-027 accepted by automated loop. History: 2026-03-31T000734Z-JORB-INFRA-027.yml

- JORB-INFRA-028 accepted by automated loop. History: 2026-03-31T001641Z-JORB-INFRA-028.yml

- JORB-INFRA-029 accepted by automated loop. History: 2026-03-31T002615Z-JORB-INFRA-029.yml

- JORB-INFRA-030 accepted by automated loop. History: 2026-03-31T003826Z-JORB-INFRA-030.yml

- JORB-INFRA-031 accepted by automated loop. History: 2026-03-31T005317Z-JORB-INFRA-031.yml

- JORB-INFRA-032 accepted by automated loop. History: 2026-03-31T010427Z-JORB-INFRA-032.yml

- JORB-INFRA-033 accepted by automated loop. History: 2026-03-31T012316Z-JORB-INFRA-033.yml

- DRAFT-JORB-INFRA-PHASE4_ARTIFACT_ENFORCEMENT_FAILED blocked by automated loop via BLK-DRAFT-JORB-INFRA-PHASE4_ARTIFACT_ENFORCEMENT_FAILED.yml. History: 2026-03-31T014204Z-DRAFT-JORB-INFRA-PHASE4_ARTIFACT_ENFORCEMENT_FAILED.yml

- DRAFT-JORB-INFRA-PHASE4_ARTIFACT_ENFORCEMENT_FAILED accepted by automated loop. History: 2026-03-31T015729Z-DRAFT-JORB-INFRA-PHASE4_ARTIFACT_ENFORCEMENT_FAILED.yml

- JORB-INFRA-035 blocked by automated loop via BLK-JORB-INFRA-035.yml. History: 2026-03-31T152930Z-JORB-INFRA-035.yml

- DRAFT-JORB-INFRA-EVAL_REGRESSION blocked by automated loop via BLK-DRAFT-JORB-INFRA-EVAL_REGRESSION.yml. History: 2026-03-31T163056Z-DRAFT-JORB-INFRA-EVAL_REGRESSION.yml

- JORB-INFRA-041 blocked by automated loop via BLK-JORB-INFRA-041.yml. History: 2026-03-31T205019Z-JORB-INFRA-041.yml
