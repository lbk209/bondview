# Credit persistence diagnostic legacy and recalculation audit

## Executive recommendation

Classification: **active public diagnostic, specialized/ad hoc in implementation,
with no direct runtime callers found in the repository**.

Recommendation: **preserve unchanged for now; rewrite later using
side-effect-free shared rule-mapped logic; consider deprecation only after
external usage is checked and a compatibility window is planned**.

The current `compare_credit_stance_persistence_cases(...)` implementation is
not legacy in the sense of being marked deprecated or superseded by an equivalent
public API. Prior reports document its public result keys and classify it as a
specialized diagnostic. However, its implementation is ad hoc: it mutates the
live `exposure_stance_config`, calls `calculate_exposure_stance()` per case,
calls `trace_stance_score("credit", ...)`, and restores module state in a
`finally` block.

Exposure-stance recalculation is currently necessary only for the current
implementation path because `trace_stance_score(...)` expects the active module
state to contain matching stance outputs. The counterfactual credit states,
state pairs, stance scores, adjustment metadata, and stabilization change flags
can be computed side-effect-free from existing `self.scores` plus a temporary
credit stance config through `_build_rule_mapped_stance_score_breakdown(...)`.

## Current behavior

Function: `compare_credit_stance_persistence_cases(...)` at `module1.py:8806`.

Purpose: compare credit stance behavior across temporary persistence settings
for two credit rule-mapped state inputs:

- `credit_spread_change`
- `credit_spread_state`

Inputs:

- `cases: dict | None = None`
- `hysteresis_buffer: float = 0.05`
- `windows: dict | None = None`
- `include_diagnostics: bool = True`

Required pre-existing module state:

- `self.exposure_stance_config` must be loaded.
- `self.features` must exist.
- `self.scores` must exist.
- `self.labels` must exist.
- `self.exposure_stance` and `self.stance_scores` must exist.
- `self.exposure_stance_config["exposure_stances"]["credit"]` must exist.

The function does **not** recalculate component scores. It requires existing
`self.scores` and reuses them.

Validation:

- `hysteresis_buffer` must be numeric, not bool, and `>= 0`.
- Each case must be a mapping with integer, non-bool, `>= 1` values for
  `credit_spread_change` and `credit_spread_state`.
- Each window must be a two-item tuple/list.
- Required windows must include `covid_initial_shock`,
  `post_shock_recovery`, `tight_spread_2021q2`, and
  `late_2022_volatility`.

Default cases:

- `base_p1_p1`
- `case_a_change2_state1`
- `case_b_change1_state2`
- `case_c_change2_state2`

Default windows:

- `covid_initial_shock`: `2020-03-01` to `2020-03-31`
- `post_shock_recovery`: `2020-06-01` to `2020-06-30`
- `tight_spread_2021q2`: `2021-04-01` to `2021-06-30`
- `late_2022_volatility`: `2022-10-01` to `2022-12-31`

State mutated during execution:

- `self.exposure_stance_config` is replaced per case with a deep-copied config
  whose credit `state_stabilization` block is replaced.
- `self.stance_scores` is replaced by `calculate_exposure_stance()`.
- `self.exposure_stance` is replaced by `calculate_exposure_stance()`.

State restored in `finally`:

- `self.exposure_stance_config`
- `self.stance_scores`
- `self.exposure_stance`

State not restored because it is not mutated by this function:

- `self.features`
- `self.scores`
- `self.labels`
- `self.component_config`
- `self.data`

Outputs:

- `summary`
- `window_metrics`
- `shock_detection`
- `recovery_behavior`
- `tight_spread_behavior`
- `late_volatility`
- `full_period_stabilization`
- `diagnostics` when `include_diagnostics=True`

## What recalculating exposure stance gains

The call to `calculate_exposure_stance()` under each temporary credit
`state_stabilization` case currently provides a module state that
`trace_stance_score("credit", include_raw_input=True, include_labels=False)` can
consume.

