# Module 1 Stage 2 Diagnostic Duplication Audit

Date: 2026-07-03

## Short conclusion

Stage 2 audited the eight diagnostic candidates identified by Stage 1B. No deletion decision is made in Stage 2.

Strongest cleanup candidate:

- `diagnose_historical_review_case()` is fully covered by `review_historical_cases(output="diagnostic")`. It is a thin public wrapper and can move toward a later focused deletion/deprecation decision after a private-helper/caller check.

Candidates that should generally be kept as specialized public wrappers or genericized behind existing APIs:

- `compare_credit_input_smoothing_effect()`
- `compare_curve_input_smoothing_effect()`
- `compare_curve_move_driver_threshold_effect()`
- `compare_curve_positioning_stabilization_cases()`
- `compare_credit_stance_persistence_cases()`

These are not fully replaced by current generic diagnostics. They run alternate scenarios, compare raw/prepared or baseline/case behavior, and expose documented public result keys, table names, columns, windows, cases, and target-specific vocabulary.

Candidates needing runtime contract checks or private helper audit:

- `diagnose_historical_review_case()` needs a small wrapper deletion/private-helper audit if removal is considered.
- `diagnose_rule_mapped_stance_transitions()` and `summarize_rule_mapped_stance_stability()` are mostly derivable from `diagnose_rule_mapped_stance()`, but provide convenience output shapes and public vocabulary; deletion should wait for runtime contract checks and compatibility decision.
- All `compare_*` diagnostics should get Stage 3 helper-family audits before any genericization because candidate-only and shared helpers are interleaved.

## Candidate-by-candidate audit

### `diagnose_historical_review_case()`

#### Purpose

Answers: "Return historical review diagnostics for the selected target/context/case filters." It is wrapper-like and generic historical-review oriented, not target-specific.

#### Public output contract

Return type: `pd.DataFrame`.

Important arguments/defaults:

- `target=None`
- `context_id=None`
- `level=None`
- `only_use_for_validation=True`
- `include_low_relevance=False`
- `min_obs=20`
- `plausible_threshold=0.70`
- `mixed_threshold=0.45`

Output is exactly the `review_historical_cases(..., output="diagnostic")` DataFrame. Public vocabulary comes from the canonical historical review diagnostic columns built by `_build_historical_diagnostic_summary()`, not from this wrapper.

#### Implementation dependency map

Candidate-only helpers: none.

Shared broader path:

- `review_historical_cases()`
- `_build_historical_case_summary_table()`
- `_build_historical_detail_table()`
- `_build_historical_review_windows()`
- `_build_historical_diagnostic_summary()`

Production scoring helpers: none directly; it consumes already calculated outputs through the historical review pipeline.

#### Generic/broader replacement path

Call:

```python
review_historical_cases(
    target=target,
    context_id=context_id,
    level=level,
    only_use_for_validation=only_use_for_validation,
    include_low_relevance=include_low_relevance,
    min_obs=min_obs,
    plausible_threshold=plausible_threshold,
    mixed_threshold=mixed_threshold,
    output="diagnostic",
)
```

No post-processing required. Output is the same canonical diagnostic path.

#### Duplication assessment

`fully_covered`.

#### Compatibility risk

`low` to `medium`. Stage 1B found no active docs/examples/tests/notebook usage and only report references, but the method is public-looking and may have external ad hoc callers.

#### Recommendation

`delete_candidate`, subject to later focused deletion PR and private-helper/caller audit. If compatibility caution is preferred, deprecate first.

### `diagnose_rule_mapped_stance_transitions()`

#### Purpose

Answers: "How did a rule-mapped stance's raw/stabilized states, rule case, score, stance label, and strength change over time?" It is generic for schema-backed rule-mapped stances (`duration`, `credit`, `curve_positioning`) but transition-oriented.

#### Public output contract

Return type: `pd.DataFrame`.

Important arguments/defaults:

- `target`
- `context_id=None`
- `start=None`
- `end=None`

Columns are derived from the rule-mapped diagnostic spec:

- `date`
- each raw state column
- each stabilized state column
- rule case column
- `previous_<rule_case_col>`
- `<rule_case_col>_changed`
- final score column
- `previous_<final_score_col>`
- `<final_score_col>_change`
- stance label column
- strength label column
- optional any-state stabilization flag

Prior reports describe it as transition-focused rule-mapped coverage for duration, credit, and curve.

#### Implementation dependency map

Candidate-only logic:

- transition DataFrame assembly
- previous rule case and score columns
- changed flags and first-valid changed flag correction

Shared generic diagnostics:

- `_resolve_rule_mapped_diagnostic_config()`
- `_derive_rule_mapped_diagnostic_spec_from_context()`
- `diagnose_rule_mapped_stance()`
- `_rule_mapped_selected_columns()`
- `_ensure_rule_mapped_stabilization_change_flags()`

Production scoring/shared rule-mapped path:

- indirectly uses `_build_rule_mapped_stance_score_breakdown()` through `diagnose_rule_mapped_stance()`.

#### Generic/broader replacement path

Call:

```python
diagnose_rule_mapped_stance(
    target,
    context_id=context_id,
    start=start,
    end=end,
    include_scores=False,
    include_raw_states=True,
    include_stabilized_states=True,
    include_rule_case=True,
    include_labels=True,
)
```

Then manually derive:

- `date = index`
- previous rule case via `.shift(1)`
- rule-case changed flag
- previous final score via `.shift(1)`
- score change
- first-valid changed flag override

#### Duplication assessment

`mostly_covered`. The generic diagnostic contains the underlying data, but callers would lose a ready transition table and would need manual derivation.

#### Compatibility risk

`medium`. Prior reports cite it as replacement guidance and transition-focused coverage, but Stage 1B found no active docs/examples/tests/notebooks.

#### Recommendation

`needs_runtime_contract_check` before any deletion/deprecation. If kept, it can remain a thin convenience wrapper over `diagnose_rule_mapped_stance()`.

### `summarize_rule_mapped_stance_stability()`

#### Purpose

Answers: "What is the stability and distribution summary for a rule-mapped stance?" It is generic for schema-backed rule-mapped stances and summary-oriented.

#### Public output contract

Return type: `dict`.

Important arguments/defaults:

- `target`
- `context_id=None`
- `start=None`
- `end=None`

Result keys:

- `component_state_summary`
- `rule_case_summary`
- `mapped_score_distribution`
- `score_summary`

Public vocabulary/columns include:

- `component_state_summary`: `component`, transition counts, stabilization changed count/ratio, most frequent raw/stabilized states, valid counts.
- `rule_case_summary`: transition count named for the rule-case column, unique count, most frequent case/ratio, valid case count.
- `mapped_score_distribution`: final score value, `count`, `share`.
- `score_summary`: score mean/median/min/max/std, valid score/stance/strength counts, stance and strength share fields.
- For duration only, explicit `positive_stance_share`, `neutral_stance_share`, `negative_stance_share`.

Prior reports identify a public vocabulary dependency for `summarize_rule_mapped_stance_stability("curve_positioning")["component_state_summary"]["component"]`, specifically `yield_move_driver`.

#### Implementation dependency map

Candidate-specific helpers:

- `_rule_mapped_component_state_summary()`
- `_rule_mapped_score_distribution()`
- `_series_value_shares()` in this summary context

Shared generic diagnostics:

- `_resolve_rule_mapped_diagnostic_config()`
- `_derive_rule_mapped_diagnostic_spec_from_context()`
- `diagnose_rule_mapped_stance()`
- `_count_series_changes()`

Production/shared rule-mapped path:

- indirectly uses `_build_rule_mapped_stance_score_breakdown()` through `diagnose_rule_mapped_stance()`.

#### Generic/broader replacement path

Call:

```python
diagnose_rule_mapped_stance(
    target,
    context_id=context_id,
    start=start,
    end=end,
    include_scores=False,
    include_raw_states=True,
    include_stabilized_states=True,
    include_rule_case=True,
    include_labels=True,
)
```

Then manually compute:

- per-component raw/stabilized transition counts and mode values
- stabilization changed counts/ratios
- rule-case transition counts, most frequent case, unique count
- final-score distribution
- score descriptive stats
- stance/strength share fields
- duration-specific positive/neutral/negative shares

