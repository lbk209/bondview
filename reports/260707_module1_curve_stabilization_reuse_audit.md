# Curve positioning stabilization diagnostic helper/config audit

## Scope

This audit covers the current `compare_curve_positioning_stabilization_cases(...)`
path in `module1.py`, including:

- `_default_curve_stabilization_cases(...)`
- `_neutral_curve_positioning_stabilization_overrides(...)`
- `_default_curve_stabilization_windows(...)`
- `_rule_mapped_stabilization_case_detail_comparison(...)`
- `_curve_stabilization_case_detail(...)`
- `_curve_stabilization_summary_row(...)`
- `_curve_stabilization_window_row(...)`

The audit does not evaluate whether this public diagnostic should be merged into
`compare_smoothing_effect(...)`.

## Executive conclusion

Recommended next action: **profile cleanup plus helper reuse**, kept local and
private.

Implementation scope estimate: **medium**.

The current diagnostic already reuses the core rule-mapped stance machinery for
case detail construction. The main remaining duplication is not in scoring
logic; it is in hard-coded detail aliases, summary column access, bucket
transition setup, score distribution setup, and duplicated flag construction.

Most model-facing names can be derived from existing YAML/config/spec:
`state_inputs`, source score columns, raw/stabilized state outputs, rule-case
output, final score output, stance label output, strength label output, and
stabilization change columns. However, the public diagnostic intentionally
renames several config-derived columns, for example from
`curve_change_bucket_raw` to `raw_curve_change_bucket`. Because those public
aliases are not present in YAML, a small private profile is the best fit if
implementation proceeds. No YAML changes are needed for a conservative cleanup.

## Current dependency map

### `compare_curve_positioning_stabilization_cases(...)`

Location: `module1.py:8724`.

Role: public diagnostic entry point. Validates prerequisites, resolves the
curve-positioning stance config, resolves cases/windows, builds per-case detail,
summary, window summary, bucket transition summary, score distribution, and
optional diagnostics.

Curve-specific: yes.

Hard-coded names: yes. It directly hard-codes the bucket transition triplets,
score distribution score columns, result table keys, and public output column
names.

Config/spec-derived: only indirectly through `_curve_positioning_stance_config()`
and downstream detail construction.

Reuse status: should remain separate as the public diagnostic wrapper. It can be
made thinner by using a private profile for column groups and by extracting
bucket/score-distribution builders.

### `_curve_stabilization_case_detail(...)`

Location: `module1.py:8536`.

Role: curve-specific wrapper over
`_rule_mapped_stabilization_case_detail_comparison(...)`, supplying the target
and all public detail aliases.

Curve-specific: yes.

Hard-coded names: yes. This is the densest hard-coded mapping in the path.

Config/spec-derived: the called generic helper derives source score/state/rule
case/final score mechanics from `_resolve_rule_mapped_stance_schema(...)`, but
the wrapper's `detail_columns` mapping is hand-written.

Reuse status: should remain as a curve wrapper unless replaced by a
curve-stabilization profile builder. Safe to simplify by deriving most mapping
from `RuleMappedDiagnosticSpec` and state input metadata, while preserving the
current public aliases.

### `_rule_mapped_stabilization_case_detail_comparison(...)`

Location: `module1.py:8411`.

Role: generic-ish detail constructor for baseline-vs-case rule-mapped
stabilization comparison. It resolves the rule-mapped stance schema, computes
baseline and case breakdowns with different stabilization overrides, copies
score inputs/states/rule cases/scores, derives labels, derives mismatch flags,
and builds score-change and one-day-spike flags.

Curve-specific: partly. The function accepts generic `stance_name` and
`detail_columns`, but its assumptions are specialized to baseline-vs-case
stabilization diagnostics.

Hard-coded names: no public curve names inside the helper, but hard-coded
`detail_columns` keys define its private mapping contract.

Config/spec-derived: yes for state input names, source score columns,
raw/stabilized state output columns, rule-case output, and score output via
`_resolve_rule_mapped_stance_schema(...)` and
`_build_rule_mapped_stance_score_breakdown(...)`.

Reuse status: should remain separate. It is already the local reusable core for
this diagnostic family. It could safely reuse a small helper for score-change
flag generation and one-day-spike flag generation, but that should be validated
for identical dtype and first-valid-row behavior.

