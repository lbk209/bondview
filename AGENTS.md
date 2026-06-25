# AGENTS.md

## Purpose

This file provides stable guidance for coding agents working on `bondview`.

The agent should treat this file as baseline project guidance. Task-specific user instructions still take priority when they are more specific.

## Project and implementation guardrails

### Project context

`bondview` is a bond ETF decision-support project.

The project uses macroeconomic data and ETF price data to evaluate bond market conditions, derive exposure views, and support systematic review of bond ETF opportunities.

The purpose is not to predict short-term ETF prices directly. The purpose is to organize market judgment, identify macro-consistent exposure views, and review ETFs whose price behavior may be misaligned with the macro-based view.

In this document, “model” means any project logic that transforms input data into signals, scores, classifications, exposure views, rankings, diagnostics, or review outputs.

The codebase should preserve clear boundaries between data acquisition, data preparation, model or signal calculation, decision logic, diagnostics, reporting, and review outputs.

The current codebase is still centered heavily on Module 1, but future modules may cover separate responsibilities such as data preparation, ETF review, portfolio or ranking logic, reporting, or other decision-support layers.

Individual modules may use more specific internal layers. For example, Module 1 currently uses a raw input → feature → component → stance hierarchy.

### Agent role

The coding agent should implement narrowly scoped changes according to the user’s instructions.

Do not make independent design decisions beyond the requested task. If a change appears to require a design decision, mention it in the task result instead of expanding the scope.

The coding agent may create the GitHub-visible work artifacts required by the Git workflow below.

The coding agent must not complete or merge final session work into the project’s stable branch unless explicitly instructed by the user.


### Implementation rules

* Make only the requested changes.
* Modify only the files required for the requested task.
* Create new files only when they are necessary for the requested task.
* Do not delete files unless explicitly instructed.
* Avoid broad refactors unless explicitly requested.
* Do not change model outputs, scoring behavior, config interpretation, public APIs, or file formats unless explicitly requested.
* Treat YAML configuration files, including `module*_config.yaml`, as behavior-sensitive files. If they are changed, report the intended behavior impact and whether model outputs changed.

### Module boundaries

* Each module should preserve a clear internal processing hierarchy and expose formal outputs for downstream consumers.
* Do not bypass a module’s formal intermediate or final outputs with raw or internal variables unless explicitly requested.
* Do not collapse data preparation, model or signal calculation, decision logic, diagnostics, plotting, or reporting merely because a local implementation would be shorter.
* Keep validation/schema logic separate from runtime logic where practical.
* Treat config validation, scoring, labels, diagnostics, plotting, and decision outputs as behavior-sensitive areas when they affect downstream behavior.
* When changing scoring, labels, diagnostics, validation, config interpretation, or decision outputs, explicitly report whether model outputs changed.
* For Module 1, preserve the current raw input → feature → component → stance hierarchy.
* Future modules may use different internal layer names, but the same principle applies: keep intermediate responsibilities explicit, reviewable, and behavior-sensitive where they affect downstream decisions.

### Model structure and implementation code

* Separate model structure from implementation code wherever practical.
* Configuration files should describe model structure where the module is configuration-driven: inputs, components or signals, scoring rules, thresholds, labels, outputs, and relationships between model parts.
* Python code should implement the reusable mechanics that interpret, validate, calculate, diagnose, and report those structures.
* Do not hard-code model-specific structure in Python when it belongs in configuration.
* When a module needs new model logic, first decide whether the change belongs in configuration, shared interpretation code, validation/schema logic, runtime calculation code, diagnostics, or reporting code.
* Validation should protect the contract between configuration and code. Runtime code should not silently compensate for malformed or incomplete model structure unless that fallback is explicitly part of the design.

### Architecture and reuse rules

* Reuse existing helpers within the current module and across related modules before creating new shared layers or duplicating logic.
* If another module already contains similar reusable mechanics, consider whether the logic should remain module-local, be extracted into a shared helper, or be reused through an existing interface.
* Do not extract shared helpers merely because two implementations look similar. Extract only when the behavior is stable, genuinely reusable, and the change can be made without broadening the task scope or changing behavior unexpectedly.
* Do not create duplicate data, configuration, diagnostics, reporting, or review paths within a module or across related modules when an existing path can be safely extended.
* Do not create thin wrapper layers, pass-through helpers, or new abstraction modules unless they remove real duplication or clarify a stable boundary.
* Prefer extending an existing interface narrowly over introducing a new architecture for a local requirement.
* Shared data retrieval, data preparation, and reusable calculation mechanics should remain consumer-neutral.
* Plotting, display, reporting, and review-specific behavior should stay in consumer-specific layers.
* Diagnostics should explain existing model behavior. Do not change scoring, labels, stance logic, decision logic, or model outputs merely to make diagnostics easier.
* If a task appears to require moving responsibilities across module boundaries, stop and report the design issue instead of silently changing the architecture.
* Do not bundle cleanup, formatting, import reorganization, or unrelated refactors into behavior-sensitive changes unless explicitly requested.

### Validation expectations

For Python changes, run syntax checks on every Python file modified by the task.

At minimum, use:

`python -m py_compile <modified_python_files>`

