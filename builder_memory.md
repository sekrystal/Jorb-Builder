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