### `_curve_stabilization_summary_row(...)`

Location: `module1.py:8599`.

Role: builds one summary row per case with score differences, score/direction/
strength change rates, transition counts, spike counts, bucket transition totals,
and dominant label values.

Curve-specific: yes.

Hard-coded names: yes. It directly references raw/stabilized score, score diff,
change flags, state bucket columns, and label/strength columns.

Config/spec-derived: no, except that it consumes columns produced earlier from
config-derived mechanics.

Reuse status: should remain a distinct summary shape. It can use a profile to
resolve columns and can continue using existing primitive helpers. Replacing it
with `_rule_mapped_input_smoothing_summary_row(...)` is unsafe because output
column names, metric grouping, one-sided missing semantics, and prefixes differ.

### `_curve_stabilization_window_row(...)`

Location: `module1.py:8683`.

Role: builds one window-level summary row per case/window.

Curve-specific: yes.

Hard-coded names: yes. It references raw/stabilized score, score diff, change
flag, rule-case, direction, and strength columns.

Config/spec-derived: no, except through prior detail construction.

Reuse status: should remain a distinct window summary shape. It already safely
uses `_inclusive_window_slice(...)`. `_window_summary_row(...)` is not a useful
drop-in because this function needs `case_id`, `obs_count`, and custom metrics,
not just a copied summary row with window metadata.

### `_default_curve_stabilization_cases(...)`

Location: `module1.py:8119`.

Role: hard-coded scenario catalog.

Curve-specific: yes.

Hard-coded names: yes. Case override keys are the curve rule-mapped state input
names: `curve_change`, `curve_state`, and `curve_move_driver`.

Config/spec-derived: only the neutral case delegates to
`_neutral_curve_positioning_stabilization_overrides(...)`.

Reuse status: should remain explicit for scenario design. The neutral case can
be derived from config/spec without changing YAML. The non-neutral scenario
values are diagnostic policy, not model structure, and should not be inferred
from YAML.

### `_neutral_curve_positioning_stabilization_overrides(...)`

Location: `module1.py:8145`.

Role: returns the baseline no-hysteresis/no-persistence stabilization override
for each curve state input.

Curve-specific: yes in its current spelling.

Hard-coded names: yes. It hard-codes the three state input names.

Config/spec-derived: no.

Reuse status: safe to replace with a small helper that derives neutral overrides
from `spec.state_inputs`: every state input gets `hysteresis_buffer: 0.0` and
`min_state_persistence: 1`.

### `_default_curve_stabilization_windows(...)`

Location: `module1.py:8155`.

Role: hard-coded event windows plus full history.

Curve-specific: yes.

Hard-coded names: yes, but these are event/window identifiers and dates, not
model output columns.

Config/spec-derived: no.

Reuse status: should remain separate unless a later task explicitly moves
default windows to historical context. Existing `_smoothing_diagnostic_windows`
uses `historical_context`; adopting it here would add a loading dependency and
could change defaults.

## Existing helper reuse assessment

