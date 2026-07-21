# Module 1 Rule-Mapped Ownership Review

## Scope and result

This task corrected ownership of shared rule-mapped mechanics and established an
acyclic module dependency direction without changing validation, loading,
configuration interpretation, model outputs, diagnostics, or sensitivity results.

The final dependency direction is:

```text
module1_schema -> Module1Calculator
Module1Calculator.load_module1_config(validate_config=True)
    -> local import of validate_module1_config
```

`module1_calculator.py` has no module-level import from `module1_schema.py`.
`module1_schema.py` imports `Module1Calculator` and calls its authoritative static
mechanics during validation. Calculator construction imports the schema validator
only inside the validation-enabled load branch, after the calculator module is
fully initialized. Fresh-process imports pass independently and in either order.

## Import ownership audit

Before this task, `module1_calculator.py` imported four names from
`module1_schema.py`:

| Imported name | Classification | Final owner/use |
| --- | --- | --- |
| `_parse_rule_scores_n_parts()` | Calculator-owned runtime mechanic | `Module1Calculator` static method used by runtime specification construction and schema validation. |
| `_resolve_rule_mapped_stabilization_config()` | Calculator-owned runtime mechanic | `Module1Calculator` static method used by runtime construction, stabilization overrides, and schema validation. |
| `_rule_mapped_bucket_classification_from_score()` | Calculator-owned runtime mechanic | `Module1Calculator` static method used by runtime specification construction and schema validation. |
| `validate_module1_config()` | Schema-owned validation entry point | Imported locally only when configuration validation is requested. |

The three superseded schema implementations were deleted. No alias, forwarding
function, copied implementation, compatibility wrapper, or registry remains in
the schema module.

The calculator has a small static finite-number predicate required by its parsing
and stabilization mechanics. Schema retains its independent numeric validation
predicate because it is used broadly by schema-owned field policy, issue
collection, and reporting. General schema policy, cross-reference validation,
completeness checks, and report construction were not moved.

## Runtime specification terminology

`_resolve_rule_mapped_stance_schema()` was renamed to
`_resolve_rule_mapped_stance_spec()` because it constructs
`_RuleMappedStanceSpec`, a calculator-owned runtime specification.

All four live callers were updated directly:

- calculator exposure-stance calculation;
- main rule-mapped diagnostics;
- sensitivity rule-mapped diagnostic context resolution;
- sensitivity stabilization-case comparison.

No compatibility wrapper or old-name alias remains. Existing diagnostic result
field names were not renamed because those are separate consumer contracts.

## Preserved loading and validation contract

The following paths match the pre-edit baseline exactly:

- strict initialization validates before accepting configuration state;
- strict invalid reload raises before replacing the accepted configuration or its
  validation metadata;
- supported non-strict invalid loading accepts the raw configuration, emits the
  same warning, and stores the same issue report;
- `validate_config=False` accepts raw configuration and leaves validation metadata
  explicitly `None`;
- runtime calculation interprets the accepted raw configuration directly through
  calculator-owned mechanics.

The schema continues to own validation decisions and structured issue/report
construction. It calls calculator mechanics only for shared parsing,
classification, and stabilization behavior, translating their `ValueError`
messages into the same structured issues as before. Calculator execution does not
consume a schema-produced runtime or validated-config object.

## Pre-edit characterization and validation

A temporary baseline was captured before editing from the current session branch
using canonical `data/module1_config.yaml` and checked-in local data. Construction
used the non-secret value `FRED_API_KEY=offline_dummy`; no FRED download or network
request was made.

The baseline and post-edit checks covered:

- exact canonical validation report;
- exact representative invalid reports for malformed rule-score keys, mixed bucket
  styles, invalid stabilization values, and an unsupported stance function;
- eight valid parsing/classification/stabilization outcomes;
- 22 invalid parsing and stabilization exception types and messages;
- strict, non-strict, and explicitly unvalidated loading state;
- canonical features, component scores, component labels, stance scores, and
  exposure stance;
- state and trace diagnostics for Duration, Credit, and Curve Positioning;
- Credit and Curve input-smoothing sensitivity results and Curve stabilization
  comparison results;
- schema and runtime acceptance/rejection for the existing top-level stance
  function whitelist.

All DataFrame and Series comparisons were exact, including indexes, column order,
values, practical dtypes, names, and missing-value masks.

## Validation results

- Python compilation passed for all modified files and direct import consumers.
- Fresh-process imports passed for calculator alone, schema alone, calculator then
  schema, and schema then calculator.
- Five canonical/invalid validation report groups matched exactly.
- Eight valid relocated-helper results and 22 invalid-helper exceptions matched
  exactly.
- All five canonical model output layers matched exactly.
- Six primary rule-mapped diagnostic tables matched exactly.
- Three affected sensitivity output groups matched exactly.
- Strict initialization and all reload modes matched exactly.
- The schema whitelist comparison matched for six supported/unsupported candidates;
  runtime dispatch matched for four supported functions and one unsupported
  function.
- Searches found no schema-side definition, duplicate implementation, old resolver
  alias, compatibility wrapper, or module-level calculator import from schema.
- YAML, data, analysis, historical analysis, and documentation files were
  unchanged.

## Behavior impact

No accepted configuration changed. Validation reports and error behavior are
unchanged. Model outputs, rule-mapped diagnostics, sensitivity outputs,
configuration order, and the supported top-level stance function whitelist are
unchanged.
