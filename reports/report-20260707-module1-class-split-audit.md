# Module 1 class split ownership audit

## Executive Recommendation

Split `RegimeModule` conservatively. The first implementation PR should
introduce a `Module1Result` snapshot without moving behavior. Most current
runtime calculation and reusable scoring mechanics belong in `Module1Calculator`.
Pure read-only summaries and target context helpers can move later to
`Module1Analysis`. Historical review and historical plotting should move only
after the result snapshot and historical-context boundary are explicit.
Sensitivity diagnostics should be deferred until they can depend on
side-effect-free calculation helpers.

Do **not** change `module1_schema.py` for the first class split unless the YAML
contract changes. This audit found no need for new YAML fields, renamed config
fields, or changed schema semantics for the split itself.

Highest-risk methods to defer:

- `compare_horizon_cases(...)`
- `compare_smoothing_effect(...)`
- `compare_curve_move_driver_threshold_effect(...)`
- `compare_curve_positioning_stabilization_cases(...)`
- `compare_credit_stance_persistence_cases(...)`
- `review_historical_cases(...)`
- `plot_historical_review_case(...)`
- `plot_target_comparison(...)`
- `get_target_context(...)` and `build_target_comparison_dataset(...)` if
  `context_id` support remains coupled to loaded historical context

## Proposed Target Class Structure

- `Module1Calculator`: owns loading config/data, resolving horizons, calculating
  features, component scores, labels, stance scores, and exposure stance. It
  should produce a `Module1Result`.
- `Module1Result`: immutable or read-only snapshot of completed outputs and
  config snapshots needed by analysis.
- `Module1Analysis`: consumes `Module1Result` only. It should not recalculate
  features, scores, labels, or stances and should not mutate runtime state.
- `Module1HistoricalAnalysis`: consumes `Module1Result` plus historical context
  or historical cases.
- `Module1SensitivityDiagnostics`: owns recalculation, reconstruction,
  smoothing/no-smoothing comparisons, threshold sensitivity, horizon cases,
  stabilization cases, and temporary/counterfactual configurations.
- `RegimeModule` compatibility facade: can remain temporarily to preserve public
  method names while delegating to the split classes.

## Full Method Inventory

This inventory lists every current `RegimeModule` method with proposed owner and
main dependency class. `R` means read-only dependency, `W` means state mutation,
and `CF` marks recalculation/reconstruction/counterfactual behavior.

