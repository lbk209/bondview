# Module 1 case-comparison diagnostic similarity audit

## Executive recommendation

Recommendation: **curve cleanup should introduce helpers designed for later
credit reuse, but not modify credit yet**.

Scope estimate for the recommended path: **medium**.

`compare_credit_stance_persistence_cases(...)` is the closest structural peer to
`compare_curve_positioning_stabilization_cases(...)`, but it is not similar
enough to justify a shared profile/helper layer now. Curve cleanup should remain
behavior-local in implementation, while naming any small new helpers generically
where their semantics are already shared: window slicing, ratio calculation,
dominant value, transition counts, score-change flags, spike flags, and simple
distribution/transition row builders.

Do not add YAML/schema fields for this cleanup. Both curve and credit can derive
model-facing names from existing rule-mapped config/spec metadata, but many
names in these diagnostics are public diagnostic aliases, event/window labels,
scenario labels, or bespoke output table columns.

No production code, YAML, or schema changes are recommended in this audit.

## Required search commands run

- `rg -n "^    def compare_.*\\(" module1.py`
- `rg -n "stabilization|persistence|threshold|cases|windows|diagnostics_by_case|detail_by_case|window_metrics|score_distribution|bucket_transition" module1.py`
- `rg -n "compare_curve_positioning_stabilization_cases|compare_credit_stance_persistence_cases|compare_curve_move_driver_threshold_effect" module1.py`
- `rg -n "_default_.*cases|_default_.*windows|_neutral_.*stabilization|state_stabilization" module1.py`

## Inventory

| Public diagnostic | Target | Comparison axis | Accepts cases | Accepts windows | Mutates config temporarily | Rebuilds stance outputs | Result keys / output | Major private helpers | Specificity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `compare_horizon_cases(...)` (`module1.py:464`) | Historical review across any requested target | Horizon settings | Yes, via `horizon_cases` / `horizon_grid` | Indirectly through `review_historical_cases(output="windows")`, not a `windows` arg | Uses a temporary `RegimeModule` instance and changes `rgm.horizons` (`module1.py:542-580`) | Yes, recalculates features, component scores, labels, and exposure stance per case (`module1.py:582-591`) | One selected DataFrame controlled by `output`: `summary`, `horizon_cases`, `compact`, `cases`, `diagnostic`, or forwarded review outputs | `_build_horizon_cases_df(...)`, `validate_horizons(...)`, `review_historical_cases(...)` | Generic batch review diagnostic, not close to stabilization cleanup |
| `compare_smoothing_effect(...)` (`module1.py:7752`) | `credit`, `curve_positioning`, `duration` where supported | Input-preparation or score smoothing | No | Yes | No | Reconstructs diagnostic detail for raw-vs-smoothed comparison; does not mutate production config | `summary`, `window_summary`, optional `detail` (`module1.py:7727-7750`) | `_smoothing_diagnostic_windows(...)`, `_smoothing_diagnostic_target_profile(...)`, `_rule_mapped_input_smoothing_effect_detail(...)`, `_smoothing_effect_result(...)`, `_rule_mapped_input_smoothing_summary_row(...)` | Generic smoothing diagnostic; useful pattern, not a shared case helper target |
| `compare_curve_move_driver_threshold_effect(...)` (`module1.py:8181`) | Curve positioning / `curve_move_driver` | Threshold/filter sensitivity for `min_abs_value` | No | No | No | Rebuilds alternate component score and stance effect using helper, but not full exposure stance | `summary`, optional `detail` (`module1.py:8406-8409`) | `_diagnostic_input_spec_by_role(...)`, `_prepared_filtered_input_columns(...)`, `_curve_move_driver_score_from_prepared_inputs(...)`, `_rule_mapped_component_parameter_effect_detail(...)` | Curve-specific threshold sensitivity |
| `compare_curve_positioning_stabilization_cases(...)` (`module1.py:8724`) | Curve positioning | Stabilization override cases | Yes | Yes | No | Uses side-by-side rule-mapped breakdowns with different stabilization overrides; does not mutate module state | `summary`, `window_summary`, `detail_by_case`, `bucket_transition_summary`, `score_distribution`, optional `diagnostics_by_case` (`module1.py:8795-8803`) | `_default_curve_stabilization_cases(...)`, `_default_curve_stabilization_windows(...)`, `_curve_stabilization_case_detail(...)`, `_curve_stabilization_summary_row(...)`, `_curve_stabilization_window_row(...)`, `_rule_mapped_stabilization_case_detail_comparison(...)` | Curve-specific public wrapper over partly generic rule-mapped comparison |
| `compare_credit_stance_persistence_cases(...)` (`module1.py:8806`) | Credit stance | Temporary persistence settings with fixed hysteresis buffer | Yes | Yes | Yes, deep-copies and replaces `exposure_stance_config["exposure_stances"]["credit"]["state_stabilization"]` per case (`module1.py:9008-9025`) | Yes, calls `calculate_exposure_stance()` per case and restores config/outputs in `finally` (`module1.py:9026-9140`) | `summary`, `window_metrics`, `shock_detection`, `recovery_behavior`, `tight_spread_behavior`, `late_volatility`, `full_period_stabilization`, optional `diagnostics` (`module1.py:9219-9229`) | local nested helpers, `_inclusive_window_slice(...)`, `_ratio_or_na(...)`, `trace_stance_score(...)` | Credit-specific event diagnostic with some shared case/window mechanics |

