# AGENTS

This file defines how coding agents should operate in this repository.

## Core Directive: Use Skills First

- Before doing task work, check whether any available skill applies.
- If a skill is relevant, read its `SKILL.md` first and follow it immediately.
- Do not only mention a skill. Actually execute its workflow.
- Prefer skill-driven workflows over ad-hoc approaches when both can solve the task.

## Skill Selection Rules

- Match user intent to the closest skill (for example: install skills, create rules, update editor settings, browser automation).
- If more than one skill may apply, pick the most specific one first.
- When multiple skills are required, run them in a logical order and preserve constraints from each skill.
- If no skill applies, proceed with normal repository workflows.

## Available Skills (Local Environment)

- `skill-creator`: Create or update skills.
- `skill-installer`: List/install skills from curated sources or repositories.
- `gm-news-snapshot`: Capture morning snapshots from NDTV and New Indian Express.
- `playwright`: Browser automation via Playwright CLI/wrapper.
- `create-rule`: Create Cursor rules and `AGENTS.md` guidance.
- `create-skill`: Author new Cursor Agent Skills.
- `update-cursor-settings`: Modify Cursor/VSCode `settings.json`.

## Execution Checklist

- Identify intent from the latest user request.
- Determine whether a listed skill applies.
- Read the relevant `SKILL.md` file before implementation.
- Execute the task using that skill's required process.
- Verify output and report concise results to the user.