| Line | Method | Owner | Dependency / Side-Effect Summary |
|---:|---|---|---|
| 219 | `__init__` | `Module1Calculator` | W: initializes all runtime state and loads core files. |
| 268 | `load_core_files` | `Module1Calculator` | R/W via loaders: config/data setup. |
| 298 | `_default_horizons_from_config` | `Module1Calculator` | R: `module1_config`. |
| 320 | `validate_horizons` | `Module1Calculator` | Pure horizon validation. |
| 365 | `update_horizons` | `Module1Calculator` | W: `horizon_overrides`, `horizons`. |
| 389 | `_build_horizon_cases_df` | `Module1SensitivityDiagnostics` | CF: normalizes horizon case grid. |
| 464 | `compare_horizon_cases` | `Module1SensitivityDiagnostics` | CF: creates temporary module, recalculates pipeline, uses historical review. |
| 629 | `load_series_config` | `Module1Calculator` | Cache/setup for series config. |
| 645 | `download_series` | `Module1Calculator` | Data acquisition helper. |
| 668 | `check_frequency_sanity` | `Module1Calculator` | Data quality check. |
| 682 | `load_local_data` | `Module1Calculator` | Data loader. |
| 714 | `load_data` | `Module1Calculator` | W: `data`. |
| 748 | `save_data` | `Module1Calculator` | R: `data`; persistence utility. |
| 779 | `_load_yaml_config` | `Module1Calculator` | YAML loader. |
| 795 | `load_module1_config` | `Module1Calculator` | W: config snapshots and `horizons`. |
| 843 | `_get_horizon` | `Module1Calculator` | R: `horizons`. |
| 856 | `_get_input_series` | `Module1Calculator` | R: `data`. |
| 866 | `_calculate_feature_from_definition` | `Module1Calculator` | R: `data`; feature mechanic. |
| 914 | `calculate_features` | `Module1Calculator` | R: `data`, `feature_config`; W: `features`. |
| 948 | `_normalize_score_input` | `Module1Calculator` | R: `horizons`. |
| 979 | `_smooth_score` | `Module1Calculator` | R: `horizons`. |
| 992 | `_prepare_component_input_series` | `Module1Calculator` | Component input mechanic. |
| 1013 | `_prepared_component_score_inputs` | `Module1Calculator` | R: `features`. |
| 1065 | `_clip_score` | `Module1Calculator` | Pure score helper. |
| 1075 | `_apply_sign` | `Module1Calculator` | Pure score helper. |
| 1085 | `_fixed_anchor_state_score` | `Module1Calculator` | Pure score helper. |
| 1121 | `_weighted_sum_score` | `Module1Calculator` | Pure score helper. |
| 1134 | `align_component_scores` | `Module1Calculator` | R/W: `scores`; R: `features`. |
| 1149 | `_calculate_single_feature_component_score` | `Module1Calculator` | R: `features`. |
| 1176 | `_calculate_weighted_feature_component_score` | `Module1Calculator` | R: `features`. |
| 1231 | `_calculate_curve_move_driver_score` | `Module1Calculator` | Component score mechanic. |
| 1254 | `_curve_move_driver_bucket_scores` | `Module1Calculator` | Component config mechanic. |
| 1281 | `_component_score_bucket_config` | `Module1Calculator` | R: `component_config`. |
| 1299 | `_rule_state_is_missing` | `Module1Calculator` | Pure rule helper. |
| 1310 | `_rule_case_from_states` | `Module1Calculator` | Pure rule helper. |
| 1323 | `_lookup_rule_score` | `Module1Calculator` | Pure rule helper. |
| 1348 | `_validate_required_score_columns` | `Module1Calculator` | R: `scores`. |
| 1382 | `_resolve_component_name_for_score_output` | `Module1Calculator` | R: `component_config`. |
| 1410 | `_resolve_rule_mapped_stance_schema` | `Module1Calculator` | R: `component_config`; core schema interpretation. |
| 1693 | `_bucket_matches_value` | `Module1Calculator` | Pure bucket helper. |
| 1704 | `_threshold_bucket` | `Module1Calculator` | Pure bucket helper. |
| 1722 | `_score_bucket` | `Module1Calculator` | Pure bucket helper. |
| 1740 | `_component_bucket_config` | `Module1Calculator` | R: `component_config`. |
| 1757 | `_component_bucket_labels` | `Module1Calculator` | R: `component_config`. |
| 1774 | `_component_bucket_style` | `Module1Calculator` | Pure bucket helper. |
| 1796 | `_component_bucket_for_score` | `Module1Calculator` | Pure bucket helper. |
| 1802 | `_calculate_current_state_component_score` | `Module1Calculator` | R: `features`. |
| 1904 | `_calculate_component_score_for_input_preparation_diagnostic` | `Module1SensitivityDiagnostics` | CF helper for alternate prepared inputs. |
| 1958 | `_recalculate_component_scores_for_input_preparation_diagnostic` | `Module1SensitivityDiagnostics` | CF: recalculates diagnostic component scores from existing features. |
| 1996 | `_stance_labels_for_score` | `unclear / shared helper` | R: stance label config; usable by calculator and diagnostics. |
| 2028 | `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic` | `Module1SensitivityDiagnostics` | CF; temporary W/R: `scores`. |
| 2074 | `_rule_mapped_component_parameter_effect_detail` | `Module1SensitivityDiagnostics` | CF parameter-effect detail helper. |
| 2145 | `calculate_component_scores` | `Module1Calculator` | R: `features`, `component_config`; W: `scores`. |
| 2214 | `calculate_component_labels` | `Module1Calculator` | R: `scores`, `component_config`; W: `labels`. |
| 2293 | `_label_stance_direction` | `Module1Calculator` | Pure label helper. |
| 2311 | `_label_stance_strength` | `Module1Calculator` | Pure label helper. |
| 2340 | `_build_weighted_stance_score_breakdown` | `Module1Calculator` | R: `scores`. |
| 2368 | `_rule_mapped_thresholds_for_input` | `Module1Calculator` | R: `component_config`. |
| 2406 | `_rule_mapped_bucket_config_for_input` | `Module1Calculator` | R: `component_config`. |
| 2423 | `_rule_mapped_bucket_candidate` | `Module1Calculator` | Core rule-mapped helper. |
| 2453 | `_threshold_tail_default_bucket_parts` | `Module1Calculator` | Pure config helper. |
| 2473 | `_is_ordered_threshold_bucket_config` | `Module1Calculator` | Pure config helper. |
| 2486 | `_rule_mapped_adjusted_row` | `Module1Calculator` | Core stance score helper. |
| 2554 | `_build_rule_mapped_stance_score_breakdown` | `Module1Calculator` | R: `scores`; core side-effect-free stance engine. |
| 2709 | `_threshold_bucket_hysteresis_candidate` | `Module1Calculator` | Core stabilization helper. |
| 2755 | `_ordered_threshold_buckets` | `Module1Calculator` | Pure config helper. |
| 2790 | `_value_in_expanded_interval` | `Module1Calculator` | Pure bucket helper. |
| 2816 | `_ordered_threshold_bucket_hysteresis_candidate` | `Module1Calculator` | Core stabilization helper. |
| 2853 | `_threshold_state_from_score` | `Module1Calculator` | Pure state helper. |
| 2867 | `_credit_spread_component_thresholds` | `Module1Calculator` | R: `component_config`. |
| 2896 | `_credit_spread_rule_scores` | `Module1Calculator` | Credit rule helper. |
| 2913 | `_credit_stance_state_buckets` | `Module1Calculator` | Credit rule helper. |
| 2937 | `_credit_spread_rule_adjustments` | `Module1Calculator` | Credit rule helper. |
| 2948 | `_credit_spread_state_intensity` | `Module1Calculator` | Credit rule helper. |
| 2973 | `_credit_stance_stabilization_config` | `Module1Calculator` | Credit stabilization config helper. |
| 3001 | `_apply_state_persistence` | `Module1Calculator` | Core stabilization helper. |
| 3048 | `_classify_state_series_with_hysteresis` | `Module1Calculator` | Core stabilization helper. |
| 3074 | `_stabilize_state_series` | `Module1Calculator` | Core stabilization helper. |
| 3093 | `_threshold_hysteresis_candidate` | `Module1Calculator` | Core stabilization helper. |
| 3132 | `_stabilize_credit_rule_states` | `Module1Calculator` | Legacy credit rule path helper. |
| 3218 | `_adjust_credit_spread_rule_score` | `Module1Calculator` | Credit adjustment helper. |
| 3245 | `_credit_spread_rule_row_from_states` | `Module1Calculator` | Credit adjustment helper. |
| 3307 | `_calculate_exposure_stance_score` | `Module1Calculator` | Core stance score dispatcher. |
| 3345 | `calculate_exposure_stance` | `Module1Calculator` | R: `scores`; W: `stance_scores`, `exposure_stance`. |
| 3417 | `run_module1_pipeline` | `Module1Calculator` | Pipeline orchestration; recalculates all model layers. |
| 3430 | `load_historical_context` | `Module1HistoricalAnalysis` | W: `historical_context`, `historical_cases`, validation result. |
| 3537 | `_valid_historical_label_vocabularies` | `Module1HistoricalAnalysis` | R: config snapshots. |
| 3583 | `_validate_historical_expected_labels_from_cases` | `Module1HistoricalAnalysis` | Historical expected-label validation. |
| 3749 | `validate_historical_expected_labels` | `Module1HistoricalAnalysis` | W: `historical_expected_label_validation`. |
| 3797 | `_normalize_review_label` | `Module1HistoricalAnalysis` | Historical label normalization. |
| 3804 | `_historical_review_target_aliases` | `Module1HistoricalAnalysis` | R: config snapshots. |
| 3846 | `_historical_review_target_groups` | `Module1HistoricalAnalysis` | R: `module1_config`. |
| 3864 | `_build_historical_cases` | `Module1HistoricalAnalysis` | Builds historical case table from context/config. |
| 3942 | `_filter_historical_cases_by_target` | `Module1HistoricalAnalysis` | Historical case filter. |
| 3989 | `_select_historical_cases` | `Module1HistoricalAnalysis` | R: `historical_cases`. |
| 4037 | `_historical_case_to_target_context` | `Module1HistoricalAnalysis` | Historical case to target-context conversion. |
| 4087 | `_review_flag_from_match_ratio` | `Module1HistoricalAnalysis` | Historical review helper. |
| 4104 | `_make_historical_case_key` | `Module1HistoricalAnalysis` | Historical review key helper. |
| 4131 | `_evaluate_historical_case` | `Module1HistoricalAnalysis` | Uses result/context outputs for one historical case. |
| 4381 | `_build_historical_case_summary_table` | `Module1HistoricalAnalysis` | Historical summary table. |
| 4424 | `_format_historical_case_summary_view` | `Module1HistoricalAnalysis` | Historical summary display table. |
| 4460 | `_build_historical_detail_table` | `Module1HistoricalAnalysis` | Historical detail table. |
| 4502 | `_build_historical_review_report` | `Module1HistoricalAnalysis` | Historical report table. |
| 4568 | `_build_historical_review_distributions` | `Module1HistoricalAnalysis` | Historical distribution tables. |
| 4623 | `_build_historical_review_windows` | `Module1HistoricalAnalysis` | Historical match-window table. |
| 4668 | `_build_historical_diagnostic_summary` | `Module1HistoricalAnalysis` | Historical diagnostic summary. |
| 4794 | `review_historical_cases` | `Module1HistoricalAnalysis` | Public historical review API. |
| 4876 | `run_module1_historical_review` | compatibility facade | Loads/runs pipeline then historical review; keep as wrapper. |
| 4924 | `_first_valid_dates_by_column` | `Module1Analysis` | Result-only helper. |
| 4931 | `_latest_valid_dates_by_column` | `Module1Analysis` | Result-only helper. |
| 4938 | `_label_distributions` | `Module1Analysis` | Result-only helper. |
| 4952 | `inspect_module1_results` | `Module1Analysis` | R: features/scores/labels/exposure stance; result-only. |
| 5033 | `_target_resolution_from_canonical` | `Module1Analysis` | R: config snapshots. |
| 5110 | `_target_resolution_for_raw_input` | `Module1Analysis` | Target resolution helper. |
| 5134 | `_target_resolution_for_feature` | `Module1Analysis` | R: `feature_config`. |
| 5162 | `_normalize_target_level` | `Module1Analysis` | Target resolution helper. |
| 5190 | `_resolve_target_for_context` | `Module1Analysis` | R: `data`, `feature_config`; result/context helper. |
| 5229 | `resolve_target` | `Module1Analysis` | Public target resolver. |
| 5375 | `_features_for_component_score` | `Module1Analysis` | R: `component_config`. |
| 5415 | `_raw_input_dependencies_for_feature` | `Module1Analysis` | R: `data`, `feature_config`. |
| 5481 | `_dependencies_for_resolution` | `Module1Analysis` | Dependency resolver. |
| 5620 | `_normalize_dependency_level` | `Module1Analysis` | Context helper. |
| 5692 | `_required_output_table` | `Module1Analysis` | Context helper. |
| 5713 | `_window_series_or_frame` | `Module1Analysis` | Result window helper. |
| 5724 | `_add_context_frame` | `Module1Analysis` | Result context helper. |
| 5759 | `_resolved_path_metadata` | `Module1Analysis` | Metadata helper. |
| 5776 | `get_target_context` | `Module1Analysis` / design question | Result-only except `context_id` path needs historical context. |
| 6083 | `_resolve_target_compare` | `Module1Analysis` | Result comparison helper. |
| 6130 | `_comparison_normalization_recommendation` | `Module1Analysis` | Result comparison metadata. |
| 6150 | `build_target_comparison_dataset` | `Module1Analysis` / design question | Result-only unless `context_id` requires historical window resolution. |
| 6272 | `raw_inputs_for_target` | `Module1Analysis` | Result/config context helper. |
| 6286 | `_resolve_historical_event_window` | `Module1HistoricalAnalysis` / design question | R: `historical_context`; should move out of result-only paths. |
| 6316 | `_diagnostic_input_column_name` | `Module1SensitivityDiagnostics` | Diagnostic alias helper. |
| 6326 | `_component_by_score_output` | `Module1SensitivityDiagnostics` | R: `component_config`; diagnostic lookup. |
| 6336 | `_diagnostic_component_filter_for_target` | `Module1SensitivityDiagnostics` | Diagnostic target helper. |
| 6343 | `_diagnostic_component_names_for_target` | `Module1SensitivityDiagnostics` | R: `exposure_stance_config`. |
| 6371 | `_score_input_features_for_diagnostic_component` | `Module1SensitivityDiagnostics` | Diagnostic input helper. |
| 6390 | `_score_input_features_for_diagnostic_components` | `Module1SensitivityDiagnostics` | R: `component_config`. |
| 6411 | `_diagnostic_input_specs` | `Module1SensitivityDiagnostics` | R: `component_config`. |
| 6484 | `_diagnostic_input_spec` | `Module1SensitivityDiagnostics` | Diagnostic input lookup. |
| 6510 | `_diagnostic_input_spec_by_role` | `Module1SensitivityDiagnostics` | Diagnostic input lookup. |
| 6534 | `_prepared_filtered_input_columns` | `Module1SensitivityDiagnostics` | R: `features`, `component_config`. |
| 6580 | `_stance_weight_terms` | `Module1Analysis` | R: `scores`; result trace helper. |
| 6637 | `_component_label_columns_for_scores` | `Module1Analysis` | R: `component_config`. |
| 6663 | `_trace_weighted_stance_score` | `Module1Analysis` | R: scores/labels/exposure stance/config; no mutation. |
| 6775 | `_resolve_rule_mapped_diagnostic_config` | `Module1Analysis` | Rule-mapped diagnostic config helper. |
| 6810 | `_derive_rule_mapped_diagnostic_spec_from_context` | `Module1Analysis` | Rule-mapped diagnostic spec helper. |
| 6863 | `_trace_rule_mapped_stance_score` | `Module1Analysis` | R: scores/labels/exposure stance/config; no mutation. |
| 6963 | `_ensure_rule_mapped_stabilization_change_flags` | `Module1Analysis` | Pure diagnostic-table helper. |
| 6998 | `_rule_mapped_trace_context_parts` | `Module1Analysis` | Result/context helper. |
| 7055 | `_duration_rule_stance_config` | `Module1Analysis` | R: `exposure_stance_config`. |
| 7066 | `_rule_mapped_selected_columns` | `Module1Analysis` | Pure column-selection helper. |
| 7106 | `diagnose_rule_mapped_stance` | `Module1Analysis` / design question | Result-only if dates are explicit; `context_id` requires historical boundary. |
| 7186 | `_diagnose_rule_mapped_stance_transitions` | `Module1Analysis` | Result-only table derivation. |
| 7228 | `_rule_mapped_component_state_summary` | `Module1Analysis` | Result-only table derivation. |
| 7285 | `_series_value_shares` | `Module1Analysis` | Pure summary helper. |
| 7294 | `_rule_mapped_score_distribution` | `Module1Analysis` | Result-only table derivation. |
| 7309 | `_summarize_rule_mapped_stance_stability` | `Module1Analysis` | Result-only table derivation. |
| 7391 | `_curve_positioning_stance_config` | `Module1Analysis` | R: `exposure_stance_config`. |
| 7403 | `_rule_mapped_trace_supported_functions` | `Module1Analysis` | Pure support list. |
| 7410 | `trace_stance_score` | `Module1Analysis` / design question | Result-only except `context_id` path. |
| 7455 | `_smoothing_diagnostic_windows` | `Module1SensitivityDiagnostics` | R: `historical_context` for default diagnostic windows. |
| 7478 | `_not_applicable_smoothing_result` | `Module1SensitivityDiagnostics` | Diagnostic result helper. |
| 7496 | `_normalize_smoothing_target` | `Module1SensitivityDiagnostics` | Diagnostic target helper. |
| 7503 | `_target_smoothing_layers` | `Module1SensitivityDiagnostics` | R: `module1_config`; diagnostic capability check. |
| 7522 | `_resolve_smoothing_layer` | `Module1SensitivityDiagnostics` | Diagnostic option resolver. |
| 7531 | `_smoothing_context_columns` | `Module1SensitivityDiagnostics` | R: component/feature config. |
| 7582 | `_smoothing_diagnostic_target_profile` | `Module1SensitivityDiagnostics` | Diagnostic profile builder. |
| 7620 | `_validate_input_smoothing_detail_prerequisites` | `Module1SensitivityDiagnostics` | R: features/scores/stance/config. |
| 7641 | `_add_smoothing_context_columns` | `Module1SensitivityDiagnostics` | R: data/features; diagnostic detail helper. |
| 7659 | `_rule_mapped_input_smoothing_effect_detail` | `Module1SensitivityDiagnostics` | CF: rebuilds raw-input path vs production path. |
| 7727 | `_smoothing_effect_result` | `Module1SensitivityDiagnostics` | Diagnostic result assembly. |
| 7752 | `compare_smoothing_effect` | `Module1SensitivityDiagnostics` | CF: smoothing/no-smoothing comparison. |
| 7843 | `_credit_stance_config` | `Module1SensitivityDiagnostics` | R: `exposure_stance_config`; diagnostic helper. |
| 7851 | `_credit_stance_score_from_component_scores` | `Module1SensitivityDiagnostics` | Counterfactual credit helper candidate. |
| 7882 | `_credit_stance_labels_for_score` | `Module1SensitivityDiagnostics` | Counterfactual credit helper candidate. |
| 7889 | `_ratio_or_na` | `Module1Analysis` | Pure summary helper. |
| 7892 | `_smoothing_pair_comparison_metrics` | `Module1SensitivityDiagnostics` | Smoothing comparison metric helper. |
| 7939 | `_smoothing_pair_comparison_metrics_for_columns` | `Module1SensitivityDiagnostics` | Smoothing comparison metric helper. |
| 7953 | `_add_prefixed_smoothing_pair_metrics` | `Module1SensitivityDiagnostics` | Smoothing summary helper. |
| 7962 | `_rule_mapped_input_smoothing_summary_row` | `Module1SensitivityDiagnostics` | Smoothing summary helper. |
| 8044 | `_inclusive_window_slice` | `Module1Analysis` | Pure window helper. |
| 8057 | `_window_summary_row` | `Module1Analysis` | Pure window-summary helper. |
| 8068 | `_series_mismatch_mask` | `Module1Analysis` | Pure comparison helper. |
| 8090 | `_curve_dominant_value` | `Module1Analysis` | Pure dominant-value helper. |
| 8096 | `_count_series_changes` | `Module1Analysis` | Pure transition-count helper. |
| 8102 | `_count_one_day_spikes` | `Module1Analysis` | Pure spike-count helper. |
| 8119 | `_default_curve_stabilization_cases` | `Module1SensitivityDiagnostics` | Diagnostic scenario defaults. |
| 8145 | `_neutral_curve_positioning_stabilization_overrides` | `Module1SensitivityDiagnostics` | Diagnostic override defaults. |
| 8155 | `_default_curve_stabilization_windows` | `Module1SensitivityDiagnostics` | Diagnostic event-window defaults. |
| 8163 | `_curve_move_driver_score_from_prepared_inputs` | `Module1SensitivityDiagnostics` | Threshold sensitivity helper. |
| 8181 | `compare_curve_move_driver_threshold_effect` | `Module1SensitivityDiagnostics` | CF: alternate threshold/filter comparison. |
| 8411 | `_rule_mapped_stabilization_case_detail_comparison` | `Module1SensitivityDiagnostics` | CF: baseline vs case stabilization detail. |
| 8536 | `_curve_stabilization_case_detail` | `Module1SensitivityDiagnostics` | Curve stabilization diagnostic detail. |
| 8599 | `_curve_stabilization_summary_row` | `Module1SensitivityDiagnostics` | Curve stabilization summary. |
| 8683 | `_curve_stabilization_window_row` | `Module1SensitivityDiagnostics` | Curve stabilization window summary. |
| 8724 | `compare_curve_positioning_stabilization_cases` | `Module1SensitivityDiagnostics` | CF: stabilization case comparison. |
| 8806 | `compare_credit_stance_persistence_cases` | `Module1SensitivityDiagnostics` | CF and temporary W: config/stance outputs. |
| 9234 | `_select_related_inputs` | `Module1HistoricalAnalysis` | Historical plot input selection. |
| 9273 | `_mark_label_changes` | `Module1HistoricalAnalysis` | Historical plot annotation helper. |
| 9300 | `_add_score_zones` | `Module1HistoricalAnalysis` | Historical plot score-zone helper. |
| 9374 | `_plot_historical_review_state_timeline` | `Module1HistoricalAnalysis` | Historical plot timeline helper. |
| 9436 | `_decompose_match_windows` | `Module1HistoricalAnalysis` | Historical match-window helper. |
| 9463 | `plot_historical_review_case` | `Module1HistoricalAnalysis` | Historical event plotting. |
| 9684 | `_resolve_historical_display_window` | `Module1HistoricalAnalysis` | Historical plot window helper. |
| 9754 | `_mark_context_window_and_update_legend` | `Module1HistoricalAnalysis` | Historical plot annotation helper. |
| 9789 | `_normalize_for_comparison_plot` | `Module1Analysis` | Result-only plot helper. |
| 9802 | `_resolve_compare_plot_normalize` | `Module1Analysis` | Result-only plot helper. |
| 9814 | `_render_compare_dataset_on_axes` | `Module1Analysis` | Result-only plot renderer. |
| 9907 | `_plot_target_inputs_on_axes` | `Module1Analysis` | R: labels/exposure stance; result-only plot helper. |
| 10006 | `plot_target_comparison` | `Module1Analysis` / design question | Result-only unless `context_id` needs historical window resolution. |