For changes that affect shared imports, module boundaries, validation/schema logic, runtime dispatch, or reporting/diagnostic dispatch, also run syntax checks on directly related Python files.

When relevant, also run focused smoke checks for:

* data or config loading
* config validation
* relevant helper functions
* non-destructive public methods
* changed diagnostics or reporting paths
* changed decision or model-output paths

For behavior-sensitive changes, include validation that is specific to the affected behavior.

If a check cannot be run because of missing credentials, unavailable dependencies, network limits, or missing external data, report that limitation clearly. Do not fake success.


## Git and GitHub workflow

### Core branch model

Before editing, check the current branch, working tree status, recent commits, and existing local/remote branches.

The default source branch is `main`.

Use a GitHub session branch as the durable integration branch for multi-step work. The session branch must exist on GitHub.

The session branch is the only long-lived agent-created working branch.

Each individual task should produce a GitHub-visible task result through a task branch and a PR into the session branch, unless the user explicitly instructs otherwise.

The required remote GitHub state after each task is:

* a session branch that exists on GitHub,
* a task branch created from the current session branch,
* a PR from the task branch into the session branch,
* critical task details included in committed files or the PR description,
* the task PR merged into the session branch after the task is complete.

Local IDE branch state is an implementation detail. The agent may perform whatever local checkout, branch, commit, push, merge, and cleanup steps are needed to produce the required GitHub-visible result.

Do not push directly to the source branch.

Do not commit directly to the source branch unless explicitly instructed.

Only the user may merge the session branch into the source branch. The agent must not merge the session branch into the source branch unless explicitly instructed.

### Session branch selection

If only the source branch exists, create one session branch from it and push the session branch to GitHub before starting task work.

The first branch that the agent creates from the confirmed source branch is the session branch.

If a session branch already exists for the current work, continue from that branch.

If the current branch is not the source branch and no session branch is explicitly identified, report the current branch and ask whether to use it as the session branch.

If multiple non-source branches exist, or if it is unclear which branch is the source branch or session branch, stop and ask the user to confirm before editing.

At any point, the normal durable remote state should be: the source branch plus one session branch. Temporary task branches may exist while task PRs are open.

### Task branch and task PR workflow

For each task, create a task branch from the current session branch.

Complete the task on the task branch.

Push the task branch to GitHub and open a PR from the task branch into the session branch.

The task PR description should include enough information for review:

* Summary of changes
* Files changed
* Commands run
* Validation results
* Behavior impact
* Limitations or checks not run
* Whether model outputs changed, if relevant

Do not leave critical findings, implementation details, audit conclusions, or validation results only in the IDE final response. They must be included in committed files or the PR description.

The agent may merge the task PR into the session branch after requested validation passes and the task PR description is complete.

After merging the task PR into the session branch, delete the remote task branch unless the user instructs otherwise.

After merging the task PR, the agent should return to the session branch, update it from GitHub, and delete the local task branch when safe.

The task branch is disposable after merge. The merged task PR and the updated session branch are the reviewable records.

Local cleanup is not the workflow invariant. The required invariant is the GitHub-visible session branch, task PR, merged task result, and final PR structure.

If a merged task PR is later found to be fundamentally wrong, revert it on the session branch with a new revert task branch and PR unless the user explicitly instructs another correction method.

Otherwise, continue from the current session branch with a normal follow-up task branch and PR.

After completing task work, report:

* current session branch
* task PR number or link
* merge result
* deleted remote task branch, if deleted
* deleted local task branch, if deleted
* validation results
* any limitations

### Audit-only and analysis-only tasks

For audit-only or analysis-only tasks, do not modify production code.

If the task result needs to be reviewed later, used by ChatGPT, or used as input to later implementation, create a markdown report under `reports/`, commit only that report, open a PR from the task branch into the session branch, and merge the task PR into the session branch after the PR description is complete.

Even short audit results should use a report file when a committed artifact is needed for the task PR.

A report file is not required only when the user explicitly requests a chat-only or local-only answer, or when the task already produces another appropriate committed artifact.

### Final PR workflow

When the user asks to finish the session, create one final PR from the session branch into the source branch.

The final PR is the user-reviewed merge point.

The agent must not merge the final PR into the source branch.

The user reviews and merges the final PR.

The final PR description should summarize the full session without duplicating every task PR detail. Include:

* Session branch name
* Source branch name
* Task PR links
* High-level summary of changes
* Files or areas changed
* Validation summary
* Important validation failures or limitations, if any
* Behavior impact
* Whether model outputs changed, if relevant
* Reverted work, if any
* Any unresolved design or implementation concerns

Use task PRs and report files as the detailed record when the session contains many tasks.

The final PR should be the source of truth for final review into the source branch.

### Report files

Use the `reports/` directory when the task produces review material that should be preserved as a committed artifact.

Create a report file for:

* audit-only or analysis-only tasks that need a task PR,
* large audits,
* behavior-sensitive refactors,
* schema or validation migrations,
* module split or module boundary reviews,
* scoring, diagnostics, plotting, or config interpretation reviews,
* follow-up plans that future tasks may depend on.

A report file is not normally needed for routine changes such as small documentation edits, small dependency updates, simple bug fixes, or minor helper changes, unless the task is audit-only or the user requests a committed report.

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