#### Duplication assessment

`mostly_covered`. The row-level data is covered, but the public summary tables, key names, duration-specific shares, and curve component display vocabulary are not automatically produced by the generic row diagnostic.

#### Compatibility risk

`medium`. Prior reports document useful public output and public vocabulary impact, but no active docs/examples/tests/notebook usage was found.

#### Recommendation

`keep_active` unless a later compatibility decision explicitly removes summary convenience APIs. If internals are refactored, preserve the public result keys/tables or deprecate first.

### `compare_credit_input_smoothing_effect()`

#### Purpose

Answers: "How does production credit logic using prepared inputs differ from a raw-input reconstruction?" It is target-specific to credit input preparation and credit stance reconstruction.

#### Public output contract

Return type: `dict`.

Arguments/defaults:

- `windows: dict | None = None`
- `include_detail: bool = True`

Default windows:

- `global_financial_crisis`
- `covid_shock`
- `fed_hiking_2022`
- `full_history`

Result keys:

- `summary`
- `window_summary`
- `detail` when `include_detail=True`

Prior contract reports document the summary/window/detail columns. Important public vocabulary includes:

- raw/smoothed credit spread component score columns
- raw/smoothed credit stance score, direction, and strength columns
- `credit_stance_score_diff`
- credit-specific changed count and one-day-spike reduction columns

#### Implementation dependency map

Candidate-specific helpers:

- `_default_credit_input_smoothing_windows()`
- `_raw_credit_component_scores_for_input_smoothing_comparison()`
- `_credit_input_smoothing_effect_detail()`
- `_credit_input_smoothing_summary_row()`

Shared diagnostic helpers:

- `_recalculate_component_scores_for_input_preparation_diagnostic()`
- `_calculate_component_score_for_input_preparation_diagnostic()`
- `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic()`
- `_prepared_filtered_input_columns()`
- `_inclusive_window_slice()`
- `_window_summary_row()`
- `_mean_abs_diff_for_valid_pairs()`
- `_changed_count_for_valid_pairs()`
- `_count_series_changes()`
- `_count_one_day_spikes()`
- `_ratio_or_na()`

Production/shared scoring helpers:

- component calculation helpers
- rule-mapped stance breakdown
- credit adjustment helpers through rule-mapped credit reconstruction

#### Generic/broader replacement path

No existing public generic API reproduces this end to end.

Partial replacement would require:

1. Recalculate credit component scores with `apply_input_preparation=False`.
2. Reconstruct credit stance from those raw component scores.
3. Pull production smoothed component and stance outputs.
4. Build raw/smoothed detail columns.
5. Compute changed counts, mean absolute differences, score-change reductions, one-day spike reductions.
6. Slice default/custom windows and repeat the summary.

Current broader APIs like `trace_stance_score("credit")` explain production scoring, but they do not recalculate raw-input component scores or assemble raw-vs-smoothed comparison tables.

#### Duplication assessment

`partially_covered`. Generic/internal pieces exist, but the main diagnostic purpose and public result shape are not covered by a current generic public API.

#### Compatibility risk

`high`. Prior reports document public result keys, columns, windows, and preservation requirements.

#### Recommendation

`genericize_behind_existing_api`. Keep the public method and migrate internals only after a generic input-preparation comparison core and equality checks exist.

### `compare_curve_input_smoothing_effect()`

#### Purpose

Answers: "How does production curve-positioning logic using prepared inputs differ from a raw-input reconstruction?" It is target-specific to curve positioning input preparation and stance reconstruction.

#### Public output contract

Return type: `dict`.

Arguments/defaults:

- `windows: dict | None = None`
- `include_detail: bool = True`

Default windows:

- `taper_tantrum_review`
- `fed_hiking_2022`
- `full_history`

Result keys:

- `summary`
- `window_summary`
- `detail` when `include_detail=True`

Public vocabulary includes:

- raw/smoothed curve component score columns
- raw/smoothed curve positioning score, direction, and strength columns
- `score_diff`
- prepared/filtered curve input columns
- curve-specific changed count and one-day-spike reduction columns

