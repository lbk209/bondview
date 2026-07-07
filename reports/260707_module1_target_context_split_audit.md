# Module 1 target/context split audit

## Executive recommendation

Do not move the public target/context methods yet. The next implementation PR
should first split historical `context_id` resolution from result-only windowed
retrieval, preferably by extracting a small helper that converts
`context_id` plus optional `start`/`end` into explicit dates. After that,
`Module1Analysis` can safely own the explicit-window target/context core.

The target/context area is mostly read-only and does not mutate runtime state.
The main blocker is ownership, not calculation behavior: `get_target_context(...)`
and `build_target_comparison_dataset(...)` are result-only when passed explicit
`start`/`end`, but they become historical-context-dependent when `context_id` is
used. Moving them as-is would either pull historical state into `Module1Analysis`
or change public behavior.

No schema, YAML, scoring, label, stance, smoothing, plotting, historical review,
or model-output changes are recommended for the next step.

## Method classification table

| Line | Method | Purpose | Reads result/config only? | Reads historical state? | Accepts/resolves `context_id`? | Live state beyond `Module1Result`? | Mutates? | Proposed owner |
|---:|---|---|---|---|---|---|---|---|
| 5021 | `_target_resolution_from_canonical(...)` | Build `TargetResolution` for canonical stance/component targets. | Yes: component/exposure config. | No | No | No, if configs are in `Module1Result`. | No | Safe for `Module1Analysis` after small adapter/helper extraction. |
| 5098 | `_target_resolution_for_raw_input(...)` | Build raw-input `TargetResolution`. | Yes. | No | No | No. | No | Safe for `Module1Analysis` now. |
| 5122 | `_target_resolution_for_feature(...)` | Build feature `TargetResolution`. | Yes: feature config. | No | No | No, if feature config is in result. | No | Safe for `Module1Analysis` after small adapter/helper extraction. |
| 5150 | `_normalize_target_level(...)` | Normalize target level aliases. | No state except label normalizer helper. | No | No | Depends on `_normalize_review_label`, which should be shared/extracted. | No | Safe after small adapter/helper extraction. |
| 5178 | `_resolve_target_for_context(...)` | Resolve raw input, feature, component, or stance target for context retrieval. | Mostly: config plus data columns for raw inputs. | No | No | Uses `self.data.columns`; data is in `Module1Result`. | No | Safe after adapter extraction. |
| 5217 | `_resolve_target(...)` | Resolve component/stance aliases and target groups. | Yes: config metadata and alias helpers. | No | No | Depends on historical-review-named alias/group helpers but reads config only. | No | Safe after alias/group helper extraction or rename. |
| 5363 | `_features_for_component_score(...)` | Return feature names used by a component score output. | Yes: component config. | No | No | No. | No | Safe for `Module1Analysis` now. |
| 5403 | `_raw_input_dependencies_for_feature(...)` | Recursively expand feature dependencies to raw inputs. | Yes: data columns and feature config. | No | No | No, if result carries `data` and feature config. | No | Safe for `Module1Analysis` after adapter extraction. |
| 5469 | `_dependencies_for_resolution(...)` | Build `TargetDependency` for target/dependency level. | Yes: config/data via helper calls. | No | No | Depends on component-label helper and config helpers. | No | Safe after small adapter/helper extraction. |
| 5608 | `_normalize_dependency_level(...)` | Normalize dependency-level aliases and validate by target level. | No meaningful state except normalizer helper. | No | No | Depends on `_normalize_review_label`. | No | Safe after helper extraction. |
| 5680 | `_required_output_table(...)` | Enforce that a named output table exists. | Reads live attributes by string. | No | No | Yes as implemented; can become table-bundle helper. | No | Safe only after small adapter/helper extraction. |
| 5701 | `_window_series_or_frame(...)` | Copy and date-window a Series/DataFrame. | Yes: input object only. | No | No | No. | No | Safe for `Module1Analysis` now. |
| 5712 | `_add_context_frame(...)` | Add selected columns and metadata to context output parts. | Yes: input frame only. | No | No | No. | Mutates local lists/dicts passed by caller only. | Safe for `Module1Analysis` now. |
| 5747 | `_resolved_path_metadata(...)` | Convert resolution/dependency to metadata. | Yes: args only. | No | No | No. | No | Safe for `Module1Analysis` now. |
| 5764 | `get_target_context(...)` | Public target/dependency retrieval API. | Yes for explicit windows. | Only via `_resolve_historical_event_window`. | Yes | Historical state only when `context_id` is provided. | No | Mixed method: split result-only core plus historical `context_id` wrapper. |
| 6071 | `_resolve_target_compare(...)` | Normalize compare mode by target level. | No meaningful state except normalizer. | No | No | Depends on `_normalize_target_level`. | No | Safe after helper extraction. |
| 6118 | `_comparison_normalization_recommendation(...)` | Recommend plot normalization based on comparison layer. | Yes: args only. | No | No | No. | No | Safe for `Module1Analysis` now. |
| 6138 | `build_target_comparison_dataset(...)` | Build consumer-neutral comparison dataset from target context. | Yes for explicit windows. | Through `get_target_context`. | Yes | Historical state only when `context_id` is forwarded. | No | Mixed method: split result-only core plus historical wrapper. |
| 6260 | `raw_inputs_for_target(...)` | Return raw-input dependency columns for a target. | Yes through target context with no `context_id`. | No | No | Uses `get_target_context` but no historical path. | No | Safe after `get_target_context` core split. |
| 6274 | `_resolve_historical_event_window(...)` | Resolve `context_id` to event `start`/`end`. | No. | Yes: `historical_context["events"]`. | Yes | Requires historical context loaded outside `Module1Result`. | No | Historical-boundary method for future `Module1HistoricalAnalysis`. |

