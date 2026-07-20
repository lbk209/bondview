# Module 1 historical case evaluation consolidation review

## Scope and implementation

`Module1HistoricalAnalysis` now has one canonical multi-case evaluation operation:

```python
_build_historical_review_tables(cases, min_obs, plausible_threshold, mixed_threshold)
```

The helper accepts an already selected historical-case table, iterates over it once,
calls the unchanged `_evaluate_historical_case()` once per row, collects both returned
objects, and builds the canonical summary and detail tables from that single pass. The
existing summary and detail column construction, missing values, practical dtypes,
sorting, concatenation, and reset-index behavior remain unchanged.

The parallel evaluation helpers were removed without aliases or forwarding wrappers:

- `_build_historical_case_summary_table()`
- `_build_historical_detail_table()`

`review_historical_cases()` now validates the output selector first, selects cases
once, builds summary and detail once, and derives all eight outputs from those tables.
It retains the prior output-dependent no-case error context: summary, compact, report,
and diagnostic requests use `historical review cases`; detail, windows, and both
distribution requests use `historical review detail cases`.

`plot_historical_review_case()` retains its existing plot-specific selection and
uniqueness checks, then evaluates the one matching case through the canonical helper
and derives windows from its returned detail table. It no longer makes two public
review calls. An explicit expected-label override still intentionally recalculates
the displayed match states and decomposed windows after canonical model evaluation;
that display-only calculation is not a second historical-case evaluation.

No internal logic or signature of `_evaluate_historical_case()` changed. No other
production module, YAML file, data file, constructor state, target resolver,
historical-context resolver, loading path, or configuration interpreter changed.

## Selection and evaluation counts

Temporary method instrumentation was used and was not committed. A representative
`target="duration"` review selects 12 cases.

| Public review output | Case-selection calls | Selected cases | Per-case evaluation calls |
| --- | ---: | ---: | ---: |
| `cases` | 1 | 12 | 12 |
| `compact` | 1 | 12 | 12 |
| `diagnostic` | 1 | 12 | 12 |
| `detail` | 1 | 12 | 12 |
| `report` | 1 | 12 | 12 |
| `windows` | 1 | 12 | 12 |
| `label_distribution` | 1 | 12 | 12 |
| `strength_distribution` | 1 | 12 | 12 |

An unsupported output performed zero selections and zero evaluations, preserving
validation ordering. Before this change, the diagnostic request selected twice and
evaluated 24 times for the same 12 cases.

Each of four instrumented plot forms called `_select_historical_cases()` once and
evaluated the one case remaining after the existing `context_id` and uniqueness checks
once:

- target/input plot with the configured expected label;
- state-only plot with the configured expected label;
- target/input plot with an explicit expected-label override;
- state-only plot with an explicit expected-label override.

Before this change, each plot form selected three times and evaluated the same case
twice.

## Behavior-equivalence validation

A temporary pre-edit baseline was captured for all eight public review outputs and
was not committed. Exact DataFrame comparison covered values, indexes, columns and
column order, row order, dtypes, return types, and missing-value representation.

The baseline matrix covered canonical component and stance names, configured
component and stance aliases, all-level target groups, component-only and stance-only
group filtering, `context_id`, validation-only and validation-inclusive requests,
relevance-inclusive requests, a temporarily marked low-relevance case, forced
insufficient-data review thresholds, component cases without strength, and stance
cases with expected strength. All 128 pre/post output comparisons passed exactly.

Six non-interactive plot baselines also matched exactly:

- the default target/input form;
- the default state-only form;
- an explicit expected-label override;
- ratio-based display boundaries with raw target/input values, no forward fill,
  label-change markers, and score zones;
- explicit display dates with normalized target/input values and label-change markers;
- a non-overlapping state-only display window.

