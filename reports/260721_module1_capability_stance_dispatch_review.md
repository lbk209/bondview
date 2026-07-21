# Module 1 Capability-Driven Stance Dispatch Review

## Scope and result

This task replaced the duplicated top-level rule-mapped stance-name whitelists
with the existing nested executable capability contract.

The final dispatch contract is:

- `function == "weighted_sum"` selects weighted execution first.
- Any other non-empty top-level function identifier is resolved through the
  stance's nested `rule_mapped` configuration.
- The nested `rule_mapped.function` must remain `rule_mapped_stance`.
- Missing or blank top-level functions, absent or malformed nested configuration,
  unsupported nested functions, and invalid nested contracts remain rejected.

The canonical YAML names `duration_rule_stance`, `credit_spread_stance`, and
`curve_positioning_stance` were not changed. No replacement registry, name
mapping, helper whitelist, alias, forwarding wrapper, or compatibility delegate
was added.

## Ownership audit

Before this task, the same three top-level names controlled calculator execution,
schema acceptance, and sensitivity trace dispatch. Main diagnostics already used
the nested `rule_mapped` contract and served as the reference consumer.

The final owners are:

| Concern | Authoritative contract |
| --- | --- |
| Weighted execution | Top-level `function == "weighted_sum"` |
| Rule-mapped execution | A non-empty non-weighted top-level identifier plus a valid nested `rule_mapped` contract |
| Executable rule-mapped capability | Nested `rule_mapped.function == "rule_mapped_stance"` |
| Nested structure and invariants | Existing calculator resolver and schema validation |
| Sensitivity trace support | The same existing nested resolver used for rule-mapped execution |

`known_custom_stance_functions` and
`Module1SensitivityDiagnostics._rule_mapped_trace_supported_functions()` were
deleted. Repository searches found no live reference, alias, wrapper, or
equivalent replacement whitelist. An occurrence of the removed sensitivity
helper name remains only in a historical report.

## Adjustment capability audit

The schema's top-level `credit_spread_stance` name check was redundant with the
nested adjustment contract and was removed. Adjustment support remains identified
by the nested `rule_mapped.adjustment` structure, whose existing checks continue
to require and enforce:

- exactly two `threshold_state` inputs;
- adjustment metadata/output structure and output ownership;
- a complete state-pair cross-product;
- the Credit adjustment configuration, state-pair entries, numeric weights, and
  default/per-pair caps;
- the existing Credit intensity and adjusted-score formulas.

The calculator formula and all adjustment error handling were left unchanged.
An otherwise identical copied Credit configuration named
`spread_adjusted_rule_stance` now validates and executes, while the same copied
form with an invalid adjustment remains rejected by schema validation,
calculator execution, main diagnostics, and sensitivity tracing.

## Mixed-form characterization

A weighted stance that also contains a valid `rule_mapped` field retains its
established split behavior:

- calculator execution and main score tracing use `weighted_sum`;
- schema validation still validates the present nested field;
- main rule-mapped diagnostics can inspect that nested contract;
- sensitivity rule-mapped tracing continues to reject the weighted top-level
  function.

A weighted stance with a malformed nested `rule_mapped` field likewise retains
weighted calculator execution, schema issues for the malformed nested field,
main-diagnostic rejection of that field, and weighted sensitivity-trace
rejection. Weighted precedence was not broadened or narrowed.

## Newly accepted copied configurations

Two otherwise canonical copied configurations were exercised through strict
loading and the full pipeline:

- Duration with top-level function `macro_rule_stance`;
- adjustment-bearing Credit with top-level function
  `spread_adjusted_rule_stance`.

Both produced the canonical features, component scores, component labels, stance
scores, exposure stance, main diagnostics, and sensitivity traces exactly. This
broadened copied-configuration acceptance is the intentional contract change.

An unknown non-empty top-level function without `rule_mapped` remains rejected by
schema validation and every execution/diagnostic consumer. Missing and blank
top-level functions also remain rejected clearly.

## Pre-edit baseline and validation

A temporary pre-edit baseline was captured from the current session branch using
canonical `data/module1_config.yaml` and checked-in local data. Construction used
the non-secret value `FRED_API_KEY=non_secret_offline_dummy`; no FRED retrieval or
network request was made.

Validation covered:

- compilation of all modified modules and direct import consumers;
- fresh-process calculator/schema imports independently and in both orders;
- canonical strict loading and zero-issue schema validation;
- exact canonical features, component scores, component labels, stance scores,
  and exposure stance;
- exact main state diagnostics and trace tables for Duration, Credit, and Curve
  Positioning;
- exact affected sensitivity traces for Duration, Credit, and Curve Positioning;
- strict copied-config loading, full execution, main diagnostics, and sensitivity
  tracing for both new top-level names;
- valid and malformed weighted-plus-rule-mapped mixed forms;
- missing/blank functions, an unknown function without nested capability,
  missing/malformed nested configuration, an unsupported nested function,
  invalid source and output ownership, incomplete rule cross-products, invalid
  stabilization, invalid adjustment, and named Duration/Curve/Credit invariants;
- repository-wide removed-symbol and name-based-dispatch searches;
- unchanged YAML, data, documentation, main diagnostics, analysis, and historical
  analysis files.

Exact pandas comparisons included indexes, column order, values, practical
dtypes, names, and missing-value behavior. Unchanged malformed cases retained
their pre-edit validation reports and exception types/messages exactly. The
missing/blank top-level schema issue now describes the non-empty identifier
contract, and an unknown non-capable identifier now fails on its missing nested
capability rather than on a closed name list.

## Behavior impact

Canonical model outputs did not change. Canonical validation, configuration
order, YAML declarations, weighted behavior, rule-mapped formulas, adjustment
formulas, main diagnostics, and sensitivity results are unchanged.

The only intended behavior change is that otherwise valid copied rule-mapped
configurations may use new non-empty top-level function names because executable
support is now determined by the nested capability contract.
