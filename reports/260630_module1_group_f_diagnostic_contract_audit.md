# Module 1 Group F Diagnostic Contract Audit

Date: 2026-06-30

## Executive Summary

Group F should first define a generic diagnostic core for component/stance input-preparation comparisons, then migrate the credit and curve smoothing diagnostics onto that core while preserving their public APIs and output shapes. `compare_curve_move_driver_threshold_effect` fits a generic parameter-effect pattern, but should remain a specialized public wrapper over a future generic engine because its user-facing vocabulary is curve-move-driver specific.

No production scoring path should change in Group F. The current public diagnostics are diagnostic-only reconstructions of alternate raw/prepared or parameter scenarios. Production stance scoring already uses the active component and rule-mapped stance paths.

J1 affects Group F: credit adjustment mechanics should remain unchanged for now. Future F work must preserve the current credit adjustment values in the credit smoothing diagnostic until Group J defines a generic adjustment contract.

Recommended implementation split:

1. F2: build a generic diagnostic core for component input-preparation comparison and stance reconstruction contracts.
2. F3: migrate `compare_credit_input_smoothing_effect` and `compare_curve_input_smoothing_effect` behind their existing public APIs.
3. F4: migrate or wrap `compare_curve_move_driver_threshold_effect` as a parameter-effect diagnostic.

## Public Diagnostics In Scope

### `compare_credit_input_smoothing_effect`

Signature:

```python
compare_credit_input_smoothing_effect(
    windows: dict | None = None,
    include_detail: bool = True,
) -> dict
```

Returns a dictionary with:

- `summary`: one-row `DataFrame`.
- `window_summary`: one row per configured window.
- `detail`: full detail `DataFrame`, only when `include_detail=True`.

Default windows:

- `global_financial_crisis`: `2007-07-01` to `2009-06-30`
- `covid_shock`: `2020-02-01` to `2020-06-30`
- `fed_hiking_2022`: `2022-03-01` to `2022-12-31`
- `full_history`: `None` to `None`

Summary columns:

- `total_rows`
- `valid_rows`
- `credit_spread_change_score_changed_count`
- `credit_spread_change_score_mean_abs_diff`
- `credit_spread_state_score_changed_count`
- `credit_spread_state_score_mean_abs_diff`
- `credit_stance_score_changed_count`
- `credit_stance_score_changed_ratio`
- `raw_credit_score_change_count`
- `smoothed_credit_score_change_count`
- `score_change_reduction_count`
- `score_change_reduction_ratio`
- `raw_one_day_spike_count`
- `smoothed_one_day_spike_count`
- `one_day_spike_reduction_count`
- `one_day_spike_reduction_ratio`

`window_summary` includes the same columns plus:

- `window_id`
- `start`
- `end`

Detail columns built by the current implementation:

- `baa10y_change`, when present in `features`
- `baa10y`, from raw data when available, otherwise from `baa10y_level` when present in `features`
- `baa10y_change_prepared_for_credit_spread_change`
- `baa10y_level_prepared_for_credit_spread_state`
- `raw_credit_spread_change_score`
- `raw_credit_spread_state_score`
- `smoothed_credit_spread_change_score`
- `smoothed_credit_spread_state_score`
- `raw_credit_stance_score`
- `smoothed_credit_stance_score`
- `credit_stance_score_diff`
- `raw_credit_stance`
- `raw_credit_stance_strength`
- `smoothed_credit_stance`
- `smoothed_credit_stance_strength`

### `compare_curve_input_smoothing_effect`

Signature:

```python
compare_curve_input_smoothing_effect(
    windows: dict | None = None,
    include_detail: bool = True,
) -> dict
```

Returns a dictionary with:

- `summary`: one-row `DataFrame`.
- `window_summary`: one row per configured window.
- `detail`: full detail `DataFrame`, only when `include_detail=True`.

Default windows:

- `taper_tantrum_review`: `2012-08-01` to `2014-06-01`
- `fed_hiking_2022`: `2022-03-01` to `2022-12-31`
- `full_history`: `None` to `None`

Summary columns:

- `total_rows`
- `valid_rows`
- `curve_change_score_changed_count`
- `curve_change_score_mean_abs_diff`
- `curve_state_score_changed_count`
- `curve_state_score_mean_abs_diff`
- `curve_move_driver_score_changed_count`
- `curve_move_driver_score_changed_ratio`
- `curve_positioning_score_changed_count`
- `curve_positioning_score_changed_ratio`
- `raw_curve_score_change_count`
- `smoothed_curve_score_change_count`
- `score_change_reduction_count`
- `score_change_reduction_ratio`
- `raw_one_day_spike_count`
- `smoothed_one_day_spike_count`
- `one_day_spike_reduction_count`
- `one_day_spike_reduction_ratio`

`window_summary` includes the same columns plus:

- `window_id`
- `start`
- `end`

Detail columns built by the current implementation:

- `curve_10y2y_change`
- `curve_10y2y_level`
- `dgs2_change`
- `dgs10_change`
- `curve_10y2y_change_prepared_for_curve_change`
- `curve_10y2y_level_prepared_for_curve_state`
- `dgs2_change_prepared_for_curve_move_driver`
- `dgs10_change_prepared_for_curve_move_driver`
- `dgs2_change_filtered_for_curve_move_driver`
- `dgs10_change_filtered_for_curve_move_driver`
- `raw_curve_change_score`
- `raw_curve_state_score`
- `raw_curve_move_driver_score`
- `smoothed_curve_change_score`
- `smoothed_curve_state_score`
- `smoothed_curve_move_driver_score`
- `raw_curve_positioning_score`
- `smoothed_curve_positioning_score`
- `score_diff`
- `raw_curve_positioning`
- `raw_curve_positioning_strength`
- `smoothed_curve_positioning`
- `smoothed_curve_positioning_strength`

The first four feature columns are conditional on presence in `features`, but they are the configured inputs for the active curve components.

### `compare_curve_move_driver_threshold_effect`

Signature:

```python
compare_curve_move_driver_threshold_effect(
    include_detail: bool = True,
) -> dict
```

Returns a dictionary with:

- `summary`: one-row `DataFrame`.
- `detail`: full detail `DataFrame`, only when `include_detail=True`.

There is no window summary in the current public contract.

Summary columns:

- `min_abs_value`
- `total_rows`
- `valid_rows`
- `rows_with_front_end_below_threshold`
- `rows_with_long_end_below_threshold`
- `rows_with_either_side_below_threshold`
- `rows_with_both_sides_below_threshold`
- `curve_move_driver_score_changed_count_vs_no_threshold`
- `curve_move_driver_score_changed_ratio_vs_no_threshold`
- `mixed_or_unclear_count_before_threshold`
- `mixed_or_unclear_count_after_threshold`
- `mixed_or_unclear_count_change`
- `curve_positioning_score_changed_count_due_to_threshold`
- `curve_positioning_score_changed_ratio_due_to_threshold`

Detail columns built by the current implementation:

- `dgs2_change`, when present in `features`
- `dgs10_change`, when present in `features`
- `dgs2_change_prepared_for_curve_move_driver`
- `dgs10_change_prepared_for_curve_move_driver`
- `dgs2_change_filtered_for_curve_move_driver`
- `dgs10_change_filtered_for_curve_move_driver`
- `curve_move_driver_score_without_threshold`
- `curve_move_driver_score_with_threshold`
- `curve_move_driver_bucket_without_threshold`
- `curve_move_driver_bucket_with_threshold`
- `curve_positioning_score_without_threshold`
- `curve_positioning_score_with_threshold`
- `curve_positioning_score_diff_due_to_threshold`
- `curve_move_driver_score_changed_by_threshold`
- `curve_positioning_score_changed_by_threshold`

## Current Credit Diagnostic Reconstruction Flow

Production scoring path:

- production component scores are calculated through component score functions with configured input preparation;
- production credit stance is calculated through the active rule-mapped stance path;
- `_build_rule_mapped_stance_score_breakdown` and `_rule_mapped_adjusted_row` are production/trace paths and apply the current credit adjustment mechanics.

Diagnostic-only reconstruction path:

