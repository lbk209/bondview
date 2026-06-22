# AGENTS.md

## Purpose

This file provides stable guidance for coding agents working on `bondview`.

The agent should treat this file as baseline project guidance. Task-specific user instructions still take priority when they are more specific.

---

# Project and implementation guardrails

## Project context

`bondview` is a bond ETF decision-support project.

The project uses macroeconomic data and ETF price data to evaluate bond market conditions, derive exposure stances, and support systematic review of bond ETF opportunities.

The purpose is not to predict short-term ETF prices directly. The purpose is to organize market judgment, identify macro-consistent exposure stances, and review ETFs whose price behavior may be misaligned with the macro-based view.

The codebase should preserve clear boundaries between data inputs, feature generation, component scoring, stance calculation, diagnostics, and reporting.

## Agent role

The coding agent should implement narrowly scoped changes according to the user’s instructions.

Do not make independent design decisions beyond the requested task. If a change appears to require a design decision, mention it in the PR description instead of expanding the scope.

Do not merge PRs. The user reviews and merges changes separately.

## Implementation rules

* Make only the requested changes.
* Avoid broad refactors unless explicitly requested.
* Do not delete files unless explicitly instructed.
* Do not modify data files unless the task explicitly requires it.
* Do not change model outputs, scoring behavior, config interpretation, or public APIs unless explicitly requested.
* If a file appears unused, mention it in the PR description instead of deleting it.

## Module boundaries

* Preserve the raw input → feature → component → stance hierarchy.
* Keep validation/schema logic separate from runtime logic where practical.
* Do not bypass formal module outputs with raw or internal variables unless explicitly requested.
* Treat config validation, scoring, labels, diagnostics, and plotting as behavior-sensitive areas.
* When changing scoring, labels, diagnostics, validation, or config interpretation, explicitly report whether model outputs changed.

## Validation expectations

For Python changes, run at least:

* `python -m py_compile module1.py module1_schema.py`

When relevant, also run focused smoke checks for:

* config loading
* config validation
* relevant helper functions
* non-destructive public methods

If a check cannot be run because of missing credentials, unavailable dependencies, network limits, or missing external data, report that limitation clearly. Do not fake success.

---

# Git and GitHub workflow

## Git preflight checks

Before making changes, run basic Git state checks.

At minimum, check:

* current branch
* working tree status
* latest commit
* whether the task is intended to update an existing PR branch or create a new branch
* whether `main` is up to date with `origin/main`

If the working tree has unrelated uncommitted changes, stop and report the issue before editing files.

If the task says to create a new branch, start from the latest `main` unless the user explicitly says to work from another branch.

If the task is related to an existing PR, work on that PR branch directly. Do not create a new branch unless explicitly instructed.

If there are pending setup or dependency PRs that may affect the requested task, warn the user before continuing.

When unsure whether the current branch is appropriate, stop and report:

* current branch
* intended branch
* working tree status
* why continuing may be risky

## Branch and commit rules

* Do not push directly to `main`.
* Create a task-specific branch before committing, unless the user explicitly says to work on an existing PR branch.
* Commit only files related to the requested task.
* Do not mix unrelated changes in the same commit.
* Do not merge PRs.

## Pull request expectations

Create a PR but do not merge it.

The PR description must include enough information for external review. Include:

* Summary of changes
* Files changed
* Commands run
* Validation results
* Behavior impact
* Limitations or checks not run
* Whether model outputs changed, if relevant

Do not rely only on the local Codex chat summary. Important audit results and validation results should be included in the PR description.

The PR should be the source of truth for review. If the local Codex final response contains important details not included in the PR description, update the PR description or add a PR comment before finishing.

## Report files

Use the `reports/` directory only when the task produces review material that is too large or detailed for a normal PR description.

Do not create a separate report file for routine changes such as small documentation edits, small dependency updates, simple bug fixes, or minor helper changes.

Create a report file only for work that has lasting review value, such as:

* large audits
* behavior-sensitive refactors
* schema or validation migrations
* module split or module boundary reviews
* scoring, diagnostics, plotting, or config interpretation reviews
* follow-up plans that future tasks may depend on

Report files must be placed under `reports/`.

Use this filename format:

`reports/YYMMDD_<scope>_<topic>_<report_type>.md`

Filename rules:

* Use the current date in `YYMMDD` format.
* Use lowercase letters, numbers, and underscores only.
* Keep names short but specific.
* `<scope>` should identify the main area, such as `module1`, `schema`, `duration`, `plot`, `diagnostics`, or `data`.
* `<topic>` should identify the specific task or subject.
* `<report_type>` should describe the document type, such as `audit`, `review`, `plan`, `summary`, or `followup`.

Examples:

* `reports/260622_module1_upload_audit.md`
* `reports/260622_module1_schema_split_review.md`
* `reports/260622_duration_stance_migration_audit.md`
* `reports/260622_plot_refactor_followup.md`

If a report file is created, the PR description must:

* link to the report file
* summarize the key findings briefly
* state why the separate report file was needed

Do not use report files as a substitute for a clear PR description.