## Credit-vs-curve comparison

### Structural similarities

- Both accept `cases`, `windows`, and `include_diagnostics`.
- Both define default cases and default windows in code.
- Both iterate case-by-case and produce multiple output tables.
- Both use `_inclusive_window_slice(...)` for window handling, directly or via a
  nested adapter.
- Both use `_ratio_or_na(...)` for ratio columns.
- Both depend on rule-mapped stance stabilization concepts.
- Both expose full per-case diagnostic detail when requested.

### Important differences

| Area | Curve stabilization | Credit persistence | Feasibility |
| --- | --- | --- | --- |
| Case validation | Minimal; passes each case config into rule-mapped stabilization resolution | Explicit validation for two integer persistence keys and `hysteresis_buffer` | Possible with small adapter, but not urgent |
| Default cases | `_default_curve_stabilization_cases(...)`, including hysteresis and persistence combinations (`module1.py:8119-8143`) | Inline credit case catalog with four persistence combinations (`module1.py:8852-8870`) | Not worth sharing; scenario policy differs |
| Default windows | `_default_curve_stabilization_windows(...)` has curve event windows plus full history (`module1.py:8155-8161`) | Inline required credit event windows (`module1.py:8872-8917`) | Not worth sharing; event policy differs |
| Rule-mapped config/spec usage | Directly resolves rule-mapped schema and builds baseline/case breakdowns in `_rule_mapped_stabilization_case_detail_comparison(...)` | Uses credit config mutation plus `trace_stance_score("credit")` | Unsafe to unify now; execution model differs |
| Temporary config mutation | No | Yes, with deep-copy restore in `finally` | Unsafe to share case runner without broader design |
| Detail construction | Side-by-side raw/stabilized public aliases in `detail_by_case` | Trace output as returned by `trace_stance_score`, copied into `diagnostics` | Not worth sharing |
| Summary construction | One general summary plus bucket transition and score distribution tables | Event-specific tables: shock, recovery, tight spread, late volatility, full-period stabilization | Not worth sharing |
| Window summary | Generic curve metrics per provided window | Credit `window_metrics` plus special tables keyed to required windows | Possible only for small window metric primitives |
| Transition counts | `_count_series_changes(...)` for score and bucket transitions | Counts stabilization change flags, daily score diffs, large moves | Possible with small adapters only |
| Spike counts | Uses `_count_one_day_spikes(...)` | No direct equivalent; uses late-period large score moves | Not worth sharing |
| Dominant value | `_curve_dominant_value(...)` for labels/rule cases | Nested `dominant_pair(...)` over `credit_state_pair` | Safe shared helper later if renamed/genericized |
| Output table shape | `summary`, `window_summary`, `bucket_transition_summary`, `score_distribution` | `window_metrics`, `shock_detection`, `recovery_behavior`, `tight_spread_behavior`, `late_volatility`, `full_period_stabilization` | Unsafe to unify without risking public columns/order |