## Ownership Classification Summary

### `Module1Calculator`

Owns initialization, core file loading, horizon validation/mutation, data
loading, feature calculation, component score/label calculation, stance
calculation, and the reusable side-effect-free scoring mechanics. This includes
the rule-mapped stance schema/score-breakdown helpers because they implement the
core stance engine used by both production calculations and diagnostics.

### `Module1Result`

No current `RegimeModule` method maps directly to this owner because it does not
exist yet. The first split PR should add this snapshot concept without moving
methods.

### `Module1Analysis`

Result-only candidates include `inspect_module1_results(...)`, target
resolution/context helpers, raw-input dependency helpers, rule-mapped tracing and
state/stability summary helpers, simple series/window helpers, and target
comparison plotting when no historical `context_id` lookup is requested.

### `Module1HistoricalAnalysis`

Historical-context owners include `load_historical_context(...)`,
`validate_historical_expected_labels(...)`, all historical case selection,
review, report/distribution/window builders, `review_historical_cases(...)`, and
historical review plotting helpers.

### `Module1SensitivityDiagnostics`

Sensitivity owners include horizon-case comparison, input-preparation smoothing
diagnostics, curve move-driver threshold sensitivity, curve stabilization cases,
credit persistence cases, and their private helpers.

### Compatibility Facade

