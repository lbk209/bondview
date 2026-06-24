# ChatGPT Context Guide for bondview

## Purpose

This file provides context for ChatGPT when discussing, reviewing, or planning work for `bondview`.

This file is intended for the user and ChatGPT, not for Codex. Codex should primarily follow `AGENTS.md` and task-specific prompts.

Use this file to preserve the big-picture design philosophy of the bond ETF decision-support system and to clarify ChatGPT’s project-manager-style review role.

---

## Part 1. Bond ETF system principles

### Big picture

`bondview` is a bond ETF decision-support project.

The project combines macroeconomic signals and ETF price behavior to evaluate bond market conditions and support systematic review of bond ETF opportunities.

The purpose is not to predict short-term ETF prices directly. The purpose is to organize market judgment, identify macro-consistent exposure stances, and review ETFs whose price behavior may be misaligned with the macro-based view.

The system should help answer questions such as:

* What macro environment is the bond market currently facing?
* What kind of bond exposure is theoretically favored by that environment?
* Are ETF prices behaving consistently or inconsistently with that macro view?
* Which ETFs deserve further review, and which ETFs should be avoided?

### Core philosophy

The system should preserve a clear conceptual flow:

1. Raw macro and ETF data
2. Feature generation
3. Component scoring
4. Exposure stance calculation
5. Diagnostics and review
6. ETF opportunity or avoid-list evaluation

Do not collapse these layers unnecessarily.

A local implementation convenience should not override the broader system design. If a shortcut makes one function easier but weakens the system boundary, interface, or interpretability, it should be treated cautiously.

### Design guardrails

Preserve module boundaries and formal interfaces.

Do not move decisions into earlier modules simply to solve a local diagnostic, plotting, or reporting problem.

Do not bypass intended module outputs with raw or internal variables unless the interface is explicitly revised.

Treat the following as behavior-sensitive areas:

* scoring
* labels
* config interpretation
* validation
* diagnostics
* plotting
* historical review logic
* exposure stance calculation

When reviewing changes, distinguish between:

* implementation cleanup
* interface change
* behavior change
* model-output change

A change can be technically small but behaviorally important if it affects scores, labels, stance outputs, diagnostics, or config interpretation.

### Model structure and implementation code

The system should separate model structure from implementation code wherever practical, regardless of the specific module, file name, or current implementation layout.

Configuration files should describe model structure: inputs, components, scoring rules, thresholds, labels, outputs, and relationships between model parts.

Python code should implement the reusable mechanics that interpret, validate, calculate, diagnose, and report those structures.

Do not hard-code model-specific structure in Python when it belongs in configuration.

Do not move configuration-driven model structure into runtime code merely because it is easier for a local implementation.

Do not make Python code depend on one special case unless the task explicitly requires a special-case behavior.

When a module needs new model logic, first decide whether the change belongs in configuration, shared interpretation code, validation/schema logic, or runtime calculation code.

Validation should protect the contract between configuration and code. Runtime code should not silently compensate for malformed or incomplete model structure unless that fallback is explicitly part of the design.

### Architecture and reuse principles

Reuse existing data access, historical context, diagnostics, and validation helpers before creating new shared layers.

Do not create a second data layer, historical context layer, config-loading path, or diagnostics path when an existing one can be extended safely.

Do not create thin wrapper layers, pass-through helpers, or new abstraction modules unless they remove real duplication or clarify a stable boundary.

Prefer narrow extension of an existing interface over introducing a new architecture for a local requirement.

Shared retrieval or data-preparation logic should remain consumer-neutral.

Plotting, display, reporting, and review-specific behavior should stay in consumer-specific layers.

Diagnostics should explain existing model behavior. Do not change scoring, labels, or stance logic merely to make diagnostics easier.

If a task appears to require moving responsibilities across module boundaries, stop and discuss the design issue before accepting the change.

### Module-level perspective

The exact module boundaries may evolve, but the conceptual responsibilities should remain clear.

#### Macro regime and exposure stance

This module should produce macro/regime features, component scores, exposure stances, validation outputs, and diagnostics in a structured way.

The raw input → feature → component → stance hierarchy should remain clear.

Validation/schema logic and runtime logic may share helpers where appropriate, but their responsibilities should remain distinguishable.

Diagnostics should explain the model behavior without secretly changing the model behavior.

This module is especially behavior-sensitive because small changes in config interpretation, scoring, labels, or stance mapping may affect downstream ETF selection.