Overall classification: **possible with small adapters for primitives, not worth
sharing as a common case-diagnostic framework now**.

## Helper reuse feasibility

| Candidate helper area | Current users | Classification | Rationale |
| --- | --- | --- | --- |
| `_inclusive_window_slice(...)` | Curve stabilization, credit persistence nested `window_slice`, smoothing effect | Safe shared helper now | Already shared and behavior is simple. |
| `_ratio_or_na(...)` | Curve stabilization, credit persistence, threshold/smoothing paths | Safe shared helper now | Already shared. |
| Dominant non-null value | Curve `_curve_dominant_value(...)`; credit nested `dominant_pair(...)` | Possible with small adapter | A generic dominant-value helper could replace curve naming and support credit pair mode, but tie behavior and returned ratio must be preserved. |
| Case default builders | Curve private functions; credit inline defaults | Not worth sharing | Defaults are diagnostic policy and have different schema. |
| Window default builders | Curve private function; credit inline required windows | Not worth sharing | Credit requires specific windows for downstream tables; curve includes `full_history`. |
| Case validation | Credit explicit; curve delegated to rule-mapped override resolver | Possible with small adapter | Could normalize map validation, but benefits are small and error messages may change. |
| Temporary case runner | Credit mutates/restores config; curve does not | Unsafe | Combining runners would mix stateful and stateless execution models. |
| Rule-mapped detail construction | Curve uses `_rule_mapped_stabilization_case_detail_comparison(...)`; credit uses `trace_stance_score(...)` | Unsafe now | Credit is already production-trace-oriented and event-specific. |
| Window row builders | Curve `_curve_stabilization_window_row(...)`; credit nested `base_window_metrics(...)`; smoothing `_smoothing_effect_result(...)` | Possible with small adapter | Shared window iteration could work, but output columns and required-window semantics differ. |
| Transition count helpers | Curve `_count_series_changes(...)`; credit sums stabilization flags and score diffs | Possible with small adapter | Keep primitive helpers, do not create common table builder yet. |
| Score distribution | Curve manual `score_distribution`; generic `_rule_mapped_score_distribution(...)` exists elsewhere | Possible with small adapter | Useful for curve local cleanup only; credit persistence does not emit distribution tables. |
| Bucket transition summary | Curve manual bucket triplets; no credit equivalent table | Not worth sharing across credit | Useful only for curve local profile cleanup. |

## Hard-coded name classification

### Curve stabilization diagnostic

Model/config-derived names that should come from existing config/spec where
practical:

- State input names: `curve_change`, `curve_state`, `curve_move_driver`.
- Source scores: `curve_change_score`, `curve_state_score`,
  `curve_move_driver_score`.
- Rule-mapped state outputs: `curve_change_bucket_raw`,
  `curve_change_bucket`, `curve_state_bucket_raw`, `curve_state_bucket`,
  `yield_move_driver_bucket_raw`, `yield_move_driver_bucket`.
- Rule/final outputs: `curve_positioning_rule_case`,
  `curve_positioning_score`, `curve_positioning`,
  `curve_positioning_strength`.
- Stabilization changed outputs:
  `state_stabilization_changed_curve_change`,
  `state_stabilization_changed_curve_state`,
  `state_stabilization_changed_curve_move_driver`,
  `state_stabilization_changed_any`.

Public diagnostic aliases that should remain stable:

- `raw_curve_change_bucket`, `stabilized_curve_change_bucket`,
  `raw_curve_state_bucket`, `stabilized_curve_state_bucket`,
  `raw_yield_move_driver_bucket`, `stabilized_yield_move_driver_bucket`.
- `raw_curve_positioning_rule_case`,
  `stabilized_curve_positioning_rule_case`.
- `raw_curve_positioning_score`, `stabilized_curve_positioning_score`,
  `raw_curve_positioning`, `stabilized_curve_positioning`,
  `raw_curve_positioning_strength`,
  `stabilized_curve_positioning_strength`.