`run_module1_historical_review(...)` is already documented as a convenience
wrapper and should remain a facade until callers migrate.

### Unclear / Needs Design Decision

`_resolve_historical_event_window(...)`, `get_target_context(...)`,
`build_target_comparison_dataset(...)`, `diagnose_rule_mapped_stance(...)`,
`trace_stance_score(...)`, and `plot_target_comparison(...)` are result-only for
explicit dates but become historical-context-dependent when `context_id` is
used. The split should separate pure date-window behavior from historical
context-id resolution.

## Result-Only Test

Methods proposed for pure `Module1Analysis` can run from `Module1Result` alone
if `Module1Result` includes data, features, scores, labels, stance scores,
exposure stance, config snapshots, and horizons. These include:

- `inspect_module1_results(...)`
- target resolution helpers and `get_target_context(...)` without `context_id`
- `raw_inputs_for_target(...)`
- `build_target_comparison_dataset(...)` without `context_id`
- rule-mapped trace/stability helpers when called with explicit `start`/`end`
  or no window
- pure metric helpers such as `_ratio_or_na(...)`,
  `_inclusive_window_slice(...)`, `_series_mismatch_mask(...)`,
  `_count_series_changes(...)`, and `_count_one_day_spikes(...)`
- target comparison plotting without historical context-id lookup

