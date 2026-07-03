# Module 1 Rule-Mapped Stability Summary API Overlap Audit

## Short Conclusion

Classification: `partial_overlap_found`.

No existing public API was found that already provides key-selected rule-mapped
stability summary tables equivalent to
`summarize_rule_mapped_stance_stability(...)`.

The closest overlaps are:

- `diagnose_rule_mapped_stance(...)`: exposes the row-level data from which all
  four summary tables can be reconstructed, but it does not return summary
  tables and does not accept a summary/table selector.
- Private helpers `_rule_mapped_component_state_summary(...)` and
  `_rule_mapped_score_distribution(...)`: produce two of the four table shapes,
  but are private internals and do not provide a public selected-output API.
- `review_historical_cases(output=...)` and `compare_horizon_cases(output=...)`:
  demonstrate the preferred one-selected-output style, but apply to historical
  review diagnostics rather than rule-mapped stability summaries.
- `compare_curve_positioning_stabilization_cases(...)`: returns adjacent
  curve-only stabilization comparison tables, including `score_distribution`,
  but it is scenario-comparison output and is not a replacement for generic
  duration/credit/curve rule-mapped stability summaries.

A future redesign of `summarize_rule_mapped_stance_stability(...)` toward a
key-selected API would not duplicate an existing replacement API. The narrow
next action is to proceed with a small API extension or redesign if the desired
public contract is to return one selected summary table at a time. Preserve the
current dict-returning behavior unless a deprecation or compatibility plan is
explicitly approved.

## Search Scope And Commands

Searched files and directories:

- `module1.py`
- `module1_schema.py`
- `data/module1_config.yaml`
- `data/historical_context.yaml`
- tracked YAML files from `rg --files -g '*.yaml' -g '*.yml'`
- `docs/`
- `reports/`

Commands and search methods used:

```bash
rg -n "component_state_summary|rule_case_summary|mapped_score_distribution|score_summary" module1.py module1_schema.py data reports docs --glob '*.py' --glob '*.yaml' --glob '*.yml' --glob '*.md'
rg -n "rule_mapped|stability|summary|distribution|transition_count|stabilization_changed|mapped_score|score_distribution|stance_share|strength_share" module1.py module1_schema.py data reports docs --glob '*.py' --glob '*.yaml' --glob '*.yml' --glob '*.md'
rg -n "\b(output|summary|section|table|kind|mode|return_type|as_dict|selected|view)\s*=|include_[A-Za-z0-9_]+" module1.py module1_schema.py data reports docs --glob '*.py' --glob '*.yaml' --glob '*.yml' --glob '*.md'
rg -n "def .*rule.*mapped|def .*stability|def .*summary|def .*distribution|def .*transition|def .*stance" module1.py
rg -n "^    def [A-Za-z_].*\(" module1.py
rg --files -g '*.yaml' -g '*.yml'
rg -n "summarize_rule_mapped_stance_stability|diagnose_rule_mapped_stance|diagnose_rule_mapped_stance_transitions|compare_curve_positioning_stabilization_cases|review_historical_cases\(|output=|include_detail|include_diagnostics|score_distribution|bucket_transition_summary|component_state_summary|mapped_score_distribution" reports docs --glob '*.md'
rg -n "component_state_summary|rule_case_summary|mapped_score_distribution|score_summary|score_distribution|bucket_transition_summary|stabilization_changed|transition_count|mapped_score|stance_share|strength_share" $(rg --files -g '*.yaml' -g '*.yml')
rg -n "\b(output|summary|section|table|kind|mode|return_type|as_dict|selected|view)\s*[:=]|include_[A-Za-z0-9_]+" $(rg --files -g '*.yaml' -g '*.yml') module1_schema.py
```

Limitations:

- This was a static audit plus direct implementation inspection. No runtime
  equality check was required by the task.
- Report-only mentions were used only to identify prior guidance and known
  public-vocabulary concerns; they were not treated as active API usage.

## Existing API Candidates