1. `compare_credit_input_smoothing_effect` calls `_credit_input_smoothing_effect_detail`.
2. `_credit_input_smoothing_effect_detail` calls `_raw_credit_component_scores_for_input_smoothing_comparison`.
3. `_raw_credit_component_scores_for_input_smoothing_comparison` recalculates `credit_spread_change` and `credit_spread_state` scores with `apply_input_preparation=False`.
4. `_credit_input_smoothing_effect_detail` compares those raw scores against production smoothed component scores.
5. `_credit_stance_score_from_component_scores` reconstructs raw credit stance scores from alternate component scores.
6. `_stabilize_credit_rule_states`, `_credit_spread_rule_row_from_states`, `_credit_spread_rule_scores`, `_credit_spread_rule_adjustments`, `_credit_spread_component_thresholds`, and `_credit_stance_state_buckets` support that diagnostic reconstruction.
7. `_credit_stance_labels_for_score` reconstructs raw credit labels/strengths for comparison against production stance labels/strengths.

The credit reconstruction is not production scoring, but it is public diagnostic behavior.

## Current Curve Diagnostic Reconstruction Flow

Production scoring path:

- production curve component scores are calculated through active component score functions with configured input preparation;
- production curve positioning stance is calculated through the active rule-mapped stance path;
- `_build_rule_mapped_stance_score_breakdown` is production/trace baseline for rule-mapped curve positioning.

Diagnostic-only reconstruction path:

1. `compare_curve_input_smoothing_effect` calls `_curve_input_smoothing_effect_detail`.
2. `_curve_input_smoothing_effect_detail` calls `_raw_curve_component_scores_for_input_smoothing_comparison`.
3. `_raw_curve_component_scores_for_input_smoothing_comparison` recalculates `curve_change`, `curve_state`, and `curve_move_driver` scores with `apply_input_preparation=False`.
4. `_curve_input_smoothing_effect_detail` compares those raw scores against production smoothed component scores.
5. `_curve_positioning_score_from_component_scores` reconstructs raw curve positioning scores from alternate component scores.
6. `_stabilize_curve_positioning_rule_buckets`, `_curve_positioning_rule_scores`, `_curve_positioning_rule_score`, `_curve_change_candidate_bucket`, `_curve_state_candidate_bucket`, `_yield_move_driver_candidate_bucket`, and `_curve_positioning_stabilization_config` support that diagnostic reconstruction.
7. `_curve_positioning_labels_for_score` reconstructs raw curve positioning labels/strengths for comparison against production labels/strengths.

This reconstruction should be replaced as a unit. Polishing individual target-specific helpers before replacing the reconstruction path is low value.

## Current Curve Move-Driver Threshold-Effect Flow

`compare_curve_move_driver_threshold_effect` is a parameter-effect diagnostic:

1. It reads the active `curve_move_driver.score.input_preparation.min_abs_value`.
2. It builds prepared and filtered diagnostic input columns through `_prepared_filtered_input_columns`.
3. It resolves front-end and long-end diagnostic inputs by role through `_diagnostic_input_spec_by_role`.
4. It calculates `curve_move_driver_score_without_threshold` from smoothed-but-unfiltered inputs.
5. It calculates `curve_move_driver_score_with_threshold` from smoothed-and-filtered inputs.
6. It reconstructs curve positioning scores for both scenarios by using production `curve_change_score` and `curve_state_score` plus the alternate move-driver score.
7. It returns one summary row and optional detail rows.

This fits a generic parameter-effect pattern: hold all other inputs fixed, vary one parameterized preparation step, recalculate the affected component, reconstruct the dependent stance, and summarize differences. The public method should remain a specialized wrapper because its summary names and below-threshold counts are specific to the curve move-driver front-end/long-end threshold semantics.

## Production Paths Versus Diagnostic-Only Paths

Production/trace paths:

- `_prepared_component_score_inputs`
- active component score calculators
- `_build_rule_mapped_stance_score_breakdown`
- `_rule_mapped_bucket_candidate`
- `_threshold_state_from_score`
- `_threshold_bucket`
- `_score_bucket`
- `_stabilize_state_series`
- `_resolve_rule_mapped_stabilization_config`
- `_rule_mapped_adjusted_row`
- `_credit_spread_state_intensity`
- `_adjust_credit_spread_rule_score`

Diagnostic-only reconstruction paths:

- `_raw_credit_component_scores_for_input_smoothing_comparison`
- `_credit_input_smoothing_effect_detail`
- `_credit_input_smoothing_summary_row`
- `_credit_stance_score_from_component_scores`
- `_credit_spread_rule_row_from_states`
- `_credit_spread_rule_scores`
- `_credit_spread_rule_adjustments`
- `_credit_spread_component_thresholds`
- `_credit_stance_state_buckets`
- `_credit_stance_labels_for_score`
- `_raw_curve_component_scores_for_input_smoothing_comparison`
- `_curve_input_smoothing_effect_detail`
- `_curve_input_smoothing_summary_row`
- `_curve_positioning_score_from_component_scores`
- `_curve_positioning_rule_scores`
- `_curve_positioning_rule_score`
- `_curve_positioning_labels_for_score`
- `_curve_change_candidate_bucket`
- `_curve_state_candidate_bucket`
- `_yield_move_driver_candidate_bucket`
- `_stabilize_credit_rule_states`
- `_stabilize_curve_positioning_rule_buckets`
- `_credit_stance_stabilization_config`
- `_curve_positioning_stabilization_config`

Public diagnostic entry points:

- `compare_credit_input_smoothing_effect`
- `compare_curve_input_smoothing_effect`
- `compare_curve_move_driver_threshold_effect`

Generic diagnostic helpers already available:

- `_prepared_filtered_input_columns`
- `_diagnostic_input_spec_by_role`
- `_diagnostic_component_names_for_target`
- `_score_input_features_for_diagnostic_components`
- `_derive_rule_mapped_diagnostic_spec_from_context`
- `_build_rule_mapped_stance_score_breakdown`
- `_rule_mapped_bucket_candidate`
- `_threshold_state_from_score`
- `_threshold_bucket`
- `_score_bucket`
- `_stabilize_state_series`
- `_resolve_rule_mapped_stabilization_config`

## Target-Specific Helpers Likely Replaceable In Group F

Likely replace as part of generic input-preparation diagnostics:

- `_raw_credit_component_scores_for_input_smoothing_comparison`
- `_raw_curve_component_scores_for_input_smoothing_comparison`
- `_credit_input_smoothing_effect_detail`
- `_curve_input_smoothing_effect_detail`
- `_credit_stance_score_from_component_scores`
- `_curve_positioning_score_from_component_scores`
- `_credit_spread_rule_scores`
- `_curve_positioning_rule_scores`
- `_credit_spread_rule_row_from_states`
- `_curve_positioning_rule_score`
- `_stabilize_credit_rule_states`
- `_stabilize_curve_positioning_rule_buckets`
- `_credit_stance_stabilization_config`
- `_curve_positioning_stabilization_config`

Likely replace or wrap as part of generic parameter-effect diagnostics:

- `compare_curve_move_driver_threshold_effect`

Likely keep public wrappers stable:

- `compare_credit_input_smoothing_effect`
- `compare_curve_input_smoothing_effect`
- `compare_curve_move_driver_threshold_effect`

## Helpers To Retain For Other Groups

Retain for Group H summary/display cleanup:

- `_credit_input_smoothing_summary_row`
- `_curve_input_smoothing_summary_row`
- `_credit_stance_labels_for_score`
- `_curve_positioning_labels_for_score`

Retain for Group I schema/validator cleanup:

- `module1_schema.py` validators, including credit adjustment and curve bucket validators
- YAML function names and rule-mapped schema fields

Retain for Group J credit adjustment decision:

- `_credit_spread_state_intensity`
- `_adjust_credit_spread_rule_score`
- `_rule_mapped_adjusted_row`
- current credit `rule_adjustments` config shape

Retain for Group K compatibility metadata:

- `_RULE_MAPPED_DIAGNOSTIC_COMPAT`
- `_derive_rule_mapped_diagnostic_spec_from_context`

Do not change stabilization-case diagnostics in Group F. Those belong to Group G.

## Candidate Generic Diagnostic Engines

### Component Input-Preparation Comparison Engine

Purpose: calculate component scores under alternate input-preparation modes and compare them against production component scores.

Required contract:

- target stance;
- component list from target inputs;
- alternate score mode, such as raw inputs with `apply_input_preparation=False`;
- production score columns;
- raw/prepared/filtered diagnostic input columns;
- score comparison columns and summary metrics.

This should be F2's first foundation because both credit and curve smoothing diagnostics need it.

### Stance Reconstruction Comparison Engine

Purpose: reconstruct a target stance from alternate component scores and compare it against production stance score/labels/strength.

Required contract:

- target stance;
- alternate component score frame;
- active rule-mapped or weighted stance config;
- output score, stance, and strength columns;
- label/strength reconstruction behavior;
- public output column aliases.