Do not classify methods as pure `Module1Analysis` if they require
`self.historical_context`, `self.historical_cases`, or counterfactual
calculation.

## Historical-Context Test

Methods that depend on historical context/cases or expected-label metadata:

- `load_historical_context(...)`
- `_valid_historical_label_vocabularies(...)`
- `_validate_historical_expected_labels_from_cases(...)`
- `validate_historical_expected_labels(...)`
- `_build_historical_cases(...)`
- `_select_historical_cases(...)`
- `_evaluate_historical_case(...)`
- all `_build_historical_*` review/report/window/distribution helpers
- `review_historical_cases(...)`
- `plot_historical_review_case(...)`
- `_decompose_match_windows(...)`
- `_resolve_historical_display_window(...)`
- `_mark_context_window_and_update_legend(...)`
- `_resolve_historical_event_window(...)`

These should move to `Module1HistoricalAnalysis`, except
`_resolve_historical_event_window(...)` should probably become a small
historical-boundary service consumed by analysis and sensitivity diagnostics.

## Sensitivity / Counterfactual Test

These methods reconstruct, recalculate, use alternate config, compare smoothing,
compare thresholds, compare horizons, or compare persistence/stabilization
cases:

- `compare_horizon_cases(...)`: alternate horizons, temporary modules, full
  pipeline recalculation.