#### Implementation dependency map

Candidate-specific helpers:

- `_default_curve_input_smoothing_windows()`
- `_raw_curve_component_scores_for_input_smoothing_comparison()`
- `_curve_input_smoothing_effect_detail()`
- `_curve_input_smoothing_summary_row()`

Shared diagnostic helpers:

- `_recalculate_component_scores_for_input_preparation_diagnostic()`
- `_calculate_component_score_for_input_preparation_diagnostic()`
- `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic()`
- `_prepared_filtered_input_columns()`
- `_diagnostic_component_names_for_target()`
- `_score_input_features_for_diagnostic_components()`
- `_inclusive_window_slice()`
- `_window_summary_row()`
- `_mean_abs_diff_for_valid_pairs()`
- `_changed_count_for_aligned_pairs()`
- `_count_series_changes()`
- `_count_one_day_spikes()`
- `_ratio_or_na()`

Production/shared scoring helpers:

- component calculation helpers
- rule-mapped stance breakdown

#### Generic/broader replacement path

No existing public generic API reproduces this end to end.

Partial replacement requires the same sequence as credit smoothing, but with curve components and curve-positioning stance reconstruction. `trace_stance_score("curve_positioning")` covers production explanation but not raw-input recalculation and raw-vs-smoothed summary/window/detail assembly.

#### Duplication assessment

`partially_covered`.

#### Compatibility risk

`high`. Prior reports document result keys, columns, default windows, and preservation requirements.

#### Recommendation

`genericize_behind_existing_api`. Keep the public method and migrate internals only with equality checks.

### `compare_curve_move_driver_threshold_effect()`

#### Purpose

Answers: "What is the effect of the curve move-driver `min_abs_value` filter on curve move-driver classification and downstream curve-positioning score?" It is target-specific and parameter-effect oriented.

#### Public output contract

Return type: `dict`.

Arguments/defaults:

- `include_detail: bool = True`

Result keys:

- `summary`
- `detail` when `include_detail=True`

Public summary vocabulary includes:

- `min_abs_value`
- below-threshold row counts
- `curve_move_driver_score_changed_count_vs_no_threshold`
- `mixed_or_unclear_count_before_threshold`
- `mixed_or_unclear_count_after_threshold`
- `curve_positioning_score_changed_count_due_to_threshold`

Detail vocabulary includes:

- prepared/filtered front-end and long-end inputs
- curve move-driver score and bucket with/without threshold
- curve positioning score with/without threshold
- diff and changed flags

#### Implementation dependency map

Candidate-specific logic:

- extracting `min_abs_value`
- constructing prepared vs filtered input scenarios
- bucket labels with/without threshold
- below-threshold and mixed/unclear summary metrics

Shared diagnostic helpers:

- `_prepared_filtered_input_columns()`
- `_diagnostic_input_spec_by_role()`
- `_diagnostic_input_column_name()`
- `_curve_move_driver_score_from_prepared_inputs()`
- `_rule_mapped_component_parameter_effect_detail()`
- `_ratio_or_na()`

Shared production helpers:

- `_curve_move_driver_bucket_scores()`
- `_component_score_bucket_config()`
- `_clip_score()`
- `_score_bucket()`
- rule-mapped stance reconstruction through `_rule_mapped_component_parameter_effect_detail()`

#### Generic/broader replacement path

No current public generic parameter-effect API exists.

Partial replacement path:

1. Build baseline component score from prepared inputs without threshold.
2. Build alternate component score from filtered inputs with threshold.
3. Use `_rule_mapped_component_parameter_effect_detail()` or an equivalent private parameter-effect core to compare downstream stance scores.
4. Manually add threshold-specific input columns, bucket labels, below-threshold counts, mixed/unclear counts, and public result keys.

#### Duplication assessment

`partially_covered`. There is a private generic-ish parameter-effect helper, but no public generic API and the public threshold vocabulary is target-specific.

#### Compatibility risk

`high`. Prior reports document public result keys and explicitly recommend preserving specialized output vocabulary.

#### Recommendation

`keep_as_specialized_wrapper`. A future generic parameter-effect core may sit underneath it, but the public wrapper should remain unless explicitly deprecated.