Specifically, the live recalculation supplies:

- Counterfactual credit stance score in `self.stance_scores` and
  `self.exposure_stance`.
- Counterfactual credit stance label and strength in `self.exposure_stance`.
- Active config alignment so `trace_stance_score("credit", ...)` resolves and
  validates the counterfactual final score, stance label, and strength columns.

The diagnostic then uses `trace_stance_score(...)` to obtain:

- counterfactual raw/stabilized credit states;
- counterfactual `credit_state_pair`;
- counterfactual `credit_stance_score`;
- credit adjustment metadata;
- stabilization change flags including `state_stabilization_changed_pair`;
- raw/context columns such as `baa10y`;
- a per-case detail table used by all event-window metrics.

Outputs that cannot be derived from the already-existing final
`credit_stance_score` alone:

- Any alternate stabilized credit states under different persistence settings.
- Alternate `credit_state_pair` values.
- Alternate credit stance scores and adjustment metadata.
- Stabilization change flags under alternate persistence.
- Event-window metrics based on those alternate states/scores.

Outputs that can be derived from existing component scores plus an alternative
credit stance config:

- Counterfactual stabilized credit states.
- Counterfactual raw/stabilized state change flags.
- Counterfactual `credit_state_pair`.
- Counterfactual base rule score, adjustment, adjusted/final
  `credit_stance_score`.
- Counterfactual stance labels and strengths, using existing label helpers.

Outputs that are only post-processing of a counterfactual detail table:

- `window_metrics`
- `shock_detection`
- `recovery_behavior`
- `tight_spread_behavior`
- `late_volatility`
- `full_period_stabilization`
- `summary`

## Can existing scores support side-effect-free counterfactuals?

Yes, likely.

The key helper is `_build_rule_mapped_stance_score_breakdown(...)` at
`module1.py:2554`. It already accepts `stabilization_overrides` and builds a
rule-mapped breakdown from existing `self.scores`, including:

- source score columns;
- raw state columns;
- stabilized state columns;
- per-input stabilization change flags;
- any-stabilization-changed flag;
- rule case output;
- base rule score;
- adjustment metadata;
- final score.

For credit, the needed schema exists in `data/module1_config.yaml:766-873`:

- `rule_mapped.state_inputs`
- `state_stabilization`
- `rule_case_output`
- `stabilization_changed_any_output`
- `base_rule_score_output`
- `adjustment.metadata_outputs`
- `adjustment.adjustment_output`
- `adjusted_score_output`
- `score_output`
- `stance_output`
- `strength_output`

Current `trace_stance_score(...)` is not side-effect-free for this purpose
because it validates and appends stance label/strength columns from active
`self.exposure_stance`. That is why the current function recalculates exposure
stance before tracing. A replacement helper can avoid this requirement by:

1. building the counterfactual breakdown directly from existing `self.scores`;
2. deriving stance label and strength from the counterfactual score locally;
3. appending the same raw/context columns used by the credit trace path;
4. returning a trace-compatible detail DataFrame without mutating
   `self.exposure_stance_config`, `self.stance_scores`, or
   `self.exposure_stance`.

## Approach comparison

| Approach | Risk | Effort | Assessment |
| --- | --- | --- | --- |
| A. Keep current live mutation/recalculation path | Medium | None | Safe short-term because it is existing behavior and restores state. Not ideal for class split or diagnostics isolation. |
| B. Keep public method but rewrite internals to compute counterfactual credit stance from existing component scores without mutating `self` | Medium | Medium | Feasible and likely the right implementation direction. Requires strict old-vs-new equality checks for all tables and diagnostics. |
| C. Add a side-effect-free private helper first, then keep this method as a wrapper | Low/medium | Medium | Best path. Preserves public API, isolates counterfactual stance calculation, and supports future class split. |
| D. Deprecate/remove later if usage is absent | Medium/high | Small mechanically, high compatibility risk | Not recommended now. Repository usage is weak, but prior reports document public output contracts and external/notebook usage is unknown. |

