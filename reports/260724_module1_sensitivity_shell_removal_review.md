# Module 1 Sensitivity synthetic-calculator removal review

## Scope and conclusion

`Module1SensitivityDiagnostics` no longer creates or retains an incomplete
`Module1Calculator`. The synthetic calculator, state-field registry, helper
registry, state synchronization, and `__getattr__` dispatch are removed.

Result inspection continues to use copied result-associated data and
configuration. Local counterfactual reconstruction uses explicit stateless
calculator capabilities. Full horizon scenarios continue to use normally
initialized calculators and completed `Module1Result` objects.

## Synthetic dependency classification

The former `_CALCULATOR_HELPERS` dependencies were classified as follows.

### Configured component-score calculation

The following calls formed one calculation-owned operation:

- `_calculate_single_feature_component_score`;
- `_calculate_weighted_feature_component_score`;
- `_calculate_curve_move_driver_score`;
- `_clip_score`;
- `_curve_move_driver_bucket_scores`;
- `_component_score_bucket_config`;
- `_curve_move_driver_score_from_prepared_inputs`.

They are now reached through
`Module1Calculator.calculate_component_score(features, component_name,
score_config, horizons, ...)`. The method accepts all operational state
explicitly and is used by both normal Calculator component execution and
Sensitivity input-preparation and curve-threshold comparisons.

Private normalization, preparation, fixed-anchor, clipping, and curve-driver
helpers remain calculator implementation details.

### Component bucket classification

Sensitivity previously called `_score_bucket` and manually resolved the
component bucket configuration. It now calls
`Module1Calculator.classify_component_score_buckets` with an explicit score
Series and bucket mapping. The capability retains Calculator's existing exact
score/range/default bucket semantics.

### Exposure score labeling and output calculation

Sensitivity previously called `_label_stance_direction`,
`_label_stance_strength`, and the stateful `calculate_exposure_stance` through
the shell.

- `Module1Calculator.label_exposure_stance_score` now labels an explicit score
  Series from explicit stance configuration and label rules.
- `Module1Calculator.calculate_exposure_stance_outputs` now returns stance-score
  and labeled exposure tables from explicit component scores, component
  configuration, and exposure-stance configuration.

Normal Calculator execution delegates to the same output implementation and
assigns the returned tables to calculator state. Sensitivity uses the pure
return values for local persistence comparisons and restores only its own
defensive local copies.

### Existing stateless capabilities

Sensitivity continues to use the established authoritative capabilities for:

- component input preparation;
- rule-mapped stance specification resolution;
- rule-mapped stance breakdown construction;
- stabilization overrides.

### Full scenario and consumer-owned behavior

`compare_horizon_cases` continues to construct normal calculators, apply
validated horizon overrides, run the complete pipeline, create completed
results, and perform historical review.

Scenario comparison, metrics, table assembly, column selection, summaries, and
reporting remain Sensitivity-owned.

## Removed compatibility machinery

The following are removed:

- `self.calculator`;
- `_CALCULATOR_STATE_FIELDS`;
- `_CALCULATOR_HELPERS`;
- `_sync_calculator_state`;
- calculator-helper dispatch through `__getattr__`;
- `object.__new__(Module1Calculator)`;
- copied `default_horizons`, `horizon_overrides`, and
  `module1_config_validation`, which existed only for shell synchronization;
- the Sensitivity forwarding method for curve-driver scoring.

Repository-wide Python scans find no remaining synthetic calculator
construction, synchronization registry, dispatcher, or downstream private
calculator-helper call.

Historical reports that describe earlier states remain unchanged.

## Retained Sensitivity state

Sensitivity retains defensive copies of `data`, `features`, `scores`, `labels`,
`stance_scores`, `exposure_stance`, `module1_config`, the three derived
configuration views, and `horizons` because current comparison, tracing,
reconstruction, or reporting paths reference them.

Historical context, historical cases, and expected-label validation inputs also
remain because they are active public constructor inputs.

Credit persistence comparisons temporarily modify only Sensitivity-owned copies
inside an existing `try/finally` boundary. The authoritative caller result and
its configuration are never modified, and repeated calls are tested for exact
equality.

## Tests and parity

Focused tests verify:

- constructed-result Sensitivity initialization does not initialize or retain a
  calculator and performs no YAML, validation, environment, or file access;
- removed shell attributes and dispatch are absent;
- repeated result inspection is call-order independent;
- new explicit calculator capabilities do not mutate features, scores, or
  configuration;
- full horizon scenarios construct normal calculators;
- identical horizon scenarios are equal and a changed horizon produces expected
  review differences;
- repeated credit persistence comparisons are identical and do not mutate the
  source result;
- established real-pipeline regression outputs remain unchanged.

An exact baseline/current comparison matched:

- features, scores, labels, stance scores, and exposure stances;
- duration, credit, and curve-positioning smoothing outputs;
- curve-driver threshold summary and detail;
- every curve-positioning stabilization output and case detail;
- every credit persistence summary, detail, and diagnostic table;
- representative validation errors;
- affected public Sensitivity signatures;
- columns, order, indexes, values, dtypes, and missing values.

## Behavior impact

No Module 1 YAML, schema rule, financial calculation, threshold, bucket, label,
weight, rule mapping, stabilization behavior, missing-value behavior, output
shape, public Sensitivity signature, or presentation behavior changed.

The architectural behavior changed only by removing incomplete calculator
construction and making shared calculation inputs explicit.

## Deliberately retained compatibility paths

- Normal calculator construction in `compare_horizon_cases`.
- Defensive Sensitivity configuration views that have active references.
- Sensitivity's existing result-oriented trace and presentation methods.
- Historical reports documenting prior implementation states.

No uncertain executable transitional compatibility path remains.
