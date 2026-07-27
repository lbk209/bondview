# Module 1 credit stabilization mapping review

## Scope and decision

This Task 9 review audited the obsolete outer
`exposure_stances.credit.state_stabilization` mapping before removing it.
The supported configuration and execution contract is
`exposure_stances.credit.rule_mapped.state_stabilization`.

No active supported consumer of the outer mapping was found. The outer mapping
was therefore removed, and the existing `credit_rule_state_stabilization` YAML
anchor was relocated to the authoritative nested mapping. The configured
component order and values remain:

1. `credit_spread_change`: `hysteresis_buffer: 0.0`,
   `min_state_persistence: 1`
2. `credit_spread_state`: `hysteresis_buffer: 0.0`,
   `min_state_persistence: 1`

## Consumer audit

The repository-wide audit classified every current reference as follows:

- `data/module1_config.yaml` previously declared the mapping at the outer
  credit level and aliased it from `rule_mapped.state_stabilization`. The
  anchor now lives directly on the nested authoritative mapping, and the outer
  key is absent.
- `Module1Calculator.resolve_rule_mapped_stance_spec` selects the credit
  `rule_mapped` configuration and passes that nested mapping to
  `resolve_rule_mapped_stabilization_config`. Normal credit stance execution
  therefore never reads the outer mapping.
- `module1_schema.validate_module1_config` validates
  `rule_mapped.state_stabilization` and passes the nested mapping to the same
  Calculator resolver. It does not read or require the outer mapping.
- `Module1Diagnostics` consumes the Calculator-resolved rule-mapped stance
  specification and has no outer-path access.
- The Calculator, `Module1Result`, Analysis, Historical Analysis, Diagnostics,
  and Sensitivity configuration snapshots carry or copy the complete parsed
  configuration. Removal is therefore observable as configuration structure,
  but none of those snapshot owners resolves credit stabilization from the
  outer path.
- `Module1SensitivityDiagnostics.compare_credit_stance_persistence_cases`
  already applies each case to the nested mapping. Its conditional
  compatibility synchronization to the outer mapping was the only active
  Python reference to the obsolete location and has been removed.
- The focused Sensitivity test previously asserted equality between the nested
  and outer scenario mappings solely to protect that compatibility behavior.
  It now asserts that case-local configurations contain only the nested
  mapping.
- Current notebooks and documentation contain no consumer of the outer credit
  path. Historical reports that accurately record earlier implementation
  states were intentionally left unchanged.

The generic `resolve_rule_mapped_stabilization_config` method still accepts a
mapping whose immediate `state_stabilization` key is resolved. This is its
purposeful rule-mapped interface and is not an outer credit configuration
consumer. Other duration, curve, score, bucket, and adjustment YAML aliases
are outside this task and remain unchanged.

## Configuration and identity impact

The YAML anchor `&credit_rule_state_stabilization` is now declared at:

`exposure_stances.credit.rule_mapped.state_stabilization`

Before removal, PyYAML materialized the outer and nested credit mappings as the
same Python object because the nested value was an alias. That cross-path
object identity no longer exists because there is only one supported path.
Object identity created by YAML anchors is not treated as a public contract;
tests assert semantic values and supported paths rather than `is` identity.

The other legitimate credit aliases remain semantically covered:

- outer `state_buckets` to each nested state input's `state_buckets`;
- outer `rule_scores` to nested `rule_mapped.rule_scores`;
- outer `rule_adjustments` to nested `rule_mapped.adjustment.config`.

## Behavior impact

This is an intentional configuration-structure change only. Resolved credit
stabilization values, Calculator behavior, Diagnostics traces, Sensitivity
case behavior, output structures, and established fingerprints are expected
to remain unchanged. No scoring, labeling, hysteresis, persistence, schema,
or diagnostic logic changed.

## Validation

All available checks passed:

- `python -m py_compile module1_sensitivity_diagnostics.py
  tests/test_module1_config_snapshot.py
  tests/test_module1_sensitivity_diagnostics.py`
- YAML load plus explicit assertions that the outer key is absent, the nested
  values and order are unchanged, schema validation has zero issues, and
  Calculator stance-spec resolution returns the same values
- four focused contract checks covering the new configuration contract, the
  representative Calculator output, and custom/default credit-persistence
  behavior: 4 passed
- focused Sensitivity suite:
  `poetry run python -m unittest tests.test_module1_sensitivity_diagnostics`:
  24 passed
- configuration-boundary suite:
  `poetry run python -m unittest tests.test_module1_config_snapshot`:
  26 passed
- full available suite:
  `poetry run python -m unittest discover -s tests`: 50 passed
- `git diff --check`

There were no unavailable checks or external-service limitations. The test
fixtures and cached project inputs required no live network access.