| Area | Current state | Reuse classification | Notes |
| --- | --- | --- | --- |
| Window slicing | `_curve_stabilization_window_row(...)` already uses `_inclusive_window_slice(...)`. | Safe reuse now | No further change needed. |
| Window row construction | Custom row assembly. `_window_summary_row(...)` only copies a row and adds `window_id`, `start`, `end`. | Not worth reusing | Current output includes `case_id` and window-specific metrics, so using `_window_summary_row(...)` would add indirection without removing much logic. |
| Score/direction/strength mismatch detection | `_rule_mapped_stabilization_case_detail_comparison(...)` already uses `_series_mismatch_mask(...)`. | Safe reuse now | Keep this helper. Tolerance is used for scores only. |
| Score transition counts | Summary/window/bucket paths use `_count_series_changes(...)`; detail flags duplicate related logic. | Possible reuse with small adapter | Counts are already reused. Detail flags need a helper returning a boolean Series with the current first-valid row forced to `False`. |
| One-day spike counts | Summary/window use `_count_one_day_spikes(...)`; detail flags duplicate related logic. | Possible reuse with small adapter | A new private `_one_day_spike_flag_series(...)` could feed both counts and flags, but must preserve current index alignment and boolean dtype. |
| Ratio calculation | `_ratio_or_na(...)` is already used. | Safe reuse now | No change needed. |
| Dominant-value calculation | `_curve_dominant_value(...)` is already used. | Safe reuse now | Despite the name, logic is generic. Renaming it could be cleanup but is not required. |
| Pair-level score comparison metrics | `_smoothing_pair_comparison_metrics(...)` exists. | Unsafe | It includes aligned/one-sided missing behavior and mean abs diff semantics that do not match the current stabilization summary output. |
| Detail construction from rule-mapped breakdowns | `_rule_mapped_stabilization_case_detail_comparison(...)` already calls `_build_rule_mapped_stance_score_breakdown(...)`. | Safe reuse now | This is the strongest existing reuse. A profile can reduce the hard-coded alias map. |
| Score distribution construction | Manual `dropna().value_counts().sort_index()` loop. | Possible reuse with small adapter | `_rule_mapped_score_distribution(...)` is similar but not shape-compatible; a tiny local helper can preserve `case_id`, `score_type`, `score`, `count`, `ratio`. |
| Bucket transition summary construction | Manual loop over three bucket triplets. | Possible reuse with small adapter | Can be generated from profile state pairs while preserving `bucket_type` aliases and output columns. |

## Hard-coded column/name audit

### YAML/config-derived and should be resolved from config/spec where practical

These names already exist in `data/module1_config.yaml` or can be resolved
through `_resolve_rule_mapped_stance_schema(...)` and
`RuleMappedDiagnosticSpec`:

- `curve_change_score`: `state_inputs[].source_score` at
  `data/module1_config.yaml:986-988`.
- `curve_state_score`: `state_inputs[].source_score` at
  `data/module1_config.yaml:996-998`.
- `curve_move_driver_score`: `state_inputs[].source_score` at
  `data/module1_config.yaml:1007-1009`.
- `curve_change`, `curve_state`, `curve_move_driver`: `state_inputs[].name`.
- `curve_change_bucket_raw`, `curve_change_bucket`,
  `curve_state_bucket_raw`, `curve_state_bucket`,
  `yield_move_driver_bucket_raw`, `yield_move_driver_bucket`:
  `state_inputs[].raw_output` and `state_inputs[].stabilized_output`.
- `curve_positioning_rule_case`: `rule_case_output` at
  `data/module1_config.yaml:1021`.
- `curve_positioning_score`: `score_output` at
  `data/module1_config.yaml:1024`.
- `curve_positioning`: `stance_output` at
  `data/module1_config.yaml:1025`.
- `curve_positioning_strength`: `strength_output` at
  `data/module1_config.yaml:1026`.
- `state_stabilization_changed_curve_change`,
  `state_stabilization_changed_curve_state`,
  `state_stabilization_changed_curve_move_driver`,
  `state_stabilization_changed_any`: existing stabilization change metadata,
  though the stabilization case diagnostic does not currently expose those names.

### Public output columns that should be preserved

These are public diagnostic aliases in detail/summary outputs. They can be
generated by a profile, but their values should not be renamed in a cleanup:

- `raw_curve_change_bucket`
- `stabilized_curve_change_bucket`
- `raw_curve_state_bucket`
- `stabilized_curve_state_bucket`
- `raw_yield_move_driver_bucket`
- `stabilized_yield_move_driver_bucket`
- `raw_curve_positioning_rule_case`
- `stabilized_curve_positioning_rule_case`
- `raw_curve_positioning_score`
- `stabilized_curve_positioning_score`
- `raw_curve_positioning`
- `stabilized_curve_positioning`
- `raw_curve_positioning_strength`
- `stabilized_curve_positioning_strength`
- `score_diff`
- `score_changed`
- `direction_changed`
- `strength_changed`
- `raw_score_change_flag`
- `stabilized_score_change_flag`
- `raw_one_day_spike_flag`
- `stabilized_one_day_spike_flag`

### Diagnostic output aliases that may reasonably remain hard-coded

These table/result names are diagnostic API vocabulary rather than model
structure:

- Result keys: `summary`, `window_summary`, `detail_by_case`,
  `bucket_transition_summary`, `score_distribution`, `diagnostics_by_case`.
