# Module 1 Sensitivity residual cleanup review

## Scope and outcome

This review covers the final residual production and test cleanup after the
Module 1 Sensitivity migrations. The implementation removes only names with no
remaining caller or one-use wrappers superseded by their authoritative local
operation. It does not change any public Sensitivity signature or successful
workflow output.

No YAML, Calculator, Diagnostics, Analysis, Historical Analysis, scoring,
labeling, threshold, stabilization, horizon, or financial logic changed.

## Removed production names

Repository-wide reference checks established the following removals:

| Removed name | Evidence and replacement |
| --- | --- |
| `Module1SensitivityDiagnostics._diagnostic_input_spec` | No caller remained. Role-based threshold selection continues through the separately justified `_diagnostic_input_spec_by_role`, which has four call sites and owns exact-match validation. |
| `Module1SensitivityDiagnostics._curve_positioning_stance_config` | One caller and no independent policy remained. The caller now reads the already isolated `exposure_stance_config` directly and retains the missing-curve-config error. |
| `Module1SensitivityDiagnostics._credit_stance_config` | No caller remained anywhere in the repository. |
| `Module1SensitivityDiagnostics._prefixed_smoothing_pair_metrics` | One caller merely prefixed the result of `_smoothing_pair_comparison_metrics`. The caller now performs that column-name mapping locally. |
| `Module1SensitivityDiagnostics._count_series_changes` | One production caller merely summed `_series_change_mask`. Smoothing counts now sum the authoritative mask directly. The independently owned same-named Diagnostics transition helper remains in `Module1Diagnostics`. |
| `Module1SensitivityDiagnostics._count_one_day_spikes` | One production caller merely summed `_one_day_spike_mask`. Smoothing counts now sum the authoritative mask directly. |
| `self.historical_cases` | Assigned by Sensitivity construction but never read. The constructor argument remains accepted to preserve the public signature. |
| `self.historical_expected_label_validation` | Assigned by Sensitivity construction but never read. The constructor argument remains accepted to preserve the public signature. |

The final static audit found a real internal caller for every remaining
Sensitivity private method. No unused import or dataclass remained:
`SmoothingDiagnosticTargetProfile`, `DiagnosticInputSpec`,
`RuleMappedDiagnosticSpec`, `dataclass`, and `replace` all remain active.

## Completed-result error messages

Calculator-lifecycle instructions were replaced with result-specific wording
without moving the validations or changing their exception type.

The changed fields and workflows are:

- `Module1Result.features`, `scores`, `exposure_stance`, and
  `module1_config` for input-smoothing comparison;
- `Module1Result.features`, `scores`, `exposure_stance`, and
  `module1_config` for curve move-driver threshold comparison;
- `Module1Result.scores`, `exposure_stance`, and `module1_config` for curve
  stabilization comparison;
- `Module1Result.module1_config`, `features`, `scores`, `labels`,
  `exposure_stance`, and `stance_scores` for credit-persistence comparison;
- the same result-specific fields in the private recalculation,
  reconstruction, and parameter-effect checks reached by those public
  workflows.

A table-driven public-workflow test covers each changed error path. Valid-input
behavior and validation timing remain unchanged.

## Retained copied Sensitivity state

The following copied or locally derived state remains because it has active
callers:

- `result`: default smoothing-window Historical Analysis and case-local credit
  result construction;
- `_diagnostics`: prepared-input metadata, completed traces, and rule-mapped
  specifications;
- `data`: credit smoothing raw-input context;
- `features`: score recalculation, smoothing context, and threshold comparison;
- `scores`: smoothing reconstruction, threshold comparison, curve
  stabilization, and credit scenarios;
- `labels`: completed-result prerequisite for credit tracing;
- `stance_scores`: completed-result prerequisite for credit scenarios;
- `exposure_stance`: smoothing, threshold, and curve-stabilization baselines;
- `module1_config`: smoothing-layer discovery and case-local configuration;
- `feature_config`: the credit smoothing raw-column mapping;
- `component_config`: Calculator-owned component calculations and
  reconstruction;
- `exposure_stance_config`: stance labels and case calculations;
- `horizons`: component input preparation and threshold scoring;
- `historical_context`: default smoothing-window resolution.

All remain isolated copies where they were copies before this task. No caller
can mutate the supplied `Module1Result` or its configuration through these
views.

## Transitional-detail decisions

1. The credit-persistence `baa10y_change`/`baa10y` consumer-local reorder is
   retained. It protects the established public diagnostic column order, which
   is fingerprinted.
2. The curve-threshold `"_prepared_for_" -> "_filtered_for_"` fallback is
   retained. Diagnostics has no filtered spec when the configured filter is
   absent, so the fallback still supplies the established output name without
   introducing a wrapper.
3. `_curve_stabilization_metrics` continues to derive event counts from the
   authoritative transition and spike masks. Reusing stored full-history flags
   would break window-boundary semantics; adding a mode switch would increase,
   not reduce, structure.
4. The PR #145 horizon fakes are retained. They are narrow boundary fakes: the
   Calculator fake delegates validation to the real Calculator method, makes
   post-construction horizon assignment impossible, and constructs only the
   minimal completed result required to verify metadata. The Historical fake
   supplies only report and non-summary tables. Their constructor-boundary,
   custom-base, metadata, ordering, argument, determinism, and no-network
   coverage remains explicit.
5. The one-use curve stance accessor was removed. The dead credit stance
   accessor was also removed. Other one-use helpers remain where they own
   validation, ordering, transformation, or complete output assembly.

The outer
`exposure_stances.credit.state_stabilization` compatibility mapping and its
case-local synchronization remain unchanged for the separate Task 9
configuration cleanup.

## Test-structure cleanup and fingerprints

The tests no longer assert that historical private helper names are absent from
Sensitivity. Ownership remains protected behaviorally through mocks of the
Diagnostics-owned prepared-input and completed-trace interfaces.

The transition/spike test now asserts the authoritative masks and sums those
masks directly; it no longer preserves removed count-wrapper names. A duplicate
threshold-detail fingerprint assertion was removed from the prepared-input
ownership test because the public threshold contract test fingerprints the
same table under the same scenario. The ownership test retains its semantic
Diagnostics call assertions.

The suite retains 32 fingerprint expectations representing 31 unique values.
The intentional duplicate is the identical credit-persistence diagnostic
fingerprint for two cases with identical settings. Retained fingerprint
categories are:

- ordered prepared-input Diagnostics outputs, including missing-source
  behavior;
- completed credit and curve trace outputs;
- credit and curve smoothing summaries, windows, and details;
- default smoothing windows;
- curve-threshold summary and detail;
- custom/default curve-stabilization summary, windows, bucket transitions,
  and score distribution;
- every custom credit-persistence output table and each diagnostic case;
- default credit-persistence summary and window metrics.

No fingerprint value changed. Semantic assertions for keys, columns, ordering,
indexes, dtypes, missing values, defaults, optional detail/diagnostics,
immutability, deterministic repetition, corrected credit behavior, Diagnostics
ownership, and horizon constructor ownership remain alongside the
fingerprints.

## Behavior statement

No public key, DataFrame column, ordering, row/case/window order, dtype,
missing-value behavior, default, successful output value, diagnostic output,
model output, or financial behavior changed. Error exception types and
validation locations did not change; only stale lifecycle instructions now
identify the missing `Module1Result` field.