For rule-mapped stances, this should reuse `_build_rule_mapped_stance_score_breakdown` or an equivalent config-driven reconstruction with supplied score inputs, instead of duplicating target-specific rule-score helpers.

### Parameter-Effect Comparison Engine

Purpose: vary a single parameterized preprocessing or scoring setting while holding the rest of the pipeline fixed.

Required contract:

- target component;
- parameter under test;
- baseline scenario;
- alternate scenario;
- dependent stance target;
- affected component score columns;
- dependent stance score comparison columns;
- optional target-specific summary metrics.

`compare_curve_move_driver_threshold_effect` fits here, but should remain a wrapper to preserve its exact output vocabulary.

## Recommended F2/F3/F4 Split

F2: build the generic diagnostic core for component and stance input-preparation comparisons. Keep public methods untouched. Focus on internal contracts for alternate component scores, prepared/filtered inputs, and stance reconstruction.

F3: migrate `compare_credit_input_smoothing_effect` and `compare_curve_input_smoothing_effect` onto the generic core. Preserve public method signatures, result keys, summary/window/detail columns, and all values.

F4: migrate `compare_curve_move_driver_threshold_effect` to a generic parameter-effect core or wrap the generic core from the public method. Preserve the existing method signature and output vocabulary.

Do not combine F2/F3/F4. Each step needs its own equality checks.

## Behavior-Preservation Requirements

Public API requirements:

- Preserve method names and signatures.
- Preserve result keys for each `include_detail` setting.
- Preserve summary and detail column names and order where practical.
- Preserve default window ids and date bounds.
- Preserve index alignment of returned detail frames.
- Preserve missing-value handling.
- Preserve comparison tolerance behavior, currently `1e-10` for numeric score comparisons.

Credit-specific requirements:

- Preserve raw credit component score calculation with `apply_input_preparation=False`.
- Preserve production smoothed component score columns.
- Preserve raw credit stance reconstruction values.
- Preserve credit adjustment intensity and adjustment mechanics exactly, per J1.
- Preserve raw/smoothed credit label and strength outputs.

Curve-specific requirements:

- Preserve raw curve component score calculation with `apply_input_preparation=False`.
- Preserve production smoothed component score columns.
- Preserve raw curve positioning reconstruction values.
- Preserve rule case lookup behavior for curve positioning.
- Preserve curve move-driver bucket names.
- Preserve below-threshold counts and mixed/unclear counts in the threshold-effect diagnostic.

## Future Equality Checks

For `compare_credit_input_smoothing_effect(include_detail=False)`, compare:

- result keys: `summary`, `window_summary`
- summary columns listed above
- window summary columns listed above
- all summary/window values

For `compare_credit_input_smoothing_effect(include_detail=True)`, additionally compare detail columns and representative full-column values for:

- `raw_credit_spread_change_score`
- `smoothed_credit_spread_change_score`
- `raw_credit_spread_state_score`
- `smoothed_credit_spread_state_score`
- `raw_credit_stance_score`
- `smoothed_credit_stance_score`
- `credit_stance_score_diff`
- `raw_credit_stance`
- `raw_credit_stance_strength`
- `smoothed_credit_stance`
- `smoothed_credit_stance_strength`

For `compare_curve_input_smoothing_effect(include_detail=False)`, compare:

- result keys: `summary`, `window_summary`
- summary columns listed above
- window summary columns listed above
- all summary/window values

For `compare_curve_input_smoothing_effect(include_detail=True)`, additionally compare detail columns and representative full-column values for:

- `raw_curve_change_score`
- `smoothed_curve_change_score`
- `raw_curve_state_score`
- `smoothed_curve_state_score`
- `raw_curve_move_driver_score`
- `smoothed_curve_move_driver_score`
- `raw_curve_positioning_score`
- `smoothed_curve_positioning_score`
- `score_diff`
- `raw_curve_positioning`
- `raw_curve_positioning_strength`
- `smoothed_curve_positioning`
- `smoothed_curve_positioning_strength`

For `compare_curve_move_driver_threshold_effect(include_detail=False)`, compare:

- result keys: `summary`
- summary columns listed above
- all summary values

For `compare_curve_move_driver_threshold_effect(include_detail=True)`, additionally compare detail columns and values for:

- `curve_move_driver_score_without_threshold`
- `curve_move_driver_score_with_threshold`
- `curve_move_driver_bucket_without_threshold`
- `curve_move_driver_bucket_with_threshold`
- `curve_positioning_score_without_threshold`
- `curve_positioning_score_with_threshold`
- `curve_positioning_score_diff_due_to_threshold`
- `curve_move_driver_score_changed_by_threshold`
- `curve_positioning_score_changed_by_threshold`

## Functions Not To Touch In F2

Do not touch these in the first implementation step:

- public diagnostic wrappers;
- `_RULE_MAPPED_DIAGNOSTIC_COMPAT`;
- credit adjustment helpers;
- schema validators;
- YAML config;
- stabilization-case diagnostics;
- summary/display helpers beyond calling them from preserved wrappers.

## Commands Run

- `sed -n '1,260p' /home/lbk/.codex/attachments/5c84b631-eb5b-4498-818b-da8a0ac10444/pasted-text.txt`
- `git status --short --branch`
- `git fetch --prune origin`
- `git branch -r --list 'origin/codex/session/*'`
- `git log --oneline -3`
- `git switch -c codex/task/260630_1712_group_f_diagnostic_contract_audit origin/codex/session/260629_1306`
- `rg -n "compare_credit_input_smoothing_effect|_default_credit_input_smoothing_windows|_raw_credit_component_scores_for_input_smoothing_comparison|_credit_input_smoothing_effect_detail|_credit_input_smoothing_summary_row|compare_curve_input_smoothing_effect|_default_curve_input_smoothing_windows|_raw_curve_component_scores_for_input_smoothing_comparison|_curve_input_smoothing_effect_detail|_curve_input_smoothing_summary_row|compare_curve_move_driver_threshold_effect" module1.py`
- `rg -n "_credit_stance_score_from_component_scores|_credit_spread_rule_row_from_states|_credit_spread_rule_scores|_credit_spread_rule_adjustments|_credit_spread_component_thresholds|_credit_stance_state_buckets|_credit_stance_labels_for_score|_curve_positioning_score_from_component_scores|_curve_positioning_rule_scores|_curve_positioning_rule_score|_curve_positioning_labels_for_score|_curve_change_candidate_bucket|_curve_state_candidate_bucket|_yield_move_driver_candidate_bucket|_stabilize_credit_rule_states|_stabilize_curve_positioning_rule_buckets|_credit_stance_stabilization_config|_curve_positioning_stabilization_config" module1.py`
- `rg -n "_prepared_component_score_inputs|_diagnostic_input_spec_by_role|_diagnostic_component_names_for_target|_score_input_features_for_diagnostic_components|_derive_rule_mapped_diagnostic_spec_from_context|_build_rule_mapped_stance_score_breakdown|_rule_mapped_bucket_candidate|_threshold_state_from_score|_threshold_bucket|_score_bucket|_stabilize_state_series|_resolve_rule_mapped_stabilization_config" module1.py`
- `rg -n "Group F|smoothing|input-preparation|parameter-effect|credit adjustment|J1|diagnostic" reports`
- `nl -ba module1.py | sed -n '6320,7060p'`
- `nl -ba module1.py | sed -n '7060,7355p'`
- `nl -ba module1.py | sed -n '7540,7870p'`
- `nl -ba module1.py | sed -n '8020,8695p'`
- `nl -ba module1.py | sed -n '1288,1335p'`
- `nl -ba module1.py | sed -n '2490,2850p'`
- `nl -ba data/module1_config.yaml | sed -n '250,430p'`
- `nl -ba data/module1_config.yaml | sed -n '430,560p'`
- `nl -ba data/module1_config.yaml | sed -n '760,960p'`
- `nl -ba data/module1_config.yaml | sed -n '960,1095p'`
- `sed -n '1,260p' reports/260630_module1_credit_adjustment_j1_audit.md`
- `sed -n '120,285p' reports/260630_module1_remaining_cleanup_reclassification_audit.md`

## Limitations And Validation

Runtime diagnostics were not run. The audit relied on static inspection because this PR is report-only and the requested validation does not require runtime behavior checks.

No production behavior validation was required because no production code, config, schema, diagnostics, YAML, or tests changed. No Python syntax check was required because no Python files changed.

No model output changed because this PR only adds an audit report.