- Summary/window columns such as `case_id`, `total_rows`, `valid_rows`,
  `obs_count`, `mean_raw_score`, `mean_stabilized_score`, `mean_score_diff`,
  `mean_abs_score_diff`, `max_abs_score_diff`, `changed_score_count`,
  `changed_score_ratio`, `raw_score_change_count`,
  `stabilized_score_change_count`, `score_change_reduction_count`,
  `score_change_reduction_ratio`, `one_day_spike_count_raw`,
  `one_day_spike_count_stabilized`, `one_day_spike_reduction_count`,
  `one_day_spike_reduction_ratio`, `bucket_change_count_raw`,
  `bucket_change_count_stabilized`, and dominant-value columns.
- Bucket transition table columns: `bucket_type`, `raw_change_count`,
  `stabilized_change_count`, `change_reduction_count`,
  `change_reduction_ratio`.
- Score distribution table columns: `score_type`, `score`, `count`, `ratio`.

### Internal temporary columns that could be generated from a profile

- Score-change flag columns: `raw_score_change_flag`,
  `stabilized_score_change_flag`.
- Spike flag columns: `raw_one_day_spike_flag`,
  `stabilized_one_day_spike_flag`.
- Bucket transition field pairs used by the loop at `module1.py:8756-8759`.
- Score distribution field pairs used by the loop at `module1.py:8776-8778`.

### Curve-specific semantic names that probably should remain explicit

- Public case IDs: `neutral_base`, `persistence_3`, `hysteresis_005`,
  `hysteresis_005_persistence_3`, `hysteresis_010_persistence_3`.
- Default window IDs and dates:
  `taper_tantrum_review`, `fed_hiking_2022`, `covid_shock_2020`,
  `full_history`.
- The public bucket alias `yield_move_driver` in `bucket_type`, because YAML
  stores state input name `curve_move_driver` but diagnostic component
  `yield_move_driver`; preserving current output likely matters more than
  deriving this label mechanically.

## YAML/config/spec-driven feasibility

Existing config/spec can provide the following without YAML changes:

- State input names: `_RuleMappedStateInputSpec.name`, parsed from
  `rule_mapped.state_inputs[].name`.
- Component names: `_RuleMappedStateInputSpec.component_name`, plus
  `diagnostic_component` where configured.
- Source score columns: `_RuleMappedStateInputSpec.source_score_col`.
- Raw/stabilized state output columns:
  `_RuleMappedStateInputSpec.raw_output_col` and
  `_RuleMappedStateInputSpec.stabilized_output_col`.
- Rule-case output column: `_RuleMappedStanceSpec.rule_case_output_col`, exposed
  as `RuleMappedDiagnosticSpec.rule_case_col`.
- Final score output column: config `score_output`, exposed as
  `RuleMappedDiagnosticSpec.final_score_col`.
- Stance label output column: config `stance_output`, exposed as
  `RuleMappedDiagnosticSpec.stance_label_col`.
- Strength label output column: config `strength_output`, exposed as
  `RuleMappedDiagnosticSpec.strength_label_col`.
- Stabilization change columns:
  `RuleMappedDiagnosticSpec.stabilization_change_cols` and
  `stabilization_change_any_col`.

Existing config/spec does not provide:

- Current public diagnostic aliases with `raw_`/`stabilized_` prefixes and
  `bucket` wording.
- The special public alias `yield_move_driver` for the state input named
  `curve_move_driver`.
- Current score-change and one-day-spike flag output column names.
- Summary/window output column names.
- Bucket transition and score distribution table schemas.
- Default non-neutral scenario catalog.
- Default windows.

Classification: **possible with existing config/spec plus small private
profile**.

No YAML changes are needed for a conservative cleanup. YAML diagnostic metadata
would only be justified if the project wants these public diagnostic aliases to
become explicit model/reporting configuration rather than private API
compatibility code.

## Potential private profile

A private profile would help. It should be derived mostly from
`RuleMappedDiagnosticSpec` plus a small alias layer, similar in spirit to
`SmoothingDiagnosticTargetProfile` at `module1.py:153-168` and
`_smoothing_diagnostic_target_profile(...)` at `module1.py:7586-7618`.