### `compare_curve_positioning_stabilization_cases()`

#### Purpose

Answers: "How do curve-positioning scores, labels, rule cases, buckets, and stability metrics change under alternate rule-mapped stabilization settings?" It is target-specific to curve positioning and stabilization-case comparison.

#### Public output contract

Return type: `dict`.

Arguments/defaults:

- `cases: dict | None = None`
- `windows: dict | None = None`
- `include_diagnostics: bool = True`

Result keys:

- `summary`
- `window_summary`
- `detail_by_case`
- `bucket_transition_summary`
- `score_distribution`
- `diagnostics_by_case` when `include_diagnostics=True`

Prior reports document public signature, result keys, default cases/windows, and table contracts. Public vocabulary includes raw/stabilized curve bucket names, `yield_move_driver`, raw/stabilized curve positioning scores/labels/strengths, score-change flags, one-day-spike flags, bucket transition summary, and score distribution.

#### Implementation dependency map

Candidate-specific helpers:

- `_default_curve_stabilization_cases()`
- `_neutral_curve_positioning_stabilization_overrides()`
- `_default_curve_stabilization_windows()`
- `_curve_stabilization_case_detail()`
- `_curve_stabilization_summary_row()`
- `_curve_stabilization_window_row()`
- bucket transition and score distribution assembly loops inside the public method

Shared generic/private helpers:

- `_rule_mapped_stabilization_case_detail_comparison()`
- `_inclusive_window_slice()`
- `_series_mismatch_mask()`
- `_count_series_changes()`
- `_count_one_day_spikes()`
- `_curve_dominant_value()`
- `_ratio_or_na()`

Production/shared rule-mapped helpers:

- `_resolve_rule_mapped_stance_schema()`
- `_build_rule_mapped_stance_score_breakdown()`
- `_stance_labels_for_score()`

#### Generic/broader replacement path

No current public generic stabilization-case comparison API exists.

Partial replacement path:

1. Use `_build_rule_mapped_stance_score_breakdown()` with baseline and case stabilization overrides.
2. Align score inputs, raw/stabilized state columns, rule cases, scores, labels, and strengths.
3. Compute changed flags, score-change flags, spike flags.
4. Assemble per-case detail, summary, window summary, bucket transition summary, score distribution, and optional diagnostics alias.

Prior Group G report says a private generic rule-mapped stabilization-case comparison core is feasible, but the public wrapper should preserve exact current output contract.

#### Duplication assessment

`partially_covered`. Generic rule-mapped primitives cover reconstruction, but not the full public comparison workflow and table contract.

#### Compatibility risk

`high`. Prior reports explicitly require preserving method signature, result keys, case ids, columns, ordering, semantics, and default windows.

#### Recommendation

`genericize_behind_existing_api`. Keep the public method; build a private generic core only with equality checks.

### `compare_credit_stance_persistence_cases()`

#### Purpose

Answers: "How does credit stance behavior change across alternate credit rule-state persistence settings and diagnostic event windows?" It is target-specific to credit stance persistence/stabilization and credit market stress/recovery windows.

#### Public output contract

Return type: `dict`.

Arguments/defaults:

- `cases: dict | None = None`
- `hysteresis_buffer: float = 0.05`
- `windows: dict | None = None`
- `include_diagnostics: bool = True`

Default cases:

- `base_p1_p1`
- `case_a_change2_state1`
- `case_b_change1_state2`
- `case_c_change2_state2`

Required/default windows include:

- `covid_initial_shock`
- `post_shock_recovery`
- `tight_spread_2021q2`
- `late_2022_volatility`

Result keys:

- `summary`
- `window_metrics`
- `shock_detection`
- `recovery_behavior`
- `tight_spread_behavior`
- `late_volatility`
- `full_period_stabilization`
- `diagnostics` when `include_diagnostics=True`

Public vocabulary includes credit state pair names, credit negative-date metrics, tight-spread metrics, late-volatility metrics, persistence setting names, and stabilization changed-count fields.

#### Implementation dependency map

Candidate-specific logic:

- default credit persistence cases and windows
- validation of required case/window shapes
- temporary mutation of credit `state_stabilization`
- shock/recovery/tight/late/full-period table assembly
- local helper closures: `first_negative_date`, `dominant_pair`, `window_slice`, `baa_metric`, `base_window_metrics`

Shared generic/private helpers:

- `_inclusive_window_slice()`
- `_ratio_or_na()`
- `trace_stance_score()`

Production/shared paths:

- `calculate_exposure_stance()` is rerun for each case.
- `trace_stance_score("credit")` uses the active rule-mapped credit diagnostic path, including credit adjustment metadata.

#### Generic/broader replacement path

No current public generic persistence-case comparison API exists.

Partial replacement path:

1. Copy the active exposure stance config.
2. Apply case-specific credit `state_stabilization` settings.
3. Recalculate exposure stance for each case.
4. Call `trace_stance_score("credit", include_raw_input=True, include_labels=False)`.
5. Manually assemble the seven public tables and restore original stance state.

Generic rule-mapped traces provide per-case diagnostics after config mutation, but they do not provide the credit-specific event-window tables.

#### Duplication assessment

`partially_covered` to `not_covered`. Underlying per-case traces are covered, but the main diagnostic purpose is the credit-specific persistence comparison and event-window reporting.

#### Compatibility risk

`high`. Prior reports document public result keys and table contracts.

#### Recommendation

`keep_as_specialized_wrapper`. A future generic persistence/stabilization-case core may support internals, but credit-specific public workflow and tables should remain unless explicitly redesigned.

## Cross-candidate pattern summary

Input smoothing comparison:

- `compare_credit_input_smoothing_effect()`
- `compare_curve_input_smoothing_effect()`

Both compare raw-input reconstruction to production prepared-input outputs. They share mechanics for recalculating component scores, reconstructing rule-mapped stance outputs, window summaries, changed counts, mean absolute differences, and spike reduction. This suggests shared internals, but public wrappers should be preserved.

Rule-mapped transition/stability summary:

- `diagnose_rule_mapped_stance_transitions()`
- `summarize_rule_mapped_stance_stability()`

Both derive convenience tables from `diagnose_rule_mapped_stance()`. They are more redundant than the comparison diagnostics, but they provide ready transition/summary shapes and public vocabulary.

Threshold/parameter-effect comparison:

- `compare_curve_move_driver_threshold_effect()`

It already uses a private parameter-effect helper, but public vocabulary is curve move-driver-specific. This suggests a shared private core with a specialized wrapper.

Stabilization/persistence case comparison:

- `compare_curve_positioning_stabilization_cases()`
- `compare_credit_stance_persistence_cases()`

Both compare alternate stabilization/persistence settings across cases/windows. Curve is closer to generic rule-mapped stabilization-case comparison. Credit includes target-specific historical market windows and credit state-pair metrics.

Historical-review single-case diagnostic:

- `diagnose_historical_review_case()`

This is the only fully redundant wrapper found in Stage 2.

## Replacement path matrix

| candidate | likely replacement path | coverage level | missing behavior / semantic difference | compatibility risk | recommendation |
|---|---|---|---|---|---|
| `diagnose_historical_review_case()` | `review_historical_cases(..., output="diagnostic")` | `fully_covered` | None beyond method name convenience | low/medium | `delete_candidate` subject to focused audit |
| `diagnose_rule_mapped_stance_transitions()` | `diagnose_rule_mapped_stance(..., include_scores=False, include_raw_states=True, include_stabilized_states=True, include_rule_case=True, include_labels=True)` plus shift/change derivation | `mostly_covered` | Ready transition columns and first-valid changed flag behavior | medium | `needs_runtime_contract_check` |
| `summarize_rule_mapped_stance_stability()` | `diagnose_rule_mapped_stance()` plus groupby/value_counts/summary derivations | `mostly_covered` | Public dict keys, summary table names, duration share fields, component display vocabulary | medium | `keep_active` |
| `compare_credit_input_smoothing_effect()` | No current public generic replacement; internal recalculation + stance reconstruction + summary assembly needed | `partially_covered` | Raw-vs-smoothed comparison workflow, windows, public columns | high | `genericize_behind_existing_api` |
| `compare_curve_input_smoothing_effect()` | No current public generic replacement; internal recalculation + stance reconstruction + summary assembly needed | `partially_covered` | Raw-vs-smoothed comparison workflow, windows, public columns | high | `genericize_behind_existing_api` |
| `compare_curve_move_driver_threshold_effect()` | Private parameter-effect helper plus target-specific assembly | `partially_covered` | Below-threshold/mixed counts, bucket labels, exact public vocabulary | high | `keep_as_specialized_wrapper` |
| `compare_curve_positioning_stabilization_cases()` | Private generic rule-mapped stabilization-case core could replace internals later | `partially_covered` | Public cases/windows/result keys/detail/summary tables | high | `genericize_behind_existing_api` |
| `compare_credit_stance_persistence_cases()` | Manual config mutation + `trace_stance_score("credit")` per case + target-specific table assembly | `partially_covered` / `not_covered` | Credit event-window workflow and seven public result tables | high | `keep_as_specialized_wrapper` |

