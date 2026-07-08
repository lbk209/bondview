# Module 1 Runtime Role Closure Audit

## Conclusion

Runtime role removed except for documented compatibility delegates.

`Module1Calculator` is the sole owner of Module 1 runtime implementation. The
remaining runtime-looking methods on `RegimeModule` are temporary delegates to
`self.calculator`, retained either for public compatibility or because existing
non-runtime workflows still call those method names.

Category D is empty: no duplicated runtime implementation remains in
`RegimeModule`.

## Method Categories

| Method | Category | Implementation Status | Current Callers | Future Owner Or Removal Condition |
| --- | --- | --- | --- | --- |
| `calculate_features` | A | Delegate only | Public compatibility API | Remove when public runtime callers migrate to `Module1Calculator`. |
| `align_component_scores` | A | Delegate only | Public compatibility API | Remove when public runtime callers migrate to `Module1Calculator`. |
| `calculate_component_scores` | A | Delegate only | Public compatibility API | Remove when public runtime callers migrate to `Module1Calculator`. |
| `calculate_component_labels` | A | Delegate only | Public compatibility API | Remove when public runtime callers migrate to `Module1Calculator`. |
| `calculate_exposure_stance` | A | Delegate only | Public compatibility API; `compare_credit_stance_persistence_cases` | Remove public wrapper after runtime callers migrate; diagnostic caller should migrate with sensitivity diagnostics. |
| `run_module1_pipeline` | A | Delegate only | Public compatibility API; `run_module1_historical_review` | Remove public wrapper after runtime callers migrate; historical caller should run `Module1Calculator` directly after historical review migration. |
| `to_module1_result` | A | Delegate only | Public compatibility API | Remove when public result production callers migrate to `Module1Calculator`. |
| `_prepare_component_input_series` | B | Delegate only | `_prepared_filtered_input_columns` | Sensitivity diagnostics / smoothing diagnostics. |
| `_clip_score` | B | Delegate only | `_calculate_component_score_for_input_preparation_diagnostic`; `compare_curve_move_driver_threshold_effect` | Sensitivity diagnostics. |
| `_calculate_single_feature_component_score` | B | Delegate only | `_calculate_component_score_for_input_preparation_diagnostic` | Sensitivity diagnostics. |
| `_calculate_weighted_feature_component_score` | B | Delegate only | `_calculate_component_score_for_input_preparation_diagnostic` | Sensitivity diagnostics. |
| `_calculate_curve_move_driver_score` | B | Delegate only | `_calculate_component_score_for_input_preparation_diagnostic` | Sensitivity diagnostics. |
| `_curve_move_driver_bucket_scores` | B | Delegate only | `compare_curve_move_driver_threshold_effect` | Sensitivity diagnostics. |
| `_component_score_bucket_config` | B | Delegate only | `compare_curve_move_driver_threshold_effect` | Sensitivity diagnostics. |
| `_resolve_rule_mapped_stance_schema` | B | Delegate only | `_resolve_rule_mapped_diagnostic_config`; `_rule_mapped_stabilization_case_detail_comparison` | Tracing and sensitivity diagnostics. |
| `_score_bucket` | B | Delegate only | `compare_curve_move_driver_threshold_effect` | Sensitivity diagnostics. |
| `_calculate_current_state_component_score` | B | Delegate only | `_calculate_component_score_for_input_preparation_diagnostic` | Sensitivity diagnostics. |
| `_label_stance_direction` | B | Delegate only | `_stance_labels_for_score` | Tracing / diagnostic label reconstruction. |
| `_label_stance_strength` | B | Delegate only | `_stance_labels_for_score` | Tracing / diagnostic label reconstruction. |
| `_build_weighted_stance_score_breakdown` | B | Delegate only | `_trace_weighted_stance_score` | Tracing. |
| `_build_rule_mapped_stance_score_breakdown` | B | Delegate only | `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic`; `_rule_mapped_stabilization_case_detail_comparison`; `_trace_rule_mapped_stance_score` | Tracing and sensitivity diagnostics. |
| `_credit_spread_state_intensity` | B | Delegate only | `_credit_spread_rule_row_from_states` | Credit diagnostics / sensitivity diagnostics. |
| `_stabilize_state_series` | B | Delegate only | `_stabilize_credit_rule_states` | Credit diagnostics / sensitivity diagnostics. |
| `_threshold_hysteresis_candidate` | B | Delegate only | `_stabilize_credit_rule_states` | Credit diagnostics / sensitivity diagnostics. |
| `_adjust_credit_spread_rule_score` | B | Delegate only | `_credit_spread_rule_row_from_states` | Credit diagnostics / sensitivity diagnostics. |
| `_curve_move_driver_score_from_prepared_inputs` | B | Delegate only | `compare_curve_move_driver_threshold_effect` | Sensitivity diagnostics. |
| Historical review methods, including `load_historical_context`, `review_historical_cases`, `run_module1_historical_review`, and related private helpers | C | Non-runtime implementation remains in `RegimeModule` | Historical review workflows | Future historical review owner. |
| Plotting methods, including `plot_historical_review_case`, `plot_target_comparison`, and plotting helpers | C | Non-runtime implementation remains in `RegimeModule` | Plotting workflows | Future plotting/reporting owner. |
| Tracing and diagnostics methods, including `trace_stance_score`, `diagnose_rule_mapped_stance`, and related private helpers | C | Non-runtime implementation remains in `RegimeModule` | Tracing and diagnostics workflows | Future diagnostics/tracing owner. |
| Sensitivity diagnostics, including smoothing, curve threshold/stabilization, and credit persistence comparisons | C | Non-runtime implementation remains in `RegimeModule` | Sensitivity diagnostic workflows | Future sensitivity diagnostics owner. |
| Target-context compatibility methods and helpers | C | Non-runtime implementation remains in `RegimeModule` | Target-context compatibility workflows | Future result-only/context compatibility owner. |
| None | D | No duplicated runtime implementation found | Not applicable | Not applicable. |

## Closure Notes

- Public runtime delegates remain only for compatibility.
- Private runtime-shaped delegates remain only because non-runtime methods still
  call those method names.
- No feature formulas, scoring formulas, labels, stance logic, smoothing,
  stabilization, thresholds, YAML semantics, or config interpretation changed.
- This audit did not migrate historical review, plotting, tracing, sensitivity
  diagnostics, or target-context workflows.