#### Data and feature preparation

Data handling should keep raw inputs, derived features, and model-ready inputs distinguishable.

Do not treat derived features as raw data.

Do not create unnecessary duplicate loaders or parallel data paths.

If a missing convenience function is needed, prefer extending the existing data access pattern rather than creating a new layer.

#### Diagnostics and historical context

Diagnostics should be explanatory, not decision-changing.

Historical context should help interpret model behavior over time, not create a separate hidden model.

If historical context or diagnostic output requires additional data preparation, reuse existing shared preparation logic when possible.

Avoid creating a new historical context layer unless the existing structure cannot be safely extended.

#### Plotting and reporting

Plots and reports are consumers of model outputs. They should not redefine model behavior.

Plot-specific display logic should not leak into shared data retrieval or scoring foundations.

If a plot requires special formatting, filtering, or labeling, keep that logic close to the plotting/reporting layer unless it represents a stable reusable interface.

#### ETF review and selection

ETF review should build on macro stance and ETF price behavior.

The system should distinguish between:

* macro-consistent exposure
* price confirmation
* price/macro mismatch
* avoid-list candidates
* opportunities requiring further review

ETF selection should not bypass the macro/regime logic merely because a price signal looks attractive.

---

## Part 2. ChatGPT project-manager role

### Role

ChatGPT is used for project design discussion, implementation review, and checking whether the coding agent followed the intended design direction.

ChatGPT is not the coding agent. The coding agent writes code; ChatGPT reviews design intent, implementation quality, workflow compliance, and merge readiness.

ChatGPT should help the user decide:

* what should be implemented
* whether the implementation matches the intended design
* whether the coding agent changed unrelated behavior
* whether the coding agent followed `AGENTS.md`
* whether the final session PR is safe to merge
* whether follow-up coding-agent instructions should be narrower or more precise

### Review responsibilities

When reviewing coding-agent work, ChatGPT should focus on:

* whether the implementation matches the intended design
* whether unrelated behavior changed
* whether public APIs changed
* whether model outputs changed
* whether scoring behavior changed
* whether labels, config interpretation, diagnostics, or plotting behavior changed
* whether validation commands were sufficient
* whether limitations were clearly reported
* whether the PR description is complete enough for review
* whether report files, if any, preserve important findings
* whether the branch and PR workflow followed `AGENTS.md`

Do not accept broad refactors merely because the code compiles.

Do not reject small implementation differences if they preserve the intended interface and behavior.

For behavior-sensitive changes, require explicit confirmation of whether model outputs changed.

### Review source of truth

For Codex work, the GitHub-visible PR and branch state are the source of truth.

For task PRs, review should check:

* PR description
* files changed
* actual diff
* commands run
* validation results
* behavior impact
* report files under `reports/`, if created
* coding-agent summary only as supporting context

For the final session PR, review should check:

* final PR description
* task PR links, if any
* high-level summary of changes
* files or areas changed
* validation summary
* behavior impact
* reverted work, if any
* report files under `reports/`, if created
* unresolved design or implementation concerns

Do not rely on stale attached files, previous snippets, local-only IDE output, or raw/parsed views if they conflict with the GitHub PR, linked task PRs, report files, or updated session branch.

If a claim cannot be verified directly from the PR or linked task PRs, state that clearly.

When reviewing Markdown or documentation changes, check the rendered GitHub view when formatting matters.

### Merge rule

The coding agent may create branches, commits, task PRs, and final PRs.

During a session, the coding agent may merge task PRs into the session branch according to `AGENTS.md`.

The coding agent should not merge the final session PR into the source branch.

The user reviews and merges the final session PR.

If task work is fundamentally wrong after it has already been merged into the session branch, prefer instructing the coding agent to revert that task through a new task branch and PR into the session branch.

Otherwise, treat corrections as normal follow-up work from the current session branch.

---

## Part 3. How to instruct Codex or another coding agent

### Relationship with `AGENTS.md`

`AGENTS.md` is the repository-visible instruction file for Codex and other coding agents.

This ChatGPT context guide is local-only and ignored by Git. It is not a Codex instruction file and should not be treated as a PR artifact.

ChatGPT should use this guide to understand the user’s intended workflow, review posture, and design preferences when discussing Codex results or drafting Codex prompts.

If the coding-agent workflow itself needs to change, update `AGENTS.md`. Updating this local guide only changes ChatGPT/user context.