## Result-only candidate list

Safe to move to `Module1Analysis` now, once imports and dataclass locations are
handled carefully:

- `_target_resolution_for_raw_input(...)`
- `_features_for_component_score(...)`
- `_window_series_or_frame(...)`
- `_add_context_frame(...)`
- `_resolved_path_metadata(...)`
- `_comparison_normalization_recommendation(...)`

Safe only after small adapter/helper extraction:

- `_target_resolution_from_canonical(...)`
- `_target_resolution_for_feature(...)`
- `_normalize_target_level(...)`
- `_resolve_target_for_context(...)`
- `_resolve_target(...)`
- `_raw_input_dependencies_for_feature(...)`
- `_dependencies_for_resolution(...)`
- `_normalize_dependency_level(...)`
- `_required_output_table(...)`
- `_resolve_target_compare(...)`
- `raw_inputs_for_target(...)`

The adapter work should avoid carrying historical-review naming into
`Module1Analysis`. In particular, `_historical_review_target_aliases(...)`,
`_historical_review_target_groups(...)`, and `_normalize_review_label(...)` are
used by target resolution but are not inherently historical; they should either
be extracted as neutral target-resolution helpers or left in `RegimeModule` until
the boundary is clearer.

## Historical-boundary candidate list

- `_resolve_historical_event_window(...)` belongs outside pure
  `Module1Analysis`. It is a historical-context lookup helper.
- Historical review callers such as `_historical_case_to_target_context(...)`
  should continue passing explicit `start`/`end` to the result-only context core
  after the split.
- Plotting and diagnostics that accept `context_id` should use a historical
  boundary helper to resolve explicit dates before calling result-only retrieval.

## Mixed-method list

- `get_target_context(...)`: result-only when called with explicit `start`/`end`
  or no window, historical-dependent only when `context_id` is not `None`.
- `build_target_comparison_dataset(...)`: result-only when no `context_id` is
  forwarded, historical-dependent only through `get_target_context(...)`.

These should be split into:

- a result-only core that accepts explicit windows and table/config inputs from
  `Module1Result`;
- a compatibility wrapper on `RegimeModule` that preserves `context_id` behavior
  by resolving the historical event window first;
- later, a `Module1HistoricalAnalysis` wrapper that owns `context_id` resolution.

## `context_id` boundary

Methods that are result-only with explicit windows:

- `get_target_context(...)`
- `build_target_comparison_dataset(...)`
- downstream tracing/plotting callers that pass `start`/`end` after resolving a
  historical event window

Methods that become historical-context-dependent only with `context_id`:

- `get_target_context(...)`
- `build_target_comparison_dataset(...)`
- plotting and tracing methods that forward `context_id` to either method or call
  `_resolve_historical_event_window(...)` themselves

`context_id` resolution can be separated cleanly because it only maps
`context_id` to `start`/`end` using `historical_context["events"]`. The
recommended boundary is:

- `Module1Analysis`: accepts explicit `start`/`end` only.
- `RegimeModule`: preserves current public `context_id` behavior during
  migration by resolving `context_id` before delegation.
