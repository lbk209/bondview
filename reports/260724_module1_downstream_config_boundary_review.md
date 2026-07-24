# Module 1 downstream configuration boundary review

## Scope and conclusion

The repository-wide audit covered Module 1 YAML access, raw configuration
validation, calculator construction, calculator-state synchronization, result
configuration resolution, and downstream error guidance.

`Module1Analysis`, `Module1Diagnostics`, and `Module1HistoricalAnalysis` already
observed the intended production boundary:

- result-specific configuration comes from `Module1Result.module1_config`;
- none loads or validates `data/module1_config.yaml`;
- none constructs an initialized, partial, synthetic, or synchronized
  `Module1Calculator`;
- Diagnostics delegates preparation and stance-breakdown calculations to the
  established stateless calculator capabilities;
- consumer-owned resolution, selection, trace ordering, historical context,
  formatting, and presentation remain in their existing modules.

No production configuration-source migration was required. The confirmed defect
was misleading result-consumer errors that instructed callers to run calculator
loading or execution methods.

## Occurrence classification

### Valid configuration owners

- `module1_calculator.py` owns the `data/module1_config.yaml` path, YAML loading,
  calculator construction, normal pipeline execution, and the schema-validation
  boundary.
- `module1_schema.py` owns raw Module 1 configuration validation.

### Analysis

- Imports `Module1Result`, not `Module1Calculator`.
- Reads configuration only through `result.module1_config`.
- Returns defensive copies of resolved feature, component, and stance
  configuration.
- Performs no YAML loading, raw validation, calculator construction, or state
  synchronization.

### Diagnostics

- Derives defensive local feature, component, and exposure-stance views from
  `result.module1_config`.
- Calls only the deliberate stateless calculator capabilities needed for input
  preparation, weighted breakdowns, rule-mapped specification resolution, and
  rule-mapped breakdowns.
- Performs no YAML loading, raw validation, calculator construction, or state
  synchronization.

### Historical Analysis

- Derives defensive local component and exposure-stance views from
  `result.module1_config`.
- Its YAML loader is used only for `historical_context.yaml`, which is a valid
  consumer-owned path.
- In-memory historical context and result inspection do not load Module 1 YAML.
- Performs no raw Module 1 validation, calculator construction, or state
  synchronization.

### Sensitivity and tests

- Sensitivity constructs normal calculators for new counterfactual executions;
  those are valid new calculations.
- Sensitivity's synthetic calculator shell and its state synchronization remain
  deferred as explicitly required.
- Existing integration tests intentionally load the production Module 1 YAML and
  execute a normal calculator pipeline; those remain complementary integration
  coverage.

## Production correction

Downstream errors in Analysis, Diagnostics, and Historical Analysis now identify
the missing `Module1Result` table or `module1_config` snapshot. They no longer
instruct result consumers to call calculator loading or execution methods.

Historical context documentation now identifies the completed result's
configuration snapshot as the label-vocabulary source.

No financial calculations, configuration interpretation, schemas, result
structure, output columns, ordering, diagnostics, or historical selection logic
changed.

## Practical constructed-result invariants

The downstream paths exercised by the focused tests require:

- `module1_config` for feature, component, stance, alias/group, dependency,
  diagnostic, and historical label operations;
- the requested result table to be present;
- configuration-declared component score and label columns to exist;
- configuration-declared stance score, label, and strength columns to exist;
- aligned indexes when fixture tables are combined for downstream inspection;
- consumer-returned or consumer-retained configuration to be isolated from the
  authoritative result snapshot.

Missing tables, configuration, or configured columns are tested through
deliberate `ValueError` paths rather than calculator reload guidance or incidental
`KeyError` and `AttributeError` failures.

## Constructed-result support

`build_constructed_module1_result` is defined in
`tests/test_module1_config_snapshot.py`, the repository's existing test-support
location. It creates fresh, aligned DataFrames and a minimal coherent
configuration for each call, accepts focused `Module1Result` field overrides,
and delegates weighted and rule-mapped fixture calculations to the production
stateless capabilities.

It performs no file access, environment lookup, network access, or calculator
initialization.

## Validation

- Five constructed-result tests pass.
- Sixteen existing snapshot, shared-capability, and real-pipeline tests pass.
- The complete 21-test suite passes.
- Exact baseline/current signatures match for features, scores, labels, stance
  scores, exposure stances, prepared inputs, a weighted trace, every configured
  rule-mapped trace, all state/transition/stability views, representative
  Analysis context, and representative Historical context.
- Modified and directly related Python modules compile.
- Calculator-first, schema-first, and independent downstream imports pass.
- An independent full calculator pipeline passes.
- `git diff --check` passes.

## Deferred work

- Sensitivity's synthetic calculator shell and state synchronization.
- Broader Sensitivity result/configuration compatibility cleanup.
- Any transitional compatibility work outside Analysis, Diagnostics, and
  Historical Analysis.