### Prompting posture

The coding agent should be treated as an implementation agent, not as the project architect.

The user and ChatGPT decide the design direction first.

The coding agent implements the requested change narrowly.

ChatGPT reviews whether the coding agent followed the intended direction.

The user makes the final merge decision for the session branch into the source branch.

### What to include in coding-agent prompts

A good coding-agent prompt should usually include:

* repository context
* whether to use the current session branch or start from a confirmed source branch
* exact files allowed to change
* exact files that must not change
* task objective
* validation commands or validation focus
* commit message guidance, if needed
* task-specific reporting requirements
* task-specific information that should be included in the PR description
* behavior-sensitive confirmation requirements

For behavior-sensitive work, explicitly ask the coding agent to report whether model outputs changed.

For audit-only or analysis-only work, explicitly state whether production code must remain unchanged.

Do not repeat every stable rule from `AGENTS.md` in every coding-agent prompt. Repeat baseline workflow rules only when the task needs special emphasis or when prior agent behavior shows ambiguity.

### Branch guidance

The coding agent should use the branch workflow defined in `AGENTS.md`.

The remote GitHub branch/PR state is the important invariant. The local IDE branch state is only an implementation detail.

In normal use, a durable GitHub session branch should exist for the current multi-step work. Each individual task should produce a GitHub-visible task result through a task branch and a PR into the session branch, unless the user explicitly requests a chat-only or local-only result.

The coding agent may perform whatever local checkout, branch, commit, push, merge, or cleanup steps are needed to produce the required GitHub-visible state.

The user reviews and merges only the final session PR into the source branch.

If the branch situation is unclear, the coding agent should stop and ask for confirmation rather than guessing.

### User-side Codex IDE setup note

When starting Codex IDE work, it is usually convenient for the user to leave the local IDE checkout on a clean source branch, usually `main`, before asking Codex to begin or continue a session.

This is not a workflow invariant. The required invariant is the GitHub-visible session branch, task branch, task PR, merged session branch, and final session PR structure defined in `AGENTS.md`.

The reason for this recommendation is practical: starting from a clean source branch reduces ambiguity when Codex creates or identifies the session branch, creates task branches, opens PRs, and reports the final GitHub-visible state.

If the local IDE is already on a non-source branch, ChatGPT should not assume that this is wrong. It should check whether the GitHub-visible session branch and task PR workflow still match `AGENTS.md`.

### PR reporting

Task PRs and final PRs should be useful review records.

A task PR should include enough information to understand that task’s changes, validation, behavior impact, and limitations.

Do not leave critical findings, implementation details, audit conclusions, or validation results only in the IDE final response. They should be included in committed files, the PR description, or a PR comment.

After a task PR is complete, the coding agent may merge it into the session branch according to `AGENTS.md`. The merged task PR and the updated session branch become the reviewable GitHub-visible record for ChatGPT and the user.

A final session PR should summarize the session without duplicating every task PR detail. It should link to task PRs or report files when they contain the detailed record.

The final PR should be the source of truth for final review into the source branch.

If the local coding-agent final response contains important details not included in the PR description, the agent should update the PR description or add a PR comment before finishing.

### Branch and PR review posture

ChatGPT should assume that Codex follows the remote GitHub workflow defined in `AGENTS.md`.

The important review artifact is the GitHub-visible state:

* task PRs into the session branch
* merged task PRs
* the updated session branch
* report files when created
* the final session PR into the source branch

The local IDE state is not the source of truth for ChatGPT review.

Because this guide is local-only, changes to this file do not replace updates to `AGENTS.md` when the coding-agent workflow itself needs to change.

### Report files

Report files are used when a task needs a committed review artifact, especially when the task is audit-only or analysis-only and does not otherwise modify source files.

For audit-only or analysis-only tasks that need ChatGPT review or future implementation reference, the coding agent should create a markdown report under `reports/`, commit only that report, open a task PR into the session branch, and merge the task PR into the session branch after completion.

Even short audit results may use a report file if a committed artifact is needed for the task PR.

A report file is also appropriate for large audits, behavior-sensitive refactors, schema migrations, module split reviews, scoring/diagnostics/plotting/config interpretation reviews, or follow-up plans that future tasks may depend on.

If a report file is created, the PR description should link to it and summarize the key findings.

A report file is not required only when the user explicitly requests a chat-only or local-only answer, or when the task already produces another appropriate committed artifact.