| method/function name | location | purpose | return type | selector argument, if any | overlap with `summarize_rule_mapped_stance_stability()` | replacement potential | notes |
|---|---:|---|---|---|---|---|---|
| `summarize_rule_mapped_stance_stability(...)` | `module1.py:7261` | Generic rule-mapped stability summary for schema-backed targets. | `dict` of four `DataFrame` tables | None | Produces all four target summary keys directly. | Current API under review, not a replacement. | Covers `duration`, `credit`, and `curve_positioning` through the rule-mapped diagnostic spec. |
| `_rule_mapped_component_state_summary(...)` | `module1.py:7180` | Builds per-component raw/stabilized transition and stabilization-change summary. | `DataFrame` | None | Produces the `component_state_summary` table body. | Low as a public replacement because it is private and requires diagnostics/spec inputs. | Useful implementation piece for a future selected-output API. |
| `_rule_mapped_score_distribution(...)` | `module1.py:7246` | Builds final mapped score counts and shares. | `DataFrame` | None | Produces the `mapped_score_distribution` table body. | Low as a public replacement because it is private and requires diagnostics/spec inputs. | Useful implementation piece for a future selected-output API. |
| `_series_value_shares(...)` | `module1.py:7237` | Builds value-share fields for stance and strength labels. | `dict` | None | Contributes to `score_summary` stance/strength share fields. | None by itself. | Private helper, not table-level output. |
| `diagnose_rule_mapped_stance(...)` | `module1.py:7073` | Row-level rule-mapped diagnostic view: score inputs, raw states, stabilized states, rule case, score, labels. | `DataFrame` | `include_scores`, `include_raw_states`, `include_stabilized_states`, `include_rule_case`, `include_labels` | Provides the source rows used by all four summary tables. | Partial underlying-data overlap only. | Does not return summary tables and does not select among `component_state_summary`, `rule_case_summary`, `mapped_score_distribution`, or `score_summary`. |
| `diagnose_rule_mapped_stance_transitions(...)` | `module1.py:7118` | Transition-focused row-level view with previous rule case/score and change flags. | `DataFrame` | None | Adjacent transition information overlaps conceptually with transition counts in summary tables. | Not a replacement. | It is row-level transition output, not summary tables. |
| `trace_stance_score(...)` | `module1.py:7375` | Generic stance trace dispatcher for weighted and rule-mapped stances. | `DataFrame` | `include_raw_input`, `include_labels` | For rule-mapped targets, exposes detailed stance trace data that can be summarized manually. | Partial underlying-data overlap only. | It is broader tracing, not a stability-summary API. |
| `review_historical_cases(...)` | `module1.py:4761` | Historical review output selector. | One selected `DataFrame` | `output` | Provides a selector-style API pattern. | Not a rule-mapped stability replacement. | Outputs historical review tables such as `cases`, `diagnostic`, `windows`, `label_distribution`, and `strength_distribution`. |
| `compare_horizon_cases(...)` | `module1.py:431` | Batch horizon comparison around historical review outputs. | One selected flat `DataFrame` | `output` | Provides a selector-style API pattern. | Not a rule-mapped stability replacement. | Uses `review_historical_cases(output=...)`; not tied to rule-mapped stability summaries. |
| `compare_credit_input_smoothing_effect(...)` | `module1.py:7626` | Credit raw-vs-smoothed input comparison. | `dict` of `DataFrame` tables | `include_detail` | Adjacent summary/detail dict pattern; not rule-mapped stability. | Not a replacement. | Credit-only comparison diagnostic. |
| `compare_curve_input_smoothing_effect(...)` | `module1.py:8035` | Curve raw-vs-smoothed input comparison. | `dict` of `DataFrame` tables | `include_detail` | Adjacent summary/detail dict pattern; not rule-mapped stability. | Not a replacement. | Curve-only comparison diagnostic. |
| `compare_curve_positioning_stabilization_cases(...)` | `module1.py:8609` | Curve-only comparison across temporary stabilization cases. | `dict` of `DataFrame` tables and detail dicts | `include_diagnostics` | Produces adjacent `bucket_transition_summary` and `score_distribution` tables for case comparisons. | Low/none for the reviewed API. | Curve-only, case-comparison-oriented, different table keys and semantics. |

## Summary-Key Coverage Matrix

| summary key | produced by `summarize_rule_mapped_stance_stability()` | produced by any other method? | selectable individually by any existing method? | notes |
|---|---|---|---|---|
| `component_state_summary` | Yes, returned in the dict at `module1.py:7344`. | Only by private `_rule_mapped_component_state_summary(...)`. | No. | No public method returns this table alone. Prior reports identify public vocabulary sensitivity for the `component` value, especially `yield_move_driver` for curve positioning. |
| `rule_case_summary` | Yes, returned in the dict at `module1.py:7348`. | No separate method found. | No. | It is assembled inline inside `summarize_rule_mapped_stance_stability(...)` from `diagnose_rule_mapped_stance(...)` rows. |
| `mapped_score_distribution` | Yes, returned in the dict at `module1.py:7349`. | Only by private `_rule_mapped_score_distribution(...)`. | No. | `compare_curve_positioning_stabilization_cases(...)` has a different `score_distribution` table for raw/stabilized curve scenario cases, not this generic mapped-score distribution. |
| `score_summary` | Yes, returned in the dict at `module1.py:7353`. | No separate method found. | No. | It is assembled inline, including generic stance/strength share fields and duration-specific positive/neutral/negative share fields. |