The comparisons covered return forms and dictionary key order, figure axes count and
size, target/input/state line data, patches and collections, context-window marking,
display limits, titles, labels, ticks, legends, normalization combinations, label
changes, score zones, and `show=False`. The non-overlap case retained the exact
`UserWarning`; the other five variants retained no warnings.

A separate pre/post check replaced `plt.show()` with an in-memory counter. With
`show=True`, both the target/input and state-only return forms invoked it exactly once
before and after the refactor.

The following pre/post exception types and messages matched exactly:

- unsupported review output;
- no selected review cases;
- invalid target;
- invalid level;
- unknown review `context_id`;
- unknown event-window `context_id`;
- no matching plot case;
- multiple matching plot cases;
- missing target-context score, label, and stance-strength columns in both review and
  plot requests.

All eight output-dependent empty-selection messages also matched their pre-edit
forms exactly.

Successful strict historical-context loading matched exactly. An in-memory invalid
expected label retained the exact strict failure, left the previously committed
historical context and case tables unchanged, and retained the exact expected-label
validation report and issue evidence.

Module 1 output hashes matched the pre-edit baseline:

- features: `80605cdddaf621aeeffdbc484e603b4855390d25911117e64098f66592b48de5`
- component scores: `e910878d5764e1e8b2bcded0c987d2df57a1c8c4aa9286ed1e9cb3755d3b462d`
- component labels: `f72608a92e961514ee0c2351664a48f298909a246014493df1b1f0bb98865922`
- stance scores: `3b11375df7cc7faab76eafa2745391b5117b711f3ba53d9a6b29232e8feee685`
- exposure stance: `dad028076ef63c860c130a17ff3073d03ca579ff32934888b2f3d79161a3e358`

## Structural and repository checks

AST and repository-wide checks confirmed:

- all eight public `Module1HistoricalAnalysis` method signatures are unchanged;
- `_evaluate_historical_case()` is AST-equivalent to the pre-edit implementation;
- both superseded helper definitions and all references are absent;
- `_build_historical_review_tables()` contains the only multi-case evaluation loop;
- the repository has one `_evaluate_historical_case()` call site;
- `review_historical_cases()` has one selection call and one canonical-table call;
- `plot_historical_review_case()` has no public review call, one canonical-table call,
  and one review-window construction call;
- no replacement wrapper or parallel evaluation path exists;
- `Module1HistoricalAnalysis.resolve_historical_event_window()` remains the sole
  historical `context_id` resolver;
- no YAML or data file changed;
- `git diff --check` passed.

Compilation and import smoke checks passed for:

- `module1_historical_analysis.py`
- `module1_analysis.py`
- `module1_calculator.py`
- `module1_diagnostics.py`
- `module1_sensitivity_diagnostics.py`
- `module1_schema.py`

The main commands were:

- Poetry-managed Python baseline and post-edit comparison scripts using
  `FRED_API_KEY=dummy MPLBACKEND=Agg poetry run python`;
- `poetry run python -m py_compile` for all six Module 1 files listed above;
- Poetry-managed imports of the same six modules;
- AST checks against
  `origin/codex/session/260720_1647:module1_historical_analysis.py`;
- repository-wide `rg` searches for the removed helpers, evaluation call sites,
  review call sites, and the historical event-window resolver;
- `git diff --name-only`, `git diff --check`, and working-tree status checks.

Validation used the Poetry-managed environment, a dummy FRED key for local-only
calculator construction, local repository data, and Matplotlib's non-interactive
`Agg` backend. No network data retrieval was performed or required.

## Behavior impact and files changed

Files changed:

- `module1_historical_analysis.py`
- `reports/260720_module1_historical_case_evaluation_review.md`

Public APIs did not change. Historical-review values, schemas, dtypes, ordering,
errors, warnings, plotting behavior, historical loading and retained validation
state, configuration interpretation, YAML/data content, and Module 1 model outputs
did not change. The only effect is removal of duplicate selection and per-case
evaluation work. There are no validation limitations or unresolved issues.
