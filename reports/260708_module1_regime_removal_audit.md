# Module 1 RegimeModule Removal Audit

## Recommendation

Not safe yet; keep `RegimeModule` as a temporary compatibility wrapper.

`Module1Calculator` now owns setup and the full runtime calculation pipeline, and
direct calculator usage can replace current runtime-only usage. Immediate
`RegimeModule` removal would still break public non-runtime workflows that have
not moved to `Module1Analysis` or another owner.

## Cleanup Completed

Removed duplicated private runtime helpers from `RegimeModule` when they were no
longer called by remaining non-runtime `RegimeModule` methods:

- `_apply_sign`
- `_apply_state_persistence`
- `_bucket_matches_value`
- `_calculate_exposure_stance_score`
- `_calculate_feature_from_definition`
- `_classify_state_series_with_hysteresis`
- `_component_bucket_config`
- `_component_bucket_for_score`
- `_component_bucket_labels`
- `_component_bucket_style`
- `_copy_module1_result_value`
- `_fixed_anchor_state_score`
- `_get_horizon`
- `_get_input_series`
- `_is_ordered_threshold_bucket_config`
- `_lookup_rule_score`
- `_normalize_score_input`
- `_ordered_threshold_bucket_hysteresis_candidate`
- `_ordered_threshold_buckets`
- `_prepared_component_score_inputs`
- `_resolve_component_name_for_score_output`
- `_rule_case_from_states`
- `_rule_mapped_adjusted_row`
- `_rule_mapped_bucket_candidate`
- `_rule_mapped_bucket_config_for_input`
- `_rule_mapped_thresholds_for_input`
- `_rule_state_is_missing`
- `_smooth_score`
- `_stance_weight_terms`
- `_threshold_bucket`
- `_threshold_bucket_hysteresis_candidate`
- `_threshold_state_from_score`
- `_threshold_tail_default_bucket_parts`
- `_validate_required_score_columns`
- `_value_in_expanded_interval`
- `_weighted_sum_score`

## Runtime Helpers Kept As Delegates

These duplicated helpers are still called by non-runtime `RegimeModule` methods,
so they were kept as thin wrappers that delegate to `self.calculator`:

- `_prepare_component_input_series`
- `_clip_score`
- `_calculate_single_feature_component_score`
- `_calculate_weighted_feature_component_score`
- `_calculate_curve_move_driver_score`
- `_curve_move_driver_bucket_scores`
- `_component_score_bucket_config`
- `_resolve_rule_mapped_stance_schema`
- `_score_bucket`
- `_calculate_current_state_component_score`
- `_label_stance_direction`
- `_label_stance_strength`
- `_build_weighted_stance_score_breakdown`
- `_build_rule_mapped_stance_score_breakdown`
- `_credit_spread_state_intensity`
- `_stabilize_state_series`
- `_threshold_hysteresis_candidate`
- `_adjust_credit_spread_rule_score`
- `_curve_move_driver_score_from_prepared_inputs`

Public runtime compatibility methods also remain as delegates:

- `calculate_features`
- `align_component_scores`
- `calculate_component_scores`
- `calculate_component_labels`
- `calculate_exposure_stance`
- `run_module1_pipeline`
- `to_module1_result`

## Remaining RegimeModule-Only Public Methods

The following public methods are still available only through `RegimeModule`:

- `compare_credit_stance_persistence_cases`
- `compare_curve_move_driver_threshold_effect`
- `compare_curve_positioning_stabilization_cases`
- `compare_horizon_cases`
- `compare_smoothing_effect`
- `diagnose_rule_mapped_stance`
- `load_historical_context`
- `plot_historical_review_case`
- `plot_target_comparison`
- `review_historical_cases`
- `run_module1_historical_review`
- `save_data`
- `trace_stance_score`
- `validate_historical_expected_labels`

## Repository Reference Audit

Tracked non-report files do not instantiate `RegimeModule` outside `module1.py`.
The only non-report matches are the class definition and comments/docstrings.
Prior reports document older `RegimeModule` public API usage and migration
rationale, but they are historical artifacts rather than executable callers.

No tracked notebooks were found in the repository.

## What Would Break If Removed Now

Immediate removal would break:

- historical review loading, validation, case review, and historical review
  convenience workflows;
- plotting workflows for historical review cases and target comparisons;
- stance tracing and rule-mapped diagnostics;
- smoothing, curve threshold, curve stabilization, and credit persistence
  sensitivity diagnostics;
- target-context compatibility APIs still implemented on `RegimeModule`;
- public `save_data` and horizon-case comparison helpers.

## Next Required Migration Step

Migrate or explicitly retire the remaining non-runtime public workflows before
removing `RegimeModule`. The highest-impact next split is to move historical
review, tracing/diagnostics, plotting, and target-context compatibility into
dedicated owners or result-only APIs, then leave `RegimeModule` as a pure facade
or remove it after external API compatibility is addressed.