## Stage 3 private-helper audit targets

Audit only these helper families if a later task proceeds toward deletion or genericization:

- Historical diagnostic wrapper family:
  - `diagnose_historical_review_case()`
  - confirm no candidate-only private helpers exist and no tracked/nontracked usage is expected.

- Rule-mapped transition/stability family:
  - `_rule_mapped_component_state_summary()`
  - `_rule_mapped_score_distribution()`
  - `_series_value_shares()`
  - transition assembly inside `diagnose_rule_mapped_stance_transitions()`

- Input smoothing comparison family:
  - `_default_credit_input_smoothing_windows()`
  - `_raw_credit_component_scores_for_input_smoothing_comparison()`
  - `_credit_input_smoothing_effect_detail()`
  - `_credit_input_smoothing_summary_row()`
  - `_default_curve_input_smoothing_windows()`
  - `_raw_curve_component_scores_for_input_smoothing_comparison()`
  - `_curve_input_smoothing_effect_detail()`
  - `_curve_input_smoothing_summary_row()`
  - shared recalculation/reconstruction/window/count helpers

- Parameter-effect family:
  - `_rule_mapped_component_parameter_effect_detail()`
  - `_curve_move_driver_score_from_prepared_inputs()`
  - threshold-specific assembly inside `compare_curve_move_driver_threshold_effect()`

- Curve stabilization-case family:
  - `_default_curve_stabilization_cases()`
  - `_neutral_curve_positioning_stabilization_overrides()`
  - `_default_curve_stabilization_windows()`
  - `_rule_mapped_stabilization_case_detail_comparison()`
  - `_curve_stabilization_case_detail()`
  - `_curve_stabilization_summary_row()`
  - `_curve_stabilization_window_row()`

- Credit persistence-case family:
  - local assembly logic inside `compare_credit_stance_persistence_cases()`
  - interactions with `calculate_exposure_stance()` and `trace_stance_score("credit")`
  - use of `_inclusive_window_slice()` and `_ratio_or_na()`

## Candidates excluded from deletion

Do not proceed toward deletion based on Stage 2 evidence:

- `compare_credit_input_smoothing_effect()`
- `compare_curve_input_smoothing_effect()`
- `compare_curve_move_driver_threshold_effect()`
- `compare_curve_positioning_stabilization_cases()`
- `compare_credit_stance_persistence_cases()`
- `summarize_rule_mapped_stance_stability()`

These either have high compatibility risk, unique target-specific workflow value, or public summary/table contracts documented in prior reports.

`diagnose_rule_mapped_stance_transitions()` is not excluded from eventual cleanup, but should not move directly to deletion. It needs runtime contract comparison and compatibility decision first.

`diagnose_historical_review_case()` is the only deletion-path candidate from this audit.

## Validation

This task is report-only.

Validation run:

- `git diff --check` - passed with no output.

No Python syntax check was required because no Python files were changed.

No production equality check was required because runtime behavior, schema behavior, YAML config, diagnostics behavior, public API behavior, and model outputs were not changed.

Runtime output comparison was not performed. This Stage 2 audit used static source inspection plus prior report contract evidence.
