# Module 1 Component Score Path Consolidation Review

## Scope and result

This task consolidated ordinary and fixed-anchor component scoring in
`module1_calculator.py` without changing model behavior, configuration
interpretation, output ordering, or supported error contracts.

`_calculate_current_state_component_score()` was removed. Its two live roles now
belong to the existing function-authoritative methods:

- `_calculate_single_feature_component_score()` owns ordinary and fixed-anchor
  `single_feature_score` calculation.
- `_calculate_weighted_feature_component_score()` owns ordinary and fixed-anchor
  `weighted_feature_score` calculation.

`curve_move_driver_score` remains a distinct calculation path. Its input
resolution, input preparation, minimum-absolute-value filtering, bucket score
resolution, sign classifier, clipping, and output behavior were not changed.

The only sensitivity compatibility edits were removal of the deleted helper from
`Module1SensitivityDiagnostics._CALCULATOR_HELPERS` and direct dispatch of
fixed-anchor single/weighted configurations through the two authoritative
calculator methods. The synthetic calculator bridge, state synchronization,
forwarding mechanism, and broader sensitivity structure were not changed.

## Pre-edit characterization

A temporary baseline was captured before editing from the canonical
`data/module1_config.yaml` and checked-in local raw data. Construction used the
non-secret environment value `FRED_API_KEY=offline_dummy`; no FRED download method
or other network request was made.

The baseline characterized every supported score form:

| Form | Characterized behavior |
| --- | --- |
| Ordinary `single_feature_score` | Feature lookup, optional input preparation, sign application, normalization, ordinary score smoothing, and clipping. |
| Ordinary `weighted_feature_score` | Ordered input traversal, required explicit numeric weights, feature lookup, optional input preparation, per-feature normalization, weighted sum, ordinary score smoothing, and clipping. |
| Fixed-anchor single feature | Feature lookup, optional input preparation, fixed-anchor transformation, sign application, smoothing bypass, and clipping. |
| Fixed-anchor weighted feature | Ordered input traversal, per-feature preparation and anchor transformation, explicit numeric weights for combined inputs, weighted sum, sign application, smoothing bypass, and clipping. |
| Fixed-anchor one-input implicit weight | One input with no declared weight receives the established implicit `1.0`; a declared or combined-weight form still requires valid explicit weights. |
| `curve_move_driver_score` | Two-input preparation enabled and disabled, minimum-absolute-value filtering behavior, configured bucket order and scores, missing behavior, and clipping. |
| Sensitivity recalculation | Prepared and unprepared results for every canonical component plus full Credit and Curve Positioning component recalculation tables. |

The baseline contained five canonical pipeline outputs, 14 direct prepared or
unprepared score cases, seven copied-config dispatch cases, 24 sensitivity cases,
and 21 pre-edit malformed/error cases.

## Authoritative calculation order

The consolidated single-feature method preserves these orders:

- ordinary: feature resolution, optional preparation, sign, normalization;
- fixed anchor: feature resolution, optional preparation, anchor transformation,
  sign.

The consolidated weighted method preserves the different validation and
calculation order required by each form:

- ordinary: input mapping and feature checks, explicit weight presence and
  numeric validation, optional preparation, normalization, weighted sum;
- fixed anchor: input mapping and feature checks, optional preparation, anchor
  transformation, implicit or explicit weight resolution and numeric validation,
  weighted sum, sign.

Production dispatch continues to apply ordinary score smoothing only to
non-fixed-anchor scores. Both forms then apply clipping. This retains the
established fixed-anchor smoothing bypass even when copied test configurations
declare normalization and smoothing keys.

No new helper, wrapper, alias, compatibility delegate, registry, class, or
abstraction layer was introduced.

## Error-contract validation

Nineteen live-equivalent malformed cases retained their exact exception type and
message:

- missing single-feature and weighted-feature inputs;
- non-mapping weighted inputs;
- missing features;
- missing ordinary weights;
- invalid ordinary and fixed-anchor weights;
- missing weights for multi-input or partially weighted fixed-anchor forms;
- missing anchors and invalid anchor order;
- invalid fixed-anchor sign;
- unsupported ordinary and fixed-anchor score functions.

Two pre-edit cases directly invoked `_calculate_current_state_component_score()`
itself. Those private, helper-only entry points no longer exist because the helper
was intentionally removed. Repository searches found no live caller outside the
production and sensitivity call sites migrated in this task. The production
unsupported-fixed-function error remains exact.

## Validation results

- Python compilation passed for `module1_calculator.py`,
  `module1_sensitivity_diagnostics.py`, and directly affected import consumers.
- Canonical schema validation returned zero issues, and strict calculator loading
  passed using canonical local files.
- Features, component scores, component labels, stance scores, and exposure stance
  matched the pre-edit baseline exactly. Comparisons covered indexes, column order,
  values, practical dtypes, names, and missing-value masks.
- All 14 direct prepared/unprepared score cases matched exactly.
- All seven copied-config dispatch cases matched exactly, covering ordinary single,
  ordinary weighted, fixed-anchor single, fixed-anchor weighted with implicit,
  explicit, and multi-input weights, plus curve move driver.
- All 24 sensitivity prepared/unprepared cases matched exactly.
- All 19 live-equivalent malformed/error contracts matched exactly.
- Removed-symbol searches found no Python or notebook reference, alias, or
  replacement wrapper. Remaining text matches are historical reports.
- `module1_schema.py`, analysis, diagnostics, historical analysis, YAML, data, and
  documentation files were unchanged.

## Behavior impact

Model outputs did not change. Scoring formulas, score ordering, declaration order,
normalization, weight semantics, anchor behavior, smoothing, clipping, sensitivity
results, schema behavior, YAML, and data are unchanged.