## Usage and reference findings

Required search:

`rg -n "compare_credit_stance_persistence_cases|credit_stance_persistence|base_p1_p1|case_a_change2_state1|state_stabilization_changed_pair|late_2022_large_move_gt_1_0_count|full_period_stabilization" .`

Findings:

- Direct code definition and internal references are only in `module1.py`.
- `data/module1_config.yaml` defines
  `stabilization_changed_any_output: state_stabilization_changed_pair`.
- No tests, docs, notebooks, or runtime callers were found in the repository.
- Multiple reports mention or audit the method:
  - `reports/260630_module1_group_h_summary_display_audit.md`
  - `reports/260703_module1_public_api_audit.md`
  - `reports/260703_module1_public_api_stage1b_usage_audit.md`
  - `reports/260703_module1_stage2_diagnostic_duplication_audit.md`
  - `reports/260630_module1_remaining_cleanup_reclassification_audit.md`
  - `reports/report-20260707-module1-case-diagnostic-similarity-audit.md`

Reference classification:

- Direct runtime call: none found outside the method's own body.
- Documentation/report mention: yes, several reports.
- Historical audit mention: yes.
- Meaningful usage evidence: weak inside the repository; external usage remains
  unknown.

## Git and history findings

Commands run:

- `git log --oneline -- module1.py`
- `git log -S "compare_credit_stance_persistence_cases" -- module1.py`
- `git log -G "credit_stance_persistence|state_stabilization_changed_pair|base_p1_p1" -- module1.py`
- `git blame -L 8806,9231 module1.py`

Findings:

- `git log -S "compare_credit_stance_persistence_cases"` shows the method was
  introduced in `b305f98 Add files via upload` on `2026-06-22`.
- `git log -G "credit_stance_persistence|state_stabilization_changed_pair|base_p1_p1"`
  shows `b305f98` and `ffd4724 Prune rule mapped diagnostic compat metadata`.
- Blame shows almost the entire function still comes from `b305f98`.
- A later change, `a2afe8f Migrate Module 1 diagnostic summaries to helpers`,
  touched shared helper usage inside this function:
  `_inclusive_window_slice(...)` and `_ratio_or_na(...)`.
- The history does not show a focused commit introducing the method as a new
  intentional public API after the initial upload.
- The history does show the method was kept through later diagnostic cleanup and
  helper migration work.

History interpretation:

- It likely predates newer rule-mapped diagnostic helper cleanup and later
  genericization work.
- It appears to have been built for a specific credit persistence/stress-window
  diagnostic workflow.
- It was not marked deprecated or converted into a compatibility wrapper.
- It was updated recently enough to use shared helper primitives, suggesting it
  has not been abandoned outright.

## Legacy / compatibility classification

Classification: **active public diagnostic with specialized/ad hoc internals**.

Evidence for active public diagnostic:

- Public method on `RegimeModule`.
- Prior reports document its arguments, default cases/windows, and result keys.
- Prior Stage 2 audit recommended `keep_as_specialized_wrapper`.
- Not marked deprecated or legacy in source.

Evidence for specialized/ad hoc:

- Inline default cases/windows and required windows.
- Local closures for event-window metrics.
- Live config mutation and restore.
- Credit-specific event tables and thresholds.
- No direct runtime callers found in repository.

Uncertainty:

- External notebook or user usage cannot be ruled out from repository search.
- No runtime equality test was performed in this audit.

## Design assessment

The current mutate/recalculate/restore pattern is **acceptable only as a
temporary legacy implementation**.

It does preserve correctness through the live stance path and restores the three
mutated attributes in `finally`. However, it works against the intended class
split direction because an analysis diagnostic mutates calculator state in order
to get a counterfactual trace.