## False Positives / Adjacent Methods

`diagnose_rule_mapped_stance(...)` is the most important adjacent method, but it
is not a replacement. It returns the row-level diagnostic frame used by
`summarize_rule_mapped_stance_stability(...)`, and its `include_*` flags select
column groups. It does not compute or return any of the four summary tables.

`diagnose_rule_mapped_stance_transitions(...)` is also adjacent but not a
replacement. It converts row-level rule-mapped diagnostics into a transition
review frame with previous rule case, previous score, score change, and
stabilization movement columns. That overlaps conceptually with transition
counts, but it does not return summary tables or support selecting the reviewed
summary keys.

`trace_stance_score(...)` can expose detailed rule-mapped trace data for
duration, credit, and curve positioning, but it is a broad trace dispatcher. It
does not calculate the stability-summary table shapes.

`review_historical_cases(output=...)` and `compare_horizon_cases(output=...)`
are true selector-style APIs, but their output domain is historical review, not
rule-mapped stance stability. They are design precedents, not replacements.

`compare_credit_input_smoothing_effect(...)`,
`compare_curve_input_smoothing_effect(...)`,
`compare_curve_move_driver_threshold_effect(...)`, and
`compare_curve_positioning_stabilization_cases(...)` return dicts with summary,
detail, window, and distribution tables. These are comparison diagnostics with
different semantics and, except for credit/curve-specific comparison coverage,
do not cover all rule-mapped targets. The curve stabilization case method's
`score_distribution` is specifically case- and score-type-qualified, not the
generic `mapped_score_distribution` table from the reviewed API.

Report-only mentions in prior audits document existing public-vocabulary
concerns and recommended retention/cleanup sequencing. They do not indicate an
active replacement API. Notable report-only guidance includes:

- `reports/260701_module1_stance_summary_api_audit.md`: documents the three
  public rule-mapped diagnostic methods and the current summary output keys.
- `reports/260701_module1_group_k3_remaining_alias_decision.md`: identifies the
  public `component_state_summary["component"]` vocabulary impact for curve
  positioning.
- `reports/260703_module1_stage2_diagnostic_duplication_audit.md`: classifies
  `summarize_rule_mapped_stance_stability(...)` as mostly derivable from
  `diagnose_rule_mapped_stance(...)`, but preserving useful public summary
  shapes and vocabulary.
- `reports/260630_module1_group_h_summary_display_audit.md` and
  `reports/260630_module1_group_g_stabilization_case_audit.md`: document
  adjacent comparison diagnostic result keys such as `summary`,
  `bucket_transition_summary`, and `score_distribution`, but not as replacements
  for generic rule-mapped stability summaries.

## Classification

`partial_overlap_found`

Existing APIs and helpers provide:

- the underlying row-level rule-mapped diagnostic data;
- two private helper-generated summary table bodies;
- selector-style API precedent in historical review diagnostics;
- adjacent curve-only stabilization comparison summaries.

Existing APIs do not provide:

- a public key-selected rule-mapped stability-summary API;
- a public method that returns `component_state_summary` alone;
- a public method that returns `rule_case_summary` alone;
- a public method that returns `mapped_score_distribution` alone;
- a public method that returns `score_summary` alone;
- a replacement that covers all three schema-backed rule-mapped targets while
  using the same `RuleMappedDiagnosticSpec`.

## Recommendation

A future redesign can proceed because no equivalent key-selected API exists.

The lowest-risk direction is a small API extension around the existing
`summarize_rule_mapped_stance_stability(...)` implementation, using the current
diagnostic spec and preserving the four existing table builders and table
vocabulary. If compatibility matters, keep the current dict-returning default
and add a selector argument such as `output`, `summary`, `section`, or `table`
only as an additive path. Do not infer that `diagnose_rule_mapped_stance(...)`
alone is a public replacement, because it requires callers to reimplement table
derivations and duration-specific share fields.

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