Useful fields:

- `target` / `display_target`
- `spec`
- state pairs: input name, bucket type alias, source score column,
  raw detail alias, stabilized detail alias
- raw/stabilized rule-case aliases
- raw/stabilized final score aliases
- score diff alias
- raw/stabilized stance label aliases
- raw/stabilized strength label aliases
- score/direction/strength changed aliases
- raw/stabilized score-change flag aliases
- raw/stabilized one-day-spike flag aliases
- summary/window column groups if needed
- score distribution fields

The profile can be mostly derived:

- `raw_{spec.final_score_col}` and `stabilized_{spec.final_score_col}` produce
  the current score aliases.
- `raw_{spec.stance_label_col}` and `stabilized_{spec.stance_label_col}` produce
  the current direction aliases.
- `raw_{spec.strength_label_col}` and `stabilized_{spec.strength_label_col}`
  produce the current strength aliases.
- `raw_{spec.rule_case_col}` and `stabilized_{spec.rule_case_col}` produce the
  current rule-case aliases.
- State bucket aliases can be generated from each state input's configured
  `raw_output` / `stabilized_output` by moving `_raw` to a `raw_` prefix and
  replacing the stabilized config name with a `stabilized_` prefix.

The profile still needs small explicit decisions:

- Keep `score_diff` instead of deriving `curve_positioning_score_diff`.
- Keep `score_changed`, `direction_changed`, and `strength_changed`.
- Keep score/spike flag names.
- Preserve `yield_move_driver` as the public bucket type alias for
  `curve_move_driver`.
- Preserve default cases and default windows as explicit diagnostic policy.

## Implementation scope estimate

Category: **medium**.

Why:

- Small pieces are safe: deriving neutral overrides from state inputs; moving
  hard-coded detail mappings into a private profile; adding tiny helpers for
  score-change flags, spike flags, bucket transition rows, and score
  distribution rows.
- The change touches multiple output-producing paths:
  detail, summary, window summary, bucket transition summary, score
  distribution, and optional diagnostics alias. Those outputs are public
  diagnostic contract, so equality checks are required.
- A larger rewrite is not justified. Replacing summaries with smoothing helpers
  or adding YAML metadata would increase risk without clear benefit.

## Recommended next action

Recommendation: **profile cleanup plus helper reuse**.

Conservative implementation boundaries:

- Do not change the public method signature.
- Do not change result keys.
- Do not change DataFrame columns, ordering, values, dtypes, or NaN behavior.
- Do not add YAML fields initially.
- Keep default case and window catalogs explicit.
- Build a private curve-stabilization profile from existing
  rule-mapped config/spec, with minimal explicit aliases only where current
  public output names cannot be derived safely.
- Add or reuse small helpers only where equality can be proven.

If implementation time is constrained, the smaller first step is:

- derive neutral overrides from `spec.state_inputs`;
- centralize detail/bucket/score columns into a private profile;
- leave summary/window row bodies structurally similar but profile-driven.

## Future validation plan

If implementation proceeds, run:

- `python -m py_compile module1.py`
- `git diff --check`
- `rg -n "raw_curve_change_bucket|stabilized_curve_change_bucket|raw_curve_positioning_score|stabilized_curve_positioning_score|raw_score_change_flag|stabilized_score_change_flag|raw_one_day_spike_flag|stabilized_one_day_spike_flag" module1.py`
- `rg -n "_curve_stabilization_case_detail|_rule_mapped_stabilization_case_detail_comparison|_curve_stabilization_summary_row|_curve_stabilization_window_row" module1.py`

Old-vs-new equality checks should compare
`compare_curve_positioning_stabilization_cases(...)` outputs for:

- default cases and default windows;
- explicit custom cases;
- explicit custom windows;
- `include_diagnostics=True`;
- `include_diagnostics=False`.

Equality coverage should include:

- `summary`
- `window_summary`
- `detail_by_case`
- `bucket_transition_summary`
- `score_distribution`
- `diagnostics_by_case` when requested

The equality harness should check DataFrame column order, index, values, dtypes
where practical, and `pd.NA`/`NaN` behavior.

## Behavior impact of this audit

No production code or YAML was changed. Model outputs are unchanged.