The pattern is not strictly necessary for counterfactual calculation because
existing rule-mapped helpers can compute the same core counterfactual outputs
from existing component scores and a temporary stabilization override. The
remaining event-window tables are post-processing.

The only unclear part is exact output equality. A side-effect-free replacement
should not be merged without old-vs-new checks for all public tables and the
optional `diagnostics` detail.

## Side-effect-free replacement feasibility

Minimum future implementation:

Private helper responsibility:

- Build a credit rule-mapped counterfactual diagnostic detail table for a given
  `stance_config` or `stabilization_overrides`, without mutating module state.

Inputs needed:

- existing `self.scores`;
- existing `self.features` / raw input context only for context columns such as
  `baa10y`;
- credit stance config;
- per-case stabilization overrides;
- existing rule-mapped schema/spec helpers.

Outputs needed:

- A DataFrame compatible with the current `diag` consumed by
  `compare_credit_stance_persistence_cases(...)`, including required columns:
  `credit_stance_score`, `credit_state_pair`,
  `state_stabilization_changed_change_state`,
  `state_stabilization_changed_spread_state`,
  `state_stabilization_changed_pair`,
  `credit_spread_state_category`, and `credit_spread_change_state`.
- If `include_diagnostics=True`, preserve the current diagnostics table shape
  and column order as closely as practical.

Implementation outline:

1. Resolve credit rule-mapped schema/spec.
2. Build `stabilization_overrides` from the case settings and
   `hysteresis_buffer`.
3. Call `_build_rule_mapped_stance_score_breakdown("credit", credit_config,
   stabilization_overrides=overrides)`.
4. Derive counterfactual stance label and strength from the resulting
   `credit_stance_score` if the current diagnostics detail requires them.
5. Append the same credit context parts currently supplied by
   `_rule_mapped_trace_context_parts(...)`, especially `baa10y` and prepared
   input columns.
6. Reuse the existing event-window post-processing unchanged.

`trace_stance_score("credit", ...)` compatibility is useful but not mandatory.
The better design is a private trace-compatible helper that avoids reliance on
active `self.exposure_stance`. If `trace_stance_score` is reused directly, it
will continue to force live state alignment.

Old-vs-new equality can be tested for:

- default cases/default windows;
- custom cases;
- custom windows;
- `include_diagnostics=True`;
- `include_diagnostics=False`;
- all result tables: `summary`, `window_metrics`, `shock_detection`,
  `recovery_behavior`, `tight_spread_behavior`, `late_volatility`,
  `full_period_stabilization`, and `diagnostics` when included.

The equality test must also assert that `exposure_stance_config`,
`stance_scores`, and `exposure_stance` are unchanged after the new method.

## Impact on class split

If classes split into `Module1Calculator` and `Module1Analysis`:

- This public method should live in `Module1Analysis`, not in the calculator
  core, because it is diagnostic/event-window analysis.
- `Module1Analysis` needs access to a side-effect-free stance engine or
  calculator service capable of building rule-mapped counterfactual details
  from existing component scores and temporary config/overrides.
- It should be excluded from the first class split if implementing that
  dependency would broaden the split task. Preserve it on the existing class or
  move it as a later cleanup once the side-effect-free helper exists.
- It should be marked in planning as a later cleanup/deprecation candidate, not
  removed during the split.

## Recommended next action

Conservative next action:

1. Preserve `compare_credit_stance_persistence_cases(...)` unchanged for now.
2. Do not deprecate or remove it in the upcoming curve cleanup or first class
   split.
3. Add a later task to introduce a side-effect-free private credit
   counterfactual trace helper.
4. Rewrite this method as a wrapper over that helper only after old-vs-new
   equality passes.
5. Consider formal deprecation only after checking external/notebook usage and
   providing a compatibility window.

## Behavior impact of this audit

Audit-only. No production code, YAML, schema, public API, output columns, or
model outputs were changed.