- `score_diff`, `score_changed`, `direction_changed`, `strength_changed`.
- Result keys and table schemas: `summary`, `window_summary`,
  `detail_by_case`, `bucket_transition_summary`, `score_distribution`,
  `diagnostics_by_case`.

Event/window/scenario names that are diagnostic policy:

- Case IDs: `neutral_base`, `persistence_3`, `hysteresis_005`,
  `hysteresis_005_persistence_3`, `hysteresis_010_persistence_3`.
- Window IDs: `taper_tantrum_review`, `fed_hiking_2022`,
  `covid_shock_2020`, `full_history`.

Internal temporary/profile-generated columns:

- `raw_score_change_flag`, `stabilized_score_change_flag`.
- `raw_one_day_spike_flag`, `stabilized_one_day_spike_flag`.
- Bucket transition triplets and score distribution score-column pairs.

### Credit persistence diagnostic

Model/config-derived names that could come from existing config/spec:

- State input names: `credit_spread_change`, `credit_spread_state`.
- Source scores: `credit_spread_change_score`,
  `credit_spread_state_score`.
- Raw/stabilized state outputs:
  `credit_spread_change_state_raw`, `credit_spread_change_state`,
  `credit_spread_state_category_raw`, `credit_spread_state_category`.
- Rule/final outputs: `credit_state_pair`, `credit_stance_score`,
  `credit_stance`, `credit_stance_strength`.
- Stabilization changed outputs:
  `state_stabilization_changed_change_state`,
  `state_stabilization_changed_spread_state`,
  `state_stabilization_changed_pair`.
- Adjustment/metadata outputs:
  `base_rule_score`, `credit_spread_change_intensity`,
  `credit_spread_state_intensity`, `rule_adjustment`.

Public diagnostic output aliases that should remain stable:

- Result keys: `summary`, `window_metrics`, `shock_detection`,
  `recovery_behavior`, `tight_spread_behavior`, `late_volatility`,
  `full_period_stabilization`, `diagnostics`.
- Summary/event columns including `change_persistence`, `state_persistence`,
  `covid_first_credit_negative_date`, `covid_delay_days_vs_base`,
  `recovery_mean_score`, `recovery_negative_score_days`,
  `tight_2021q2_mean_score`, `tight_2021q2_tight_state_ratio`,
  `late_2022_max_abs_daily_score_move`,
  `late_2022_large_move_gt_0_5_count`,
  `late_2022_large_move_gt_1_0_count`, `full_changed_pair_count`,
  `full_changed_pair_ratio`.
- Window metric/event table columns such as `dominant_credit_state_pair`,
  `changed_pair_count`, `changed_pair_ratio`,
  `changed_change_state_count`, `changed_spread_state_count`,
  `first_credit_negative_date`, `delay_days_vs_base`,
  `tight_state_count`, `tight_state_ratio`, `tight_pair_count`,
  `tight_pair_ratio`, `large_move_gt_0_5_count`,
  `large_move_gt_1_0_count`.

Event/window/scenario names that are diagnostic policy:

- Case IDs: `base_p1_p1`, `case_a_change2_state1`,
  `case_b_change1_state2`, `case_c_change2_state2`.
- Required window IDs: `covid_initial_shock`, `post_shock_recovery`,
  `tight_spread_2021q2`, `late_2022_volatility`.
- Threshold/event constants: negative score threshold `-0.5`, tight-state
  label `tight`, large move thresholds `0.5` and `1.0`.

Internal temporary columns/profile candidates:

- Required diagnostic column set in `compare_credit_stance_persistence_cases`.
- Case-setting key mapping from persistence settings to `state_stabilization`.
- Repeated `credit_stance_score`/`credit_state_pair` access in local window and
  event calculations.

### Curve threshold sensitivity diagnostic

Model/config-derived names:

- Target/component: `curve_positioning`, `curve_move_driver`.
- Prepared/filtered input roles from diagnostic input specs.
- `curve_move_driver_score` and bucket config from component config.

Public diagnostic aliases that should remain stable:

- `curve_move_driver_score_without_threshold`,
  `curve_move_driver_score_with_threshold`,
  `curve_move_driver_bucket_without_threshold`,
  `curve_move_driver_bucket_with_threshold`,
  `curve_positioning_score_without_threshold`,
  `curve_positioning_score_with_threshold`,
  `curve_positioning_score_diff_due_to_threshold`,
  `curve_move_driver_score_changed_by_threshold`,
  `curve_positioning_score_changed_by_threshold`.
- Summary columns describing rows below threshold and changed-score counts.

Internal temporary/profile candidates:

- Baseline/alternate output aliases passed to
  `_rule_mapped_component_parameter_effect_detail(...)`.

### Smoothing and horizon diagnostics

Smoothing already has a private profile (`SmoothingDiagnosticTargetProfile`) and
derives many aliases from `RuleMappedDiagnosticSpec`. Its hard-coded result
keys are public diagnostic output vocabulary and should remain stable.

Horizon comparison case/window names come from user input or historical review
outputs. Its hard-coded names are mostly output options and review metadata, not
stabilization model structure.

## Cleanup strategy

Recommended strategy:

1. Keep the first curve cleanup implementation local to
   `compare_curve_positioning_stabilization_cases(...)` and its private helpers.
2. Introduce a small private curve stabilization profile derived from existing
   `RuleMappedDiagnosticSpec` where possible.
3. Name primitive helpers generically if their semantics are already shared,
   for example score-change flag series, one-day-spike flag series, dominant
   non-null value, distribution-row builder, or transition-count-row builder.
4. Do not change `compare_credit_stance_persistence_cases(...)` in the curve
   cleanup task.
5. Do not create a shared case-diagnostic framework until there is a second
   implementation task that actually changes credit and can prove equality for
   all credit tables.

Why not a shared profile/helper layer now:

- Credit and curve differ in execution model: credit mutates/restores config and
  recalculates stance outputs; curve builds baseline/case breakdowns side by
  side without mutating module state.
- Credit output is event-specific and table-rich; curve output is generalized
  around raw/stabilized detail, bucket transitions, score distribution, and
  generic windows.
- A broad shared layer would likely move responsibilities across diagnostic
  boundaries and increase risk to public output columns, dtypes, ordering, and
  `pd.NA` behavior.

## Scope estimate

Recommended path: **medium**.

Reasons:

- Curve-only profile cleanup is moderate: it touches detail construction,
  summary/window construction, bucket transition rows, score distribution rows,
  and optional diagnostics aliasing.
- Adding a few primitive helpers is small by itself, but equality validation is
  non-trivial because the public return shape includes nested DataFrames by
  case.
- Designing the helpers for later credit reuse adds naming/API discipline, but
  should not require credit changes now.

A shared curve+credit implementation would be **large** and is not recommended
for the first cleanup.

## Future validation plan

Always run:

- `python -m py_compile module1.py`
- `git diff --check`
- Search checks for changed helper names and hard-coded aliases, including:
  `rg -n "compare_curve_positioning_stabilization_cases|_curve_stabilization_case_detail|_curve_stabilization_summary_row|_curve_stabilization_window_row" module1.py`
  and targeted searches for preserved public aliases.

For curve cleanup, run old-vs-new equality checks covering:

- default cases/default windows;
- custom cases;
- custom windows;
- `include_diagnostics=True`;
- `include_diagnostics=False`.

Curve equality should cover:

- `summary`
- `window_summary`
- `detail_by_case`
- `bucket_transition_summary`
- `score_distribution`
- `diagnostics_by_case` when included

Checks should compare result keys, DataFrame column order, index, values,
practical dtypes, and missing-value behavior.

For any future credit change or shared-helper adoption that touches credit,
run old-vs-new equality checks covering:

- default cases/default windows;
- custom cases;
- custom windows;
- `include_diagnostics=True`;
- `include_diagnostics=False`.

Credit equality should cover:

- `summary`
- `window_metrics`
- `shock_detection`
- `recovery_behavior`
- `tight_spread_behavior`
- `late_volatility`
- `full_period_stabilization`
- `diagnostics` when included

Credit checks must also confirm config/output restoration after the diagnostic
returns, because that is part of the current credit behavior.

## Behavior impact of this audit

This report is audit-only. No production code, YAML, schema, public APIs, output
columns, or model outputs were changed.
