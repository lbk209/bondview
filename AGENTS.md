# AGENTS.md

## Purpose

This file provides stable guidance for coding agents working on `bondview`.

The agent should treat this file as baseline project guidance. Task-specific user instructions still take priority when they are more specific.

## Project and implementation guardrails

### Project context

`bondview` is a bond ETF decision-support project.

The project uses macroeconomic data and ETF price data to evaluate bond market conditions, derive exposure stances, and support systematic review of bond ETF opportunities.

The purpose is not to predict short-term ETF prices directly. The purpose is to organize market judgment, identify macro-consistent exposure stances, and review ETFs whose price behavior may be misaligned with the macro-based view.

The codebase should preserve clear boundaries between data inputs, feature generation, component scoring, stance calculation, diagnostics, and reporting.

### Agent role

The coding agent should implement narrowly scoped changes according to the user’s instructions.

Do not make independent design decisions beyond the requested task. If a change appears to require a design decision, mention it in the PR description instead of expanding the scope.

The coding agent may create branches, commits, task PRs, and final review PRs according to the Git workflow below.

The coding agent must not merge the session branch into the source branch. The user reviews and merges the final PR into the source branch.

### Implementation rules

* Make only the requested changes.
* Modify only the files required for the requested task.
* Create new files only when they are necessary for the requested task.
* Do not delete files unless explicitly instructed.
* Avoid broad refactors unless explicitly requested.
* Do not change model outputs, scoring behavior, config interpretation, public APIs, or file formats unless explicitly requested.
* Treat YAML configuration files, including `module*_config.yaml`, as behavior-sensitive files. If they are changed, report the intended behavior impact and whether model outputs changed.

### Module boundaries

* Preserve the raw input → feature → component → stance hierarchy.
* Keep validation/schema logic separate from runtime logic where practical.
* Do not bypass formal module outputs with raw or internal variables unless explicitly requested.
* Treat config validation, scoring, labels, diagnostics, and plotting as behavior-sensitive areas.
* When changing scoring, labels, diagnostics, validation, or config interpretation, explicitly report whether model outputs changed.

### Model structure and implementation code

* Separate model structure from implementation code wherever practical.
* Configuration files should describe model structure: inputs, components, scoring rules, thresholds, labels, outputs, and relationships between model parts.
* Python code should implement the reusable mechanics that interpret, validate, calculate, diagnose, and report those structures.
* Do not hard-code model-specific structure in Python when it belongs in configuration.
* When a module needs new model logic, first decide whether the change belongs in configuration, shared interpretation code, validation/schema logic, or runtime calculation code.
* Validation should protect the contract between configuration and code. Runtime code should not silently compensate for malformed or incomplete model structure unless that fallback is explicitly part of the design.

### Architecture and reuse rules

* Reuse existing data access, historical context, diagnostics, and validation helpers before creating new shared layers.
* Do not create a second data layer, historical context layer, config-loading path, or diagnostics path when an existing one can be extended safely.
* Do not create thin wrapper layers, pass-through helpers, or new abstraction modules unless they remove real duplication or clarify a stable boundary.
* Prefer extending the existing interface narrowly over introducing a new architecture for a local requirement.
* Shared retrieval or data-preparation logic should remain consumer-neutral.
* Plotting, display, reporting, and review-specific behavior should stay in consumer-specific layers.
* Diagnostics should explain existing model behavior. Do not change scoring, labels, or stance logic merely to make diagnostics easier.
* If a task appears to require moving responsibilities across module boundaries, stop and report the design issue instead of silently changing the architecture.
* Do not bundle cleanup, formatting, import reorganization, or unrelated refactors into behavior-sensitive changes unless explicitly requested.

### Validation expectations

For Python changes, run syntax checks on every Python file modified by the task.

At minimum, use:

`python -m py_compile <modified_python_files>`

For changes that affect shared imports, module boundaries, validation/schema logic, or runtime dispatch, also run syntax checks on directly related Python files.

When relevant, also run focused smoke checks for:

* config loading
* config validation
* relevant helper functions
* non-destructive public methods
* changed diagnostics or reporting paths

For behavior-sensitive changes, include validation that is specific to the affected behavior.

If a check cannot be run because of missing credentials, unavailable dependencies, network limits, or missing external data, report that limitation clearly. Do not fake success.

## Git and GitHub workflow

### Working branch policy

Before editing, check the current branch, working tree status, recent commits, and existing local/remote branches.

The default source branch is `main`.

If only the source branch exists, create one session branch from it before starting work.

The first branch that the agent creates from the confirmed source branch is the session branch.

The session branch is the only long-lived agent-created working branch.

If a session branch already exists for the current work, continue from that branch.

If multiple non-source branches exist, or if it is unclear which branch is the source branch or session branch, stop and ask the user to confirm before editing.

Do not push directly to `main`.

Do not commit directly to the source branch unless explicitly instructed.

At any point, the normal clean state should be: the source branch plus one session branch.

### Task work and task PR workflow

The first task may be committed directly to the session branch.

For later tasks, the agent may either continue directly on the session branch or create a temporary task branch from the session branch when a separate task PR would make review clearer.

If a task branch is created, its PR should target the session branch, not the source branch.

The task PR description should include enough information for review:

* Summary of changes
* Files changed
* Commands run
* Validation results
* Behavior impact
* Limitations or checks not run
* Whether model outputs changed, if relevant

The agent may merge the task PR into the session branch after requested validation passes and the task PR description is complete.

After merging the task PR into the session branch, delete the task branch.

The task branch is disposable after merge. The merged task PR and the session branch are the reviewable records.

If a merged task PR is later found to be fundamentally wrong, revert it on the session branch with a new revert commit unless the user explicitly instructs another correction method.

Otherwise, continue from the current session branch with a normal follow-up task.

After completing task work, report:

* current session branch
* task PR number or link, if a task PR was created
* merge result, if a task PR was merged
* deleted task branch, if a task branch was deleted
* validation results
* any limitations

### Final PR workflow

When the user asks to finish the session, create one final PR from the session branch into the source branch.

The final PR is the user-reviewed merge point.

The agent must not merge the final PR into the source branch.

The user reviews and merges the final PR.

The final PR description should summarize the full session without duplicating every task PR detail. Include:

* Session branch name
* Source branch name
* Task PR links, if any
* High-level summary of changes
* Files or areas changed
* Validation summary
* Important validation failures or limitations, if any
* Behavior impact
* Whether model outputs changed, if relevant
* Reverted work, if any
* Any unresolved design or implementation concerns

Use task PRs and report files as the detailed record when the session contains many tasks.

The final PR should be the source of truth for final review.

### Report files

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
