# Module 1 Group G Stabilization-Case Diagnostic Audit

## Executive summary

Group G can be represented by a generic rule-mapped stabilization-case comparison core without changing the public curve diagnostic contract. The active public stabilization-case comparison in scope is `compare_curve_positioning_stabilization_cases(...)`. It already builds each scenario through `_build_rule_mapped_stance_score_breakdown(...)` with explicit `stabilization_overrides`, then uses curve-specific code only to assemble the public detail columns, summary tables, bucket transition summary, score distribution, and optional diagnostics alias.

The future migration should preserve the public method signature, result keys, case ids, DataFrame columns, column order, value semantics, and default windows. No generic implementation should be added in G1. G2 should build a private generic rule-mapped comparison core that returns enough structured outputs to preserve the current curve wrapper. G3 should migrate the public curve diagnostic behind the same API and remove only target-specific helpers that are clearly unused after the migration.

This audit is report-only. No production code, schema, config, diagnostics, YAML, tests, or existing reports were changed. No model output changed.

## Public diagnostics in scope

### Stabilization-case comparison diagnostic

```python
compare_curve_positioning_stabilization_cases(
    self,
    cases: dict | None = None,
    windows: dict | None = None,
    include_diagnostics: bool = True,
) -> dict
```

The task text mentions `include_detail`, but the current public method uses `include_diagnostics`. Detail is always returned through `detail_by_case`; `include_diagnostics` only controls whether the result also includes `diagnostics_by_case`.

### Related diagnostics to avoid changing

These public diagnostics are related cleanup context only and should not be changed by Group G:

- `compare_credit_input_smoothing_effect(...)`
- `compare_curve_input_smoothing_effect(...)`
- `compare_curve_move_driver_threshold_effect(...)`

## Return object and result keys

Static inspection and runtime inspection agree on these keys.

With `include_diagnostics=False`:

- `summary`
- `window_summary`
- `detail_by_case`
- `bucket_transition_summary`
- `score_distribution`

With `include_diagnostics=True`:

- `summary`
- `window_summary`
- `detail_by_case`
- `bucket_transition_summary`
- `score_distribution`
- `diagnostics_by_case`

`detail_by_case` is a dict keyed by case id. `diagnostics_by_case` is currently another dict keyed by case id and contains the same detail DataFrames as `detail_by_case`.

Runtime-observed shapes with local data:

- `summary`: `(5, 28)`
- `window_summary`: `(20, 21)`
- `detail_by_case["neutral_base"]`: `(7495, 25)`
- `bucket_transition_summary`: `(15, 6)`
- `score_distribution`: `(90, 5)`
- `diagnostics_by_case["neutral_base"]`: `(7495, 25)` when included

## Summary DataFrame columns

`summary` columns:

1. `case_id`
2. `total_rows`
3. `valid_rows`
4. `mean_raw_score`
5. `mean_stabilized_score`
6. `mean_score_diff`
7. `mean_abs_score_diff`
8. `max_abs_score_diff`
9. `changed_score_count`
10. `changed_score_ratio`
11. `changed_direction_count`
12. `changed_direction_ratio`
13. `changed_strength_count`
14. `changed_strength_ratio`
15. `raw_score_change_count`
16. `stabilized_score_change_count`
17. `score_change_reduction_count`
18. `score_change_reduction_ratio`
19. `one_day_spike_count_raw`
20. `one_day_spike_count_stabilized`
21. `one_day_spike_reduction_count`
22. `one_day_spike_reduction_ratio`
23. `bucket_change_count_raw`
24. `bucket_change_count_stabilized`
25. `dominant_raw_direction`
26. `dominant_stabilized_direction`
27. `dominant_raw_strength`
28. `dominant_stabilized_strength`

`window_summary` columns:

1. `case_id`
2. `window_id`
3. `start`
4. `end`
5. `obs_count`
6. `mean_raw_score`
7. `mean_stabilized_score`
8. `mean_score_diff`
9. `mean_abs_score_diff`
10. `changed_score_count`
11. `changed_score_ratio`
12. `raw_score_change_count`
13. `stabilized_score_change_count`
14. `one_day_spike_count_raw`
15. `one_day_spike_count_stabilized`
16. `dominant_raw_rule_case`
17. `dominant_stabilized_rule_case`
18. `dominant_raw_direction`
19. `dominant_stabilized_direction`
20. `dominant_raw_strength`
21. `dominant_stabilized_strength`

`bucket_transition_summary` columns:

1. `case_id`
2. `bucket_type`
3. `raw_change_count`
4. `stabilized_change_count`
5. `change_reduction_count`
6. `change_reduction_ratio`

`score_distribution` columns:

1. `case_id`
2. `score_type`
3. `score`
4. `count`
5. `ratio`

## Detail DataFrame columns

