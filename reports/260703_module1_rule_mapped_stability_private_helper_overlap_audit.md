# Module 1 Rule-Mapped Stability Private Helper Overlap Audit

## Short Conclusion

The private helpers behind `summarize_rule_mapped_stance_stability(...)` are not
covered by a broader internal replacement that can preserve the current output
values, table shapes, NaN behavior, ordering, and target-specific vocabulary.

Final helper classifications:

| helper | overlap classification | short conclusion |
|---|---|---|
| `_rule_mapped_component_state_summary(...)` | `unique` | Rule-mapped-specific table builder; preserve or wrap it in a redesign. |
| `_rule_mapped_score_distribution(...)` | `partial_overlap` | Similar value-count distribution code exists, but output contract and spec coupling differ. |
| `_series_value_shares(...)` | `partial_overlap` | Generic-shaped value-share logic overlaps with distribution helpers, but no helper returns the same prefixed dict fields. |
| `_count_series_changes(...)` | `unique` | No duplicate helper found; it is already the shared generic transition-count utility used outside rule-mapped stability summaries. |

A future redesign should preserve the rule-mapped table builders or wrap them
behind a selected-output public path. Internal consolidation is only plausible
around low-level value-count/share formatting, and only after equality checks
protect column names, ordering, `pd.NA` behavior, and duration-specific share
fields. No helper is safely replaceable by an existing broader helper today.

## Search Scope And Commands

Searched files and directories:

- `module1.py`
- `module1_schema.py`
- all tracked Python files from `rg --files -g '*.py'`
- `docs/`
- `reports/`
- YAML mentions only where helper vocabulary or prior guidance could matter

Commands and search methods used:

```bash
rg -n "_rule_mapped_component_state_summary|_rule_mapped_score_distribution|_series_value_shares|_count_series_changes" --glob '*.py' --glob '*.md' --glob '*.yaml' --glob '*.yml'
rg -n "value_counts|transition_count|state_transition|score_distribution|distribution|share|ratio|summary|most_frequent|mode\(\)|nunique|std\(|mean\(|median\(|dropna|stabilization_changed|bucket_transition_summary|label_distribution|strength_distribution" module1.py module1_schema.py --glob '*.py'
rg -n "def .*summary|def .*distribution|def .*count|def .*ratio|def .*dominant|def .*change|def .*value|def .*window" module1.py module1_schema.py
rg -n "_rule_mapped_component_state_summary|_rule_mapped_score_distribution|_series_value_shares|_count_series_changes|value_counts|score_distribution|bucket_transition_summary|label_distribution|strength_distribution|most_frequent|transition_count" reports docs --glob '*.md'
rg --files -g '*.py'
rg -n "def .*value|def .*distribution|def .*summary|def .*count|def .*ratio|value_counts\(|mode\(\)|nunique\(|_count_series_changes|_series_value_shares|score_distribution|transition_count" $(rg --files -g '*.py')
git grep -n "_curve_value_counts_with_ratio\|summarize_stance_logic" -- .
```

Limitations:

- This was a static audit with direct implementation inspection. No runtime
  equality check was required by the task.
- Prior reports were used as guidance only. Old report-only mentions of deleted
  helpers such as `_curve_value_counts_with_ratio(...)` were not treated as
  active implementation.

## Helper Usage Matrix

| helper | definition location | call sites | used only by `summarize_rule_mapped_stance_stability(...)`? | active outside rule-mapped stability summary? | notes |
|---|---:|---|---|---|---|
| `_rule_mapped_component_state_summary(...)` | `module1.py:7180` | `module1.py:7344` | Yes | No | Builds the `component_state_summary` table from `diagnostics` plus `RuleMappedDiagnosticSpec`. Its `component` values use `spec.component_names`, including public vocabulary such as curve `yield_move_driver`. |
| `_rule_mapped_score_distribution(...)` | `module1.py:7246` | `module1.py:7349` | Yes | No | Builds the `mapped_score_distribution` table from `spec.final_score_col`, with final score column name, `count`, and `share`. |
| `_series_value_shares(...)` | `module1.py:7237` | `module1.py:7315`, `module1.py:7316` | Yes | No | Produces flattened dict fields such as `stance_<value>_share` and `strength_<value>_share` for `score_summary`. |
| `_count_series_changes(...)` | `module1.py:7762` | `module1.py:7216`, `module1.py:7219`, `module1.py:7291`, `module1.py:7569`, `module1.py:7572`, `module1.py:7969`, `module1.py:7972`, `module1.py:8494`, `module1.py:8497`, `module1.py:8505`, `module1.py:8513`, `module1.py:8597`, `module1.py:8598`, `module1.py:8646`, `module1.py:8647` | No | Yes | Shared by rule-mapped stability, credit/curve input-smoothing summaries, and curve stabilization comparison summaries. |

## Similar-Helper Candidates