- Future `Module1HistoricalAnalysis`: owns context-id lookup and historical-case
  workflows.

## Recommended next implementation PR

Split `context_id` resolution first, without moving public APIs.

Narrow implementation shape:

1. Add a private result-only helper for target-context construction that accepts
   explicit tables/configs or a `Module1Result`, plus explicit `start`/`end`.
2. Keep `RegimeModule.get_target_context(...)` public and behavior-compatible.
   It should resolve `context_id` with the existing historical helper, then call
   the result-only core with explicit dates.
3. Do not move `build_target_comparison_dataset(...)` until
   `get_target_context(...)` has this clean split and equivalence tests pass.

This is safer than moving several private helpers immediately because it creates
the key ownership boundary while preserving all public behavior.

## Behavior risks

- Return-shape changes in `TargetContextResult` and `TargetCompareDataset`,
  especially `resolution`, `request`, `resolved_path`, `returned_columns`,
  `source_layer_mapping`, `source_column_mapping`, `metadata`, `start`, `end`,
  and `context_id`.
- Target alias and target-group resolution changes if
  `_historical_review_target_aliases(...)` or
  `_historical_review_target_groups(...)` are renamed or extracted incorrectly.
- Context-window changes if explicit `start`/`end` precedence over
  `context_id` event dates is not preserved.
- Raw-input dependency expansion changes, especially recursive feature
  dependencies, spread features, and sorted/deduplicated raw-input columns.
- Column order changes from `parts` concatenation, `dict.fromkeys(...)`
  de-duplication, and removal of duplicate data columns.
- Index/window changes from `pd.to_datetime(start/end)` filtering and raw-input
  `ffill_inputs` behavior.
- Missing-output error message changes from `_required_output_table(...)`.
- Public behavior of `get_target_context(...)` for partial pipeline state.
- Public behavior of `build_target_comparison_dataset(...)`, including compare
  mode normalization and validation that returned columns exist in `ctx.data`.
- Downstream plotting/tracing dependencies:
  `diagnose_rule_mapped_stance(...)`, trace helpers, `_plot_target_inputs_on_axes(...)`,
  and `plot_target_comparison(...)` depend on these target/context outputs.

## Future validation plan

For the next implementation PR:

- Run syntax checks on all touched Python files:
  `python -m py_compile module1.py module1_result.py module1_analysis.py`.
- Run `git diff --check`.
- With local data, run the Module 1 pipeline and compare old vs new
  `get_target_context(...)` outputs for:
  raw input, feature, component, stance, and target-group cases.
- Compare explicit-window behavior for no window, `start` only, `end` only, and
  both `start`/`end`.
- Compare `context_id` behavior with historical context loaded:
  event-only dates, explicit `start` overriding event start, explicit `end`
  overriding event end, and unknown `context_id` errors.
- Compare `build_target_comparison_dataset(...)` for compare modes:
  `auto`, `components`, `features`, `raw_inputs`, and `full` where valid.
- Validate missing-output behavior before each pipeline step:
  data/config loaded only, after features, after scores, after labels, and after
  exposure stance.
- Validate target aliases and target groups from config metadata.
- Validate raw-input dependency expansion for `change`, `pct_change`, `level`,
  and `spread` feature definitions.
- Assert equality of keys, dataclass fields, metadata dictionaries, returned
  column tuples, column order, index order, values, missing values, and error
  messages where practical.
- Confirm callers that use these helpers still work:
  `raw_inputs_for_target(...)`, rule-mapped diagnostics using
  `get_target_context(...)`, and `plot_target_comparison(..., return_data=True)`.

## Open questions

- Should neutral target alias helpers be renamed now, or should names remain
  stable until after behavior-equivalence tests are in place?
- Should `Module1Analysis.get_target_context(...)` reject `context_id`
  explicitly, or omit that parameter entirely?
- Should `data` remain part of `Module1Result` for raw-input context retrieval,
  or should raw inputs be passed separately in a future boundary?
- Should `TargetResolution`, `TargetDependency`, `TargetContextResult`, and
  `TargetCompareDataset` stay in `module1.py` temporarily, or move to a neutral
  result/context types file before method movement?

## Audit-only confirmation

This report is audit-only. It recommends no production code, YAML, schema,
public API, scoring, label, stance, smoothing, historical review, plotting,
config interpretation, or model-output changes in this task.
