# Module 1 `summarize_stance_logic` Deletion Audit

## Conclusion

Recommended decision: **delete in a follow-up implementation PR**.

Within the tracked repository, `summarize_stance_logic(...)` has no live callers outside its own definition. Its private helpers are only reached through that wrapper, and `_curve_value_counts_with_ratio(...)` is only used by the curve helper. The old credit/curve summary tables are convenience groupings over data already exposed by newer diagnostics, especially `trace_stance_score(...)` and `diagnose_rule_mapped_stance(...)`.

External compatibility risk is possible because `summarize_stance_logic(...)` is a public method name, but it does not appear documented or used in tracked docs, notebooks, examples, tests, or production paths. In this project context, deletion appears safer than adding new duration support to a redundant wrapper.

## Reference Map

### `summarize_stance_logic`

| reference | classification | note |
| --- | --- | --- |
| `module1.py:7436` | definition | Public wrapper. |
| `reports/260629_module1_target_bucket_accessors_audit.md:168` | stale report reference | Suggested a historical smoke check. |
| `reports/260701_module1_stance_summary_api_audit.md` | report reference | Prior audit discussion and recommendation. |

No tracked production path, notebook, example, docs page, or test calls this method.

### `_summarize_credit_stance_logic`

| reference | classification | note |
| --- | --- | --- |
| `module1.py:7457` | internal call | Called only by `summarize_stance_logic("credit")`. |
| `module1.py:7473` | definition | Private helper. |
| `reports/260630_module1_remaining_cleanup_reclassification_audit.md:145` | stale report reference | Historical cleanup classification. |
| `reports/260701_module1_stance_summary_api_audit.md:23` | report reference | Prior audit output map. |

No external/repository caller exists.

### `_summarize_curve_positioning_stance_logic`

| reference | classification | note |
| --- | --- | --- |
| `module1.py:7464` | internal call | Called only by `summarize_stance_logic("curve_positioning")`. |
| `module1.py:7872` | definition | Private helper. |
| `reports/260629_module1_target_bucket_accessors_audit.md` | stale report reference | Historical cleanup notes. |
| `reports/260630_module1_remaining_cleanup_reclassification_audit.md:146` | stale report reference | Historical cleanup classification. |
| `reports/260701_module1_stance_summary_api_audit.md:30` | report reference | Prior audit output map. |

No external/repository caller exists.

### `_curve_value_counts_with_ratio`

| reference | classification | note |
| --- | --- | --- |
| `module1.py:7861` | definition | Private helper. |
| `module1.py:7896`, `7915`, `7919`, `7923`, `7927`, `7931` | internal calls | Used only inside `_summarize_curve_positioning_stance_logic(...)`. |
| `reports/260630_module1_remaining_cleanup_reclassification_audit.md` | stale report reference | Historical cleanup notes. |
| `reports/260701_module1_stance_summary_api_audit.md` | report reference | Prior audit discussion. |

No remaining live reference would exist if the curve summary helper is deleted.

## Unique-Output Check

### Credit

Old output:

- `state_pair_distribution`;
- `mean_score_by_state_pair`;
- `stance_label_distribution`;
- `stance_strength_distribution`.

These are not unique data products. They can be recovered from `trace_stance_score("credit", include_raw_input=False, include_labels=False)` or `diagnose_rule_mapped_stance("credit")` with simple `value_counts()` and `groupby()`.

The adjustment-related fields in `mean_score_by_state_pair` are useful convenience columns:

- `base_rule_score`;
- `rule_adjustment`;
- `credit_stance_score`;
- `credit_spread_change_intensity`;
- `credit_spread_state_intensity`.

They are still exposed by the rule-mapped diagnostic output, so deleting the wrapper removes only a prebuilt grouping, not the underlying diagnostic data.

### Curve Positioning

Old output:

- `rule_case_distribution`;
- `mean_score_by_rule_case`;
- `curve_change_bucket_distribution`;
- `curve_state_bucket_distribution`;
- `yield_move_driver_bucket_distribution`;
- `stance_label_distribution`;
- `stance_strength_distribution`.

These are also recoverable from `trace_stance_score("curve_positioning", include_raw_input=False, include_labels=False)` or `diagnose_rule_mapped_stance("curve_positioning")` using simple `value_counts()` and `groupby()`.

The ratio columns are convenient but not unique. `_curve_value_counts_with_ratio(...)` is a small formatting helper rather than a model or diagnostic data source.

## Public API Risk

`summarize_stance_logic(...)` is public by naming, but it appears to be a local diagnostic wrapper rather than a stable documented API:

- no tracked runtime code calls it;
- no tracked notebooks or examples call it;
- no active docs call it;
- no tests call it;
- duration is unsupported and falls through to `print("not implemented")`;
- newer generic diagnostics already provide broader rule-mapped coverage.

Deletion could still affect untracked external callers. If the user treats ad hoc Python methods as external API, deprecate first. Otherwise, immediate deletion is reasonable.

## Recommended Implementation Direction

If deletion is approved, remove exactly:

- `summarize_stance_logic(...)`;
- `_summarize_credit_stance_logic(...)`;
- `_summarize_curve_positioning_stance_logic(...)`;
- `_curve_value_counts_with_ratio(...)`.

Replacement guidance:

- Use `summarize_rule_mapped_stance_stability(...)` for summary-level diagnostics.
- Use `diagnose_rule_mapped_stance(...)` for row-level reconstruction/detail.
- Use `diagnose_rule_mapped_stance_transitions(...)` for transition-focused review.
- Use `trace_stance_score(...)` for full trace-style diagnostics.

Smallest safe alternative if deletion is considered too risky:

- keep `summarize_stance_logic(...)`;
- add a deprecation warning;
- do not add duration support;
- keep existing credit/curve output unchanged until a later removal window.

## Future Deletion Validation Plan

For a deletion PR, run:

- `python -m py_compile module1.py module1_schema.py`;
- `git diff --check`;
- active Module 1 config validation with issue count zero;
- production equality for component scores and exposure stances;
- smoke checks for replacement diagnostics on `duration`, `credit`, and `curve_positioning`:
  - `trace_stance_score(...)`;
  - `diagnose_rule_mapped_stance(...)`;
  - `diagnose_rule_mapped_stance_transitions(...)`;
  - `summarize_rule_mapped_stance_stability(...)`;
- repository search confirming the deleted function names remain only in old reports, if anywhere.

## Audit Validation

Report-only audit. No runtime, YAML, schema, diagnostic behavior, public method output, scoring, config semantics, or model output was changed.

Checks performed:

- exact tracked-repository searches for all four target names;
- inspected the target definitions and generic replacement diagnostics in `module1.py`;
- checked tracked docs/notebook/example paths via repository search;
- `git diff --check` was run for the report patch.