| candidate method/function | location | purpose | similarity | key semantic differences | replacement potential |
|---|---:|---|---|---|---|
| `_build_historical_review_distributions(...)` | `module1.py:4535` | Builds `label_distribution` and `strength_distribution` tables grouped by historical case metadata. | Uses `dropna()` and `value_counts()` to create count/ratio distributions. | Requires historical review detail columns and group keys; outputs `value`, `count`, `ratio` plus case metadata; not spec-driven; does not produce prefixed share dict fields or mapped-score column names. | Low; not a drop-in replacement for `_series_value_shares(...)` or `_rule_mapped_score_distribution(...)`. |
| `_label_distributions(...)` | `module1.py:4905` | Returns value-count `Series` by table column for result inspection. | Uses `dropna().value_counts()`. | Returns a dict of `Series`; no ratios/shares; no stable DataFrame table shape; no rule-mapped spec vocabulary. | None for stability summary output preservation. |
| `_evaluate_historical_case(...)` summary assembly | `module1.py:4098` | Builds one historical case summary with label modes and score stats. | Uses `mode()`, `mean()`, `median()`, min/max, valid counts, and match ratios. | Historical validation semantics, expected-label matching, no transition counts, no rule-case distribution, no `RuleMappedDiagnosticSpec`, no duration-specific stance shares. | None. |
| `_credit_input_smoothing_summary_row(...)` | `module1.py:7543` | Builds credit raw-vs-smoothed input-preparation comparison metrics. | Uses `_count_series_changes(...)`, ratios, valid counts, and summary-row dict output. | Compares paired raw/smoothed score columns; target-specific column names; not state summary or mapped-score distribution. | None for table builders; confirms `_count_series_changes(...)` is shared. |
| `_curve_input_smoothing_summary_row(...)` | `module1.py:7943` | Builds curve raw-vs-smoothed input-preparation comparison metrics. | Uses `_count_series_changes(...)`, ratios, valid counts, and summary-row dict output. | Compares paired raw/smoothed score columns; curve-specific metrics; no rule-mapped component table or final-score distribution. | None for table builders; confirms `_count_series_changes(...)` is shared. |
| `_curve_stabilization_summary_row(...)` | `module1.py:8484` | Builds curve stabilization case summary rows. | Uses `_count_series_changes(...)`, `_curve_dominant_value(...)`, ratios, means, and change counts. | Curve-only scenario-comparison summary; raw/stabilized comparison vocabulary; no generic duration/credit/curve spec coverage. | Low; not equivalent to `_rule_mapped_component_state_summary(...)`. |
| `_curve_stabilization_window_row(...)` | `module1.py:8568` | Builds window-level curve stabilization case metrics. | Uses `_count_series_changes(...)` and dominant-value summaries. | Window-specific and curve-only; no component state summary table shape; no mapped score distribution. | None. |
| score-distribution loop in `compare_curve_positioning_stabilization_cases(...)` | `module1.py:8661` | Builds curve case score distribution rows. | Uses `dropna().value_counts().sort_index()` like `_rule_mapped_score_distribution(...)`. | Adds `case_id`, `score_type`, `score`, `ratio`; only raw/stabilized curve scenario scores; does not use `spec.final_score_col`; ratio column name differs from `share`. | Partial overlap only; not a safe replacement. |
| bucket-transition loop in `compare_curve_positioning_stabilization_cases(...)` | `module1.py:8641` | Builds curve bucket transition reduction table. | Uses `_count_series_changes(...)` for raw/stabilized bucket columns. | Curve-only case-comparison output; columns are `raw_change_count`, `stabilized_change_count`, reduction count/ratio, not rule-mapped component state summary columns. | None for component summary replacement. |
| `_curve_dominant_value(...)` | `module1.py:7756` | Returns the modal non-null value or `pd.NA`. | Similar to most-frequent fields in `_rule_mapped_component_state_summary(...)` and rule-case summary. | Returns only value, no ratio, count, component row, or spec-driven columns. Name and current usage are curve-oriented. | Low; could be a tiny local reuse candidate only with equality checks, not a replacement. |
| `dominant_pair(...)` local helper | `module1.py:8810` | Returns dominant credit state pair and ratio for persistence cases. | Similar to rule-case most-frequent value/ratio. | Local nested helper; credit-specific `credit_state_pair`; no generic signature; no table-builder contract. | None. |
| `_ratio_or_na(...)` | `module1.py:7657` | Returns numerator/denominator or `pd.NA` on zero denominator. | Similar ratio/share fallback behavior. | Does not build counts, distributions, or preserve output dtypes/column names. Some existing stability code uses direct division to produce `float` shares. | Possible tiny cleanup candidate later, not a helper replacement. |
| `_window_summary_row(...)` | `module1.py:7723` | Adds window metadata around an existing summary row. | Similar summary-row dict manipulation. | Window metadata wrapper only; no distribution, transition, or state-summary semantics. | None. |

## Per-Helper Assessment

### `_rule_mapped_component_state_summary(...)`

Current purpose:

- Builds `component_state_summary` for `summarize_rule_mapped_stance_stability(...)`.
- Requires `diagnostics` plus `RuleMappedDiagnosticSpec`.
- Emits one row per rule-mapped state input with:
  - `component`
  - raw/stabilized transition counts
  - stabilization changed count/ratio
  - most frequent raw/stabilized states
  - valid raw/stabilized counts

Existing overlap:

- Shares `_count_series_changes(...)` with other diagnostics.
- Uses modal-value logic similar to `_curve_dominant_value(...)`.
- Uses ratio concepts similar to `_ratio_or_na(...)`.
- No broader helper found that builds the same table shape or preserves
  `spec.component_names` vocabulary.

Equivalence classification: `unique`.

Recommendation:

Preserve this helper or wrap it in any selected-output redesign. Do not replace
it with curve stabilization summary helpers; those are target- and
scenario-specific.

### `_rule_mapped_score_distribution(...)`

Current purpose:

- Builds `mapped_score_distribution` for `summarize_rule_mapped_stance_stability(...)`.
- Requires `diagnostics` plus `RuleMappedDiagnosticSpec`.
- Drops null final scores, sorts by score value, and returns a DataFrame whose
  first column is named after `spec.final_score_col`, followed by `count` and
  `share`.
- When no valid scores exist, the returned DataFrame has the final score column
  and `count`, then assigns `share` using `pd.NA`.

Existing overlap:

- The curve stabilization case score-distribution loop also uses
  `dropna().value_counts().sort_index()`.
- Historical review distribution builders also use value-count distribution
  patterns.

Key non-equivalence:

- Existing distribution builders use different metadata columns and names such
  as `value`, `ratio`, `score`, `score_type`, and `case_id`.
- They are not driven by `RuleMappedDiagnosticSpec`.
- They do not cover duration, credit, and curve positioning through the same
  target-agnostic contract.

Equivalence classification: `partial_overlap`.

Recommendation:

Keep the helper for now. A future redesign may factor out a tiny
value-count-with-share primitive, but only if equality checks prove the same
column names, ordering, empty-output behavior, and dtypes.

### `_series_value_shares(...)`

Current purpose:

- Produces flattened share fields for `score_summary`, using a caller-provided
  prefix and the literal observed values:
  - `stance_<value>_share`
  - `strength_<value>_share`
- Drops nulls.
- Returns an empty dict when there are no valid observations.

Existing overlap:

- `_build_historical_review_distributions(...)` and `_label_distributions(...)`
  both use `dropna().value_counts()`.
- Prior reports mention a deleted or obsolete `_curve_value_counts_with_ratio`
  helper only as report-only guidance, not active implementation.

Key non-equivalence:

- Existing active helpers return DataFrames or dicts of count `Series`, not
  flattened prefixed share fields.
- They do not preserve the exact dynamic key names currently added to
  `score_summary`.

Equivalence classification: `partial_overlap`.

Recommendation:

Keep the helper unless a future generic value-share helper is introduced with
explicit equality tests. It is generic-shaped, but no active existing helper can
replace it without changing output shape.

### `_count_series_changes(...)`

Current purpose:

- Counts transitions in a single series after dropping nulls.
- Returns `0` for an empty valid series.
- Compares each non-null value with the previous non-null value and excludes the
  first valid value from the count.

Existing overlap:

- No duplicate helper was found.
- It is already shared outside `summarize_rule_mapped_stance_stability(...)` by:
  - credit input-smoothing summary rows;
  - curve input-smoothing summary rows;
  - curve stabilization summary/window rows;
  - curve stabilization bucket-transition summaries.

Equivalence classification: `unique`.

Recommendation:

Keep it as the existing shared generic utility. Future redesign should continue
to use it rather than adding another transition-count implementation.

## Future Redesign Implication

A redesign of `summarize_rule_mapped_stance_stability(...)` should:

- expose selected outputs through the current public method or a compatible
  wrapper around the current result table builders;
- keep `_rule_mapped_component_state_summary(...)` as the authoritative builder
  for `component_state_summary`;
- keep `_rule_mapped_score_distribution(...)` unless a generic value-count
  helper is introduced with exact output-preservation checks;
- keep `_series_value_shares(...)` unless a generic prefixed-share helper is
  introduced with exact key-name and empty-series behavior checks;
- continue using `_count_series_changes(...)` as the shared transition-count
  primitive.

The audit does not support replacing the rule-mapped table builders with
historical review distributions, curve stabilization summaries, or older
report-only helper guidance. Those candidates are semantically adjacent but do
not match the rule-mapped stability summary contract closely enough.

No implementation details beyond this audit-level guidance are recommended
before a specific redesign task defines compatibility and output-selection
requirements.

## Validation

This was report-only.

Validation run:

```bash
git diff --check
```

No Python syntax check was required because no Python files were changed.

Behavior impact:

- No runtime code changed.
- No schema code changed.
- No YAML config changed.
- No diagnostics behavior changed.
- No public API behavior changed.
- No model outputs changed.
