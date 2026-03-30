# Preflight Contract

Preflight must reject execution when:
- required repo paths are missing
- run lock is already owned by another live controller
- Phase 4/4B repo-local standards are missing
- task-specific configuration is incomplete

Existing preflight already covers:
- backlog validation
- active/status consistency
- git and VM auth checks
- clean worktree gating

This slice adds:
- lock ownership
- required directory presence
- standards presence for Phase 4/4B tasks