Each `detail_by_case[case_id]` DataFrame has these columns:

1. `curve_change_score`
2. `curve_state_score`
3. `curve_move_driver_score`
4. `raw_curve_change_bucket`
5. `stabilized_curve_change_bucket`
6. `raw_curve_state_bucket`
7. `stabilized_curve_state_bucket`
8. `raw_yield_move_driver_bucket`
9. `stabilized_yield_move_driver_bucket`
10. `raw_curve_positioning_rule_case`
11. `stabilized_curve_positioning_rule_case`
12. `raw_curve_positioning_score`
13. `stabilized_curve_positioning_score`
14. `score_diff`
15. `raw_curve_positioning`
16. `stabilized_curve_positioning`
17. `raw_curve_positioning_strength`
18. `stabilized_curve_positioning_strength`
19. `score_changed`
20. `direction_changed`
21. `strength_changed`
22. `raw_score_change_flag`
23. `stabilized_score_change_flag`
24. `raw_one_day_spike_flag`
25. `stabilized_one_day_spike_flag`

Bucket comparison columns:

- `raw_curve_change_bucket` versus `stabilized_curve_change_bucket`
- `raw_curve_state_bucket` versus `stabilized_curve_state_bucket`
- `raw_yield_move_driver_bucket` versus `stabilized_yield_move_driver_bucket`

Rule-case comparison columns:

- `raw_curve_positioning_rule_case` versus `stabilized_curve_positioning_rule_case`

Score, label, and strength comparison columns:

- `raw_curve_positioning_score` versus `stabilized_curve_positioning_score`
- `raw_curve_positioning` versus `stabilized_curve_positioning`
- `raw_curve_positioning_strength` versus `stabilized_curve_positioning_strength`
- Derived comparison flags: `score_changed`, `direction_changed`, `strength_changed`

## Current stabilization-case comparison flow

1. `compare_curve_positioning_stabilization_cases(...)` validates that component scores, exposure stance, and config have been calculated or loaded.
2. It resolves the curve positioning stance config.
3. It uses provided `cases` or `_default_curve_stabilization_cases()`.
4. It uses provided `windows` or `_default_curve_stabilization_windows()`.
5. For each case, `_curve_stabilization_case_detail(case_config, stance_config)` builds a detail DataFrame.
6. The detail path runs `_build_rule_mapped_stance_score_breakdown("curve_positioning", ..., stabilization_overrides=neutral_overrides)` for the raw/baseline side.
7. The detail path runs `_build_rule_mapped_stance_score_breakdown("curve_positioning", ..., stabilization_overrides=case_config)` for the case side.
8. The curve-specific detail assembler maps generic rule-mapped output columns into public raw/stabilized comparison columns.
9. `_curve_stabilization_summary_row(...)`, `_curve_stabilization_window_row(...)`, bucket transition logic, and score distribution logic derive the public summary tables.
10. If `include_diagnostics=True`, the same detail DataFrame is also placed in `diagnostics_by_case`.

## Stabilization cases compared

Default case ids:

- `neutral_base`
- `persistence_3`
- `hysteresis_005`
- `hysteresis_005_persistence_3`
- `hysteresis_010_persistence_3`

Default windows:

- `taper_tantrum_review`: `2012-08-01` to `2014-06-01`
- `fed_hiking_2022`: `2022-03-01` to `2022-12-31`
- `covid_shock_2020`: `2020-02-01` to `2020-06-30`
- `full_history`: `None` to `None`

## Neutral and configured case behavior

The neutral/baseline stabilization scenario is `_neutral_curve_positioning_stabilization_overrides()`:

```python
{
    "curve_change": {"hysteresis_buffer": 0.0, "min_state_persistence": 1},
    "curve_state": {"hysteresis_buffer": 0.0, "min_state_persistence": 1},
    "curve_move_driver": {"hysteresis_buffer": 0.0, "min_state_persistence": 1},
}
```

This neutral case disables hysteresis and persistence beyond immediate classification for all three curve inputs. It is used as the raw/baseline side for every case comparison, including the `neutral_base` case itself.

Case-specific overrides are full `state_stabilization` mappings keyed by:

- `curve_change`
- `curve_state`
- `curve_move_driver`

Each case component must provide:

- `hysteresis_buffer`
- `min_state_persistence`

In the active detail path, overrides are validated by the generic `_resolve_rule_mapped_stabilization_config(...)` through `_build_rule_mapped_stance_score_breakdown(...)`.

## Production and diagnostic helper classification

Production/trace paths that should remain stable:

- `_build_rule_mapped_stance_score_breakdown(...)`: active production and trace path for rule-mapped stance calculation.
- `_resolve_rule_mapped_stabilization_config(...)`: schema/runtime contract resolver for rule-mapped stabilization mappings.
- `_stabilize_state_series(...)`: generic stabilization primitive used by rule-mapped production and diagnostics.
- `_rule_mapped_bucket_candidate(...)`: active bucket stabilization dispatch for rule-mapped bucket inputs.
- `_ordered_threshold_bucket_hysteresis_candidate(...)`: active ordered/range bucket hysteresis helper.
- `_threshold_bucket_hysteresis_candidate(...)`: active tail/default threshold bucket hysteresis helper.
- `_score_bucket(...)` and `_threshold_bucket(...)`: active bucket classification primitives.
- `_derive_rule_mapped_diagnostic_spec_from_context(...)`, `_resolve_rule_mapped_diagnostic_config(...)`, and `_RULE_MAPPED_DIAGNOSTIC_COMPAT`: active public diagnostic compatibility/spec helpers; keep until Group K.

Curve stabilization diagnostic-only or target-specific assembly paths:

- `compare_curve_positioning_stabilization_cases(...)`: public curve diagnostic entry; keep the API stable.
- `_curve_stabilization_case_detail(...)`: curve-specific detail assembler over generic rule-mapped breakdowns.
- `_curve_stabilization_case_summary_row(...)`: no current function by that exact name; the active helper is `_curve_stabilization_summary_row(...)`.
- `_curve_stabilization_window_row(...)`: curve-specific window summary assembler.
- `_default_curve_stabilization_cases(...)`: curve-specific default case catalog.
- `_default_curve_stabilization_windows(...)`: curve-specific default windows.
- `_neutral_curve_positioning_stabilization_overrides(...)`: curve-specific neutral case factory.

Legacy curve-specific reconstruction helpers:

- `_curve_positioning_stabilization_config(...)`
- `_stabilize_curve_positioning_rule_buckets(...)`
- `_curve_change_candidate_bucket(...)`
- `_curve_state_candidate_bucket(...)`
- `_yield_move_driver_candidate_bucket(...)`
- `_curve_positioning_score_from_component_scores(...)`

These are not used by the active stabilization-case comparison detail path. They remain relevant to older curve reconstruction paths and should not be removed in G1.

## Target-specific helpers likely replaceable in G2/G3

Likely replaceable after a generic rule-mapped comparison core exists:

- `_curve_stabilization_case_detail(...)`, if the generic core can produce raw/stabilized detail columns and the curve wrapper can rename/preserve public columns.
- `_curve_stabilization_summary_row(...)`, if generic summary assembly can be configured with score, label, strength, rule-case, and bucket column names.
- `_curve_stabilization_window_row(...)`, if generic window summary assembly preserves the current output columns.
- Bucket transition and score distribution loops inside `compare_curve_positioning_stabilization_cases(...)`, if the generic core can emit equivalent tables.
- `_neutral_curve_positioning_stabilization_overrides(...)`, if the generic core can generate a neutral override map from the rule-mapped state inputs while preserving the same values.

Replaceable only if their remaining callers are migrated or removed:

- `_curve_positioning_stabilization_config(...)`
- `_stabilize_curve_positioning_rule_buckets(...)`
- `_yield_move_driver_candidate_bucket(...)`
- `_curve_change_candidate_bucket(...)`
- `_curve_state_candidate_bucket(...)`

## Helpers that should remain for Groups H/I/J/K

Keep for Group H summary/display cleanup:

- Public wrapper result keys and table vocabulary.
- `_curve_stabilization_summary_row(...)` and `_curve_stabilization_window_row(...)` until generic summary/display behavior has explicit equality checks.

Keep for Group I schema cleanup:

- `_resolve_rule_mapped_stabilization_config(...)`
- `_resolve_rule_mapped_stance_schema(...)`
- schema-side rule-mapped validation in `module1_schema.py`

Keep for Group J credit adjustment:

- `_build_rule_mapped_stance_score_breakdown(...)`
- `_rule_mapped_adjusted_row(...)`
- credit adjustment metadata and output handling inside the generic rule-mapped path

Keep for Group K compatibility metadata:

- `_RULE_MAPPED_DIAGNOSTIC_COMPAT`
- `_derive_rule_mapped_diagnostic_spec_from_context(...)`
- `_resolve_rule_mapped_diagnostic_config(...)`

## Candidate generic stabilization-case comparison core

A private generic core should accept:

- target or stance name;
- stance config or resolved rule-mapped context;
- case mapping;
- neutral/baseline stabilization override mapping, or instructions to derive one;
- window mapping;
- output vocabulary mapping for public column preservation;
- flags controlling optional diagnostics aliasing.

The core should:

1. Resolve the rule-mapped context and diagnostic spec.
2. Build neutral/baseline and case breakdowns through `_build_rule_mapped_stance_score_breakdown(...)`.
3. Map configured score-input, raw/stabilized state, rule-case, final-score, stance-label, and strength-label columns into a comparison detail DataFrame.
4. Compute score differences and mismatch flags with the same tolerance semantics.
5. Compute change counts and one-day spike flags with the same helpers.
6. Emit generic summary, window summary, state/bucket transition summary, score distribution, detail-by-case, and optional diagnostics-by-case structures.
7. Let the public curve wrapper preserve exact current keys and public column names.

This is feasible because the curve detail path is already driven by generic rule-mapped breakdowns. The main risk is not calculation feasibility; it is preserving public output vocabulary and ordering.

## Recommended G2/G3 implementation split

G2 should build the private generic core first:

- Add a private helper for rule-mapped stabilization-case comparisons.
- Use `_build_rule_mapped_stance_score_breakdown(...)` as the only stance reconstruction path.
- Add focused equality tests or runtime comparison checks against the current curve diagnostic outputs.
- Do not change `compare_curve_positioning_stabilization_cases(...)` yet unless the G2 task explicitly includes a wrapper call guarded by equality checks.

G3 should migrate and clean up:

- Route `compare_curve_positioning_stabilization_cases(...)` through the generic core.
- Preserve the public method signature, result keys, DataFrame columns, column order, default cases, and default windows.
- Remove only curve-specific helpers that have no remaining callers after migration.
- Defer summary/display reshaping to Group H.
- Defer schema/validation cleanup to Group I.
- Do not change credit adjustment mechanics; those belong to Group J.
- Do not move or rename `_RULE_MAPPED_DIAGNOSTIC_COMPAT`; that belongs to Group K.

## Behavior-preservation and equality requirements

Future PRs should compare exact result keys for:

- `include_diagnostics=False`
- `include_diagnostics=True`

Future PRs should compare DataFrame columns and values for:

- `summary`
- `window_summary`
- every `detail_by_case[case_id]`
- `bucket_transition_summary`
- `score_distribution`
- every `diagnostics_by_case[case_id]` when included

Future PRs should preserve:

- public signature;
- default case ids and case order;
- default window ids and window order;
- all output keys;
- all DataFrame columns and column order;
- raw versus stabilized bucket semantics;
- raw versus stabilized rule-case semantics;
- score difference and mismatch semantics;
- score-change and one-day-spike counting semantics;
- `detail_by_case` always being returned;
- `diagnostics_by_case` being included only when `include_diagnostics=True`;
- no changes to production scoring, labels, stance logic, config interpretation, schema validation, YAML function names, or `_RULE_MAPPED_DIAGNOSTIC_COMPAT`.

## Commands run

- `git status --short --branch`
- `git branch --show-current`
- `git log --oneline -5`
- `git fetch --prune origin`
- `git branch -r --list 'origin/codex/session/*'`
- `git branch -r --list 'origin/codex/task/*'`
- `git checkout codex/session/260629_1306`
- `git pull --ff-only origin codex/session/260629_1306`
- `git checkout -b codex/task/260630_1906_g1_stabilization_case_audit`
- `rg -n "compare_curve_positioning_stabilization_cases|_curve_stabilization_case_detail|_curve_stabilization_case_summary_row|_neutral_curve_positioning_stabilization_overrides|_curve_positioning_stabilization_config|_stabilize_curve_positioning_rule_buckets" .`
- `rg -n "_build_rule_mapped_stance_score_breakdown|_resolve_rule_mapped_stabilization_config|_stabilize_state_series|_rule_mapped_bucket_candidate|_ordered_threshold_bucket_hysteresis_candidate|_threshold_bucket_hysteresis_candidate|_score_bucket|_threshold_bucket|_derive_rule_mapped_diagnostic_spec_from_context|_resolve_rule_mapped_diagnostic_config|_RULE_MAPPED_DIAGNOSTIC_COMPAT" .`
- `rg -n "compare_credit_input_smoothing_effect|compare_curve_input_smoothing_effect|compare_curve_move_driver_threshold_effect" .`
- `sed -n` inspections of relevant `module1.py`, `module1_schema.py`, and `data/module1_config.yaml` sections
- `poetry env info --path`
- `python - <<'PY' ...` runtime attempt with default interpreter; blocked by missing `pandas`
- `poetry run python - <<'PY' ...` runtime attempt; blocked by missing `FRED_API_KEY`
- `FRED_API_KEY=dummy poetry run python - <<'PY' ...` runtime diagnostic inspection; succeeded

## Limitations and checks not run

- No production behavior validation was required because this is audit-only.
- No Python syntax check was required because no Python files were modified.
- Runtime inspection used `FRED_API_KEY=dummy` because the environment did not provide a real `FRED_API_KEY`; the diagnostic ran successfully against local data and did not require a successful FRED request.
- The default interpreter does not have `pandas`; runtime inspection used the project Poetry environment.
- No model outputs changed because this PR only adds this report.
