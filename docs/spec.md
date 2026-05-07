# Mirage Spec Workflow Guide

Mirage supports a spec-driven workflow so you can move from idea -> spec -> plan -> implementation in a structured way.

This guide covers:

- what Mirage spec mode is
- where files are stored
- which commands to use
- an end-to-end workflow
- common patterns and troubleshooting

## What "spec-driven" means in Mirage

In Mirage, spec-driven work uses two artifacts:

- **Spec**: the problem definition and expected outcome
- **Plan**: the implementation checklist derived from the spec

Implementation is intentionally **separate** from artifact creation:

- `/spec` creates or updates the spec artifact
- `/plan` creates or updates the plan artifact
- `/implement-spec` starts iterative implementation from the active spec + plan

This separation helps you review and refine requirements before code changes begin.

## Directory structure

Mirage stores spec artifacts in your project under `.mirage/`:

- `.mirage/specs/*.md` - generated and curated specs
- `.mirage/plans/*.md` - generated and curated plans
- `.mirage/compactions/*.md` - optional compact/summarize outputs

If needed, Mirage scaffolds `.mirage/` directories automatically for project runs.

## Commands

### `/spec [title]`

Creates a spec markdown file in `.mirage/specs/`.

Behavior:

- if no title is provided, Mirage uses `Project Spec`
- file name is slugified from title
- if file exists, a timestamped variant is created
- switches runtime mode to `plan` (analysis-oriented)

Example:

```text
/spec User onboarding improvements
```

### `/plan [title]`

Creates a plan markdown file in `.mirage/plans/` using the latest spec as source.

Behavior:

- requires at least one spec file
- if no title is provided, Mirage uses `Project Plan`
- if existing file name collides, timestamped variant is created
- switches runtime mode to `plan`

Example:

```text
/plan Onboarding v2 implementation
```

### `/implement-spec [task]`

Runs implementation iteratively from the active spec + plan.

Behavior:

- requires both latest spec and latest plan to exist
- enables spec-driven execution for the run
- executes checklist-style iterations from open plan items
- auto-resets spec-driven mode when run finishes
- switches to `build` mode policy for implementation

Example:

```text
/implement-spec Implement phase 1 with tests first
```

If no task is provided, Mirage uses:

- `Implement the active plan step-by-step.`

## End-to-end workflow

Use this as the default pattern for larger features.

1. Enter problem statement with constraints.
2. Run `/spec <title>`.
3. Review and edit generated spec file if needed.
4. Run `/plan <title>`.
5. Review and edit plan checklists.
6. Run `/implement-spec <execution note>`.
7. Validate outputs, tests, and plan checkbox completion.

## What Mirage injects into context

Every run includes a concise project context summary as bullet points, including:

- project name
- detected stack
- working directory
- sample top-level entries

When `/implement-spec` is used, Mirage additionally injects:

- active spec content and path
- active plan content and path
- current plan task iteration markers

## Artifact quality tips

To get better results:

- keep spec title specific (`Auth token refresh in CLI`, not `Auth improvements`)
- make acceptance criteria measurable
- keep plan tasks small and file-oriented
- include rollback and validation steps in plan
- edit generated files manually when domain constraints are missing

## Recommended plan structure

A strong plan file usually includes:

- milestones
- grouped checkbox tasks
- file touchpoints
- validation strategy
- rollback strategy

Mirage already seeds this structure when creating plans.

## Common issues

### "no spec found. create one first with /spec <title>"

Cause:

- you ran `/plan` or `/implement-spec` without any spec artifact

Fix:

- run `/spec <title>` first

### "no plan found. create one first with /plan <title>"

Cause:

- you ran `/implement-spec` without a plan artifact

Fix:

- run `/plan <title>`

### Spec-driven behavior runs unexpectedly

Current behavior:

- spec-driven implementation only runs when explicitly triggered with `/implement-spec`
- normal chat/run prompts are not forced into spec-driven iteration

## CLI vs slash commands

Spec workflow is currently driven by slash commands inside interactive chat.

If you need non-interactive automation, use:

- `mirage run` for one-shot tasks
- `mirage serve` for HTTP automation

Then optionally generate/edit spec-plan artifacts in chat and execute with `/implement-spec`.

## Team usage pattern

For team consistency, use this convention:

- one feature = one spec file + one plan file
- keep names aligned (`feature-x-spec`, `feature-x-plan`)
- run `/implement-spec` in focused sessions
- update plan checkboxes as implementation progresses

## Quick command reference

```text
/spec <title>
/plan <title>
/implement-spec [task]
```

## Summary

Use Mirage spec workflow when work is multi-step, risky, or cross-cutting:

- `/spec` defines **what** and **why**
- `/plan` defines **how**
- `/implement-spec` executes iteratively against that source of truth

This gives you repeatable execution with clearer intent, better reviewability, and safer delivery.