- `compare_smoothing_effect(...)`: raw/no-smoothing path reconstruction and
  comparison.
- `compare_curve_move_driver_threshold_effect(...)`: alternate curve move-driver
  threshold/filter path.
- `compare_curve_positioning_stabilization_cases(...)`: alternate
  stabilization cases.
- `compare_credit_stance_persistence_cases(...)`: temporary config mutation and
  exposure-stance recalculation.
- Private helpers from `_calculate_component_score_for_input_preparation_diagnostic(...)`
  through `_rule_mapped_component_parameter_effect_detail(...)`.
- Private smoothing helpers from `_smoothing_diagnostic_windows(...)` through
  `_rule_mapped_input_smoothing_summary_row(...)`.
- Private curve stabilization helpers from `_default_curve_stabilization_cases(...)`
  through `_curve_stabilization_window_row(...)`.

These should not move to pure `Module1Analysis`.

## Mutation and Side-Effect Audit

| State | Methods | Mutation Type | Split Guidance |
|---|---|---|---|
| `module1_config` | `__init__`, `load_module1_config` | cache/state setup | Calculator. |
| `feature_config` | `__init__`, `load_module1_config` | cache/state setup | Calculator. |
| `component_config` | `__init__`, `load_module1_config` | cache/state setup | Calculator. |
| `exposure_stance_config` | `__init__`, `load_module1_config`, `compare_credit_stance_persistence_cases` | setup; temporary diagnostic mutation | Calculator owns setup; credit persistence mutation is future cleanup target. |
| `data` | `__init__`, `load_data` | core pipeline mutation | Calculator. |
| `features` | `__init__`, `calculate_features` | core pipeline mutation | Calculator. |
| `scores` | `__init__`, `align_component_scores`, `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic`, `calculate_component_scores` | core mutation; temporary diagnostic mutation | Calculator for core; diagnostic temporary write is cleanup target. |
| `labels` | `__init__`, `calculate_component_labels` | core pipeline mutation | Calculator. |
| `stance_scores` | `__init__`, `calculate_exposure_stance`, `compare_credit_stance_persistence_cases` | core mutation; temporary diagnostic restore | Calculator for core; credit persistence mutation is cleanup target. |
| `exposure_stance` | `__init__`, `calculate_exposure_stance`, `compare_credit_stance_persistence_cases` | core mutation; temporary diagnostic restore | Calculator for core; credit persistence mutation is cleanup target. |
| `historical_context` | `__init__`, `load_historical_context` | historical state setup | Historical analysis input, not result. |
| `historical_cases` | `__init__`, `load_historical_context` | historical state setup | Historical analysis input, not result. |
| `horizons` | `__init__`, `update_horizons`, `load_module1_config`, `compare_horizon_cases` temporary module | core setup and sensitivity case override | Calculator owns runtime horizons; horizon cases remain sensitivity diagnostics. |

