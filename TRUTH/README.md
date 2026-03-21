# TRUTH Documentation System

## Purpose
This folder defines the documentation standard for production systems operated on these VMs.

These docs keep three things aligned:
- runtime truth
- repo truth
- operator truth

Use this system in any repo that matters operationally.

## Canonical Files

### `AGENTS.md`
Use for:
- agent and operator instructions
- repo rules
- deployment workflow
- environment and coordination notes

### `PROJECT_STATE.md`
Use for:
- current live status
- what is complete
- what is incomplete
- key files and next steps

### `CHANGELOG.md`
Use for:
- dated material changes
- merges
- deploys
- auth and infra changes

### `TRUTH.md`
Use for:
- concise current-reality snapshot
- public URLs
- runtime location
- infra identity
- current production facts
- operator mechanics

## Update Triggers
Update these docs whenever:
- production behavior changes
- auth changes
- infra or runtime location changes
- branch alignment changes
- deployment path changes
- live URLs change
- operator workflow changes

## Minimum Standard
- `TRUTH.md`: current reality snapshot
- `PROJECT_STATE.md`: current implementation state
- `CHANGELOG.md`: historical record of material changes
- `AGENTS.md`: operating instructions for the responsible agent

## Workflow
1. Verify the change.
2. Update the canonical docs.
3. Build, restart, or deploy as needed.
4. Verify runtime behavior.
5. Commit and push.

## Templates
- `AGENTS.template.md`
- `PROJECT_STATE.template.md`
- `CHANGELOG.template.md`
- `TRUTH.template.md`