Temporary diagnostic mutations to clean up later:

- `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(...)`
  temporarily replaces `self.scores`.
- `compare_credit_stance_persistence_cases(...)` temporarily replaces
  `self.exposure_stance_config`, `self.stance_scores`, and
  `self.exposure_stance`.

## Proposed `Module1Result` Fields

Minimum recommended fields:

- `data`
- `features`
- `scores`
- `labels`
- `stance_scores`
- `exposure_stance`
- `module1_config`
- `feature_config`
- `component_config`
- `exposure_stance_config`
- `horizons`
- `default_horizons`
- `horizon_overrides`
- `module1_config_validation`
- `historical_expected_label_validation` only if produced separately and
  explicitly attached

Historical context should **not** be part of the minimum `Module1Result`.
Pass `historical_context` and derived `historical_cases` separately to
`Module1HistoricalAnalysis`. This keeps ordinary result analysis pure and avoids
coupling a model output snapshot to review metadata.

## `module1_schema.py` Boundary

No schema changes are needed for the first class split if YAML/config structure
and validation contracts remain unchanged.

Only revisit `module1_schema.py` if a later split introduces new YAML sections,
renames config fields, changes output declarations, or adds diagnostic metadata
to YAML. This audit does not recommend any of those changes for the first split.

## Recommended Implementation Sequence

1. Introduce `Module1Result` snapshot construction from the current
   `RegimeModule` after `calculate_exposure_stance()` with no behavior changes.
2. Add `Module1Analysis` methods that consume `Module1Result` for
   `inspect_module1_results(...)`, simple result summaries, and pure target
   context helpers without historical `context_id`.
3. Separate historical context loading/case building/review into
   `Module1HistoricalAnalysis`, consuming `Module1Result` plus explicit
   historical context/cases.
4. Add `Module1SensitivityDiagnostics` around side-effect-free helpers where
   already available; defer live-mutating diagnostics.
5. Refactor legacy/ad hoc sensitivity diagnostics:
   `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(...)` and
   `compare_credit_stance_persistence_cases(...)` should stop mutating live
   module state before they are moved.
6. Keep `RegimeModule` as a compatibility facade until public callers migrate.

## High-Risk Methods to Defer

- `compare_horizon_cases(...)`: creates temporary modules and reruns full
  pipeline.
- `compare_smoothing_effect(...)`: complex public return shape and alternate
  path reconstruction.
- `compare_curve_move_driver_threshold_effect(...)`: specialized threshold
  sensitivity output contract.
- `compare_curve_positioning_stabilization_cases(...)`: public nested detail
  tables and stabilization case outputs.
- `compare_credit_stance_persistence_cases(...)`: live temporary mutation and
  credit event-window output contract.
- `review_historical_cases(...)`: many public output modes.
- `plot_historical_review_case(...)`: historical context and plotting behavior.
- `plot_target_comparison(...)`: result-only in normal mode, but optional
  historical `context_id` makes ownership mixed.
- `get_target_context(...)` and `build_target_comparison_dataset(...)`: useful
  result-only core, but historical-window option should be separated first.

## Open Design Questions

- Should `get_target_context(...)` accept only explicit `start`/`end` in
  `Module1Analysis`, leaving `context_id` resolution to
  `Module1HistoricalAnalysis`?
- Should rule-mapped trace helpers live in `Module1Analysis`, or should
  `Module1Calculator` expose a read-only trace engine that analysis consumes?
- Should `Module1SensitivityDiagnostics` depend on `Module1Calculator` services
  or a smaller side-effect-free stance engine extracted from calculator helpers?
- Should `RegimeModule` remain as the long-term facade, or only as a temporary
  compatibility layer?
- How much historical plotting belongs in `Module1HistoricalAnalysis` versus a
  separate plotting/presentation layer?

## Behavior Impact

Audit-only. No production code, YAML, schema, public APIs, or model outputs were
changed.
