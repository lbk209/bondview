# Module 1 Group H Summary/Display Diagnostic Audit

## Executive summary

Group H should be a preservation-first cleanup. The current Module 1 compare diagnostics expose several public table contracts whose vocabulary is target-specific and should not be redesigned during cleanup. The clearest safe genericization opportunities are small private helpers for repeated count/math mechanics: window slicing, mismatch count, mean absolute difference, transition count, one-day spike count, dominant value, ratio-with-empty handling, and case/window row assembly scaffolding.

Do not start H2 by changing public output names, keys, table shapes, or table ordering. H2 should first build small private summary/count helpers where the current duplication is obvious and equality can be proven. H3 can migrate selected diagnostics to those helpers one at a time. H4 should remove leftovers only after H2/H3 migrations prove that old summary/display assembly paths are unused.

This report is audit-only. No production code, config, schema, YAML, diagnostics, tests, or existing reports changed. No model output changed.

## Public diagnostics in scope

### `compare_horizon_cases`

```python
@classmethod
compare_horizon_cases(
    cls,
    horizon_cases=None,
    horizon_grid=None,
    base_horizons=None,
    *,
    api_key_env="FRED_API_KEY",
    series_config_path="data/fred_series_config.csv",
    module1_config_path="data/module1_config.yaml",
    data_path="data/raw_data_19980101_20260508.csv",
    historical_context_path="data/historical_context.yaml",
    target=None,
    context_id=None,
    level=None,
    only_use_for_validation=True,
    include_low_relevance=False,
    min_obs=20,
    plausible_threshold=0.70,
    mixed_threshold=0.45,
    output: str = "summary",
    max_cases=100,
) -> pd.DataFrame
```

This is a batch comparison diagnostic. It returns one flat DataFrame, not a dict. It supports `output="summary"`, `horizon_cases`, `compact`, `cases`, `diagnostic`, and other `review_historical_cases(...)` output modes.

### `compare_credit_input_smoothing_effect`

```python
compare_credit_input_smoothing_effect(
    self,
    windows: dict | None = None,
    include_detail: bool = True,
) -> dict
```

### `compare_curve_input_smoothing_effect`

```python
compare_curve_input_smoothing_effect(
    self,
    windows: dict | None = None,
    include_detail: bool = True,
) -> dict
```

### `compare_curve_move_driver_threshold_effect`

```python
compare_curve_move_driver_threshold_effect(
    self,
    include_detail: bool = True,
) -> dict
```

### `compare_curve_positioning_stabilization_cases`

```python
compare_curve_positioning_stabilization_cases(
    self,
    cases: dict | None = None,
    windows: dict | None = None,
    include_diagnostics: bool = True,
) -> dict
```

There is no `include_detail` parameter here. `detail_by_case` is always returned. `diagnostics_by_case` is returned only when `include_diagnostics=True`.

### `compare_credit_stance_persistence_cases`

```python
compare_credit_stance_persistence_cases(
    self,
    cases: dict | None = None,
    hysteresis_buffer: float = 0.05,
    windows: dict | None = None,
    include_diagnostics: bool = True,
) -> dict
```

## Result key matrix

| Diagnostic | Detail flag | Result keys |
| --- | --- | --- |
| `compare_horizon_cases` | none | Returns a single DataFrame selected by `output` |
| `compare_credit_input_smoothing_effect(False)` | `include_detail=False` | `summary`, `window_summary` |
| `compare_credit_input_smoothing_effect(True)` | `include_detail=True` | `summary`, `window_summary`, `detail` |
| `compare_curve_input_smoothing_effect(False)` | `include_detail=False` | `summary`, `window_summary` |
| `compare_curve_input_smoothing_effect(True)` | `include_detail=True` | `summary`, `window_summary`, `detail` |
| `compare_curve_move_driver_threshold_effect(False)` | `include_detail=False` | `summary` |
| `compare_curve_move_driver_threshold_effect(True)` | `include_detail=True` | `summary`, `detail` |
| `compare_curve_positioning_stabilization_cases(False)` | `include_diagnostics=False` | `summary`, `window_summary`, `detail_by_case`, `bucket_transition_summary`, `score_distribution` |
| `compare_curve_positioning_stabilization_cases(True)` | `include_diagnostics=True` | previous keys plus `diagnostics_by_case` |
| `compare_credit_stance_persistence_cases(False)` | `include_diagnostics=False` | `summary`, `window_metrics`, `shock_detection`, `recovery_behavior`, `tight_spread_behavior`, `late_volatility`, `full_period_stabilization` |
| `compare_credit_stance_persistence_cases(True)` | `include_diagnostics=True` | previous keys plus `diagnostics` |

## Detail flag behavior

Diagnostics using `include_detail`:

- `compare_credit_input_smoothing_effect`
- `compare_curve_input_smoothing_effect`
- `compare_curve_move_driver_threshold_effect`

Diagnostics using `include_diagnostics`:

- `compare_curve_positioning_stabilization_cases`
- `compare_credit_stance_persistence_cases`

Diagnostics that always return detail-like objects:

- `compare_curve_positioning_stabilization_cases` always returns `detail_by_case`.
- `compare_credit_stance_persistence_cases` always returns derived case tables; full per-date diagnostics are optional under `diagnostics`.
- `compare_horizon_cases` returns the requested flat table directly.

## Runtime-observed table contracts

Runtime inspection used local data through the Poetry environment with `FRED_API_KEY=dummy`.

### Credit input smoothing

`summary`: shape `(1, 16)`

Columns:

- `total_rows`
- `valid_rows`
- `credit_spread_change_score_changed_count`
- `credit_spread_change_score_mean_abs_diff`
- `credit_spread_state_score_changed_count`
- `credit_spread_state_score_mean_abs_diff`
- `credit_stance_score_changed_count`
- `credit_stance_score_changed_ratio`
- `raw_credit_score_change_count`
- `smoothed_credit_score_change_count`
- `score_change_reduction_count`
- `score_change_reduction_ratio`
- `raw_one_day_spike_count`
- `smoothed_one_day_spike_count`
- `one_day_spike_reduction_count`
- `one_day_spike_reduction_ratio`

`window_summary`: shape `(4, 19)`. It uses all `summary` columns plus:

- `window_id`
- `start`
- `end`

`detail`: shape `(7495, 15)`

Columns:

- `baa10y_change`
- `baa10y`
- `baa10y_change_prepared_for_credit_spread_change`
- `baa10y_level_prepared_for_credit_spread_state`
- `raw_credit_spread_change_score`
- `raw_credit_spread_state_score`
- `smoothed_credit_spread_change_score`
- `smoothed_credit_spread_state_score`
- `raw_credit_stance_score`
- `smoothed_credit_stance_score`
- `credit_stance_score_diff`
- `raw_credit_stance`
- `raw_credit_stance_strength`
- `smoothed_credit_stance`
- `smoothed_credit_stance_strength`

### Curve input smoothing

`summary`: shape `(1, 18)`

Columns:

- `total_rows`
- `valid_rows`
- `curve_change_score_changed_count`
- `curve_change_score_mean_abs_diff`
- `curve_state_score_changed_count`
- `curve_state_score_mean_abs_diff`
- `curve_move_driver_score_changed_count`
- `curve_move_driver_score_changed_ratio`
- `curve_positioning_score_changed_count`
- `curve_positioning_score_changed_ratio`
- `raw_curve_score_change_count`
- `smoothed_curve_score_change_count`
- `score_change_reduction_count`
- `score_change_reduction_ratio`
- `raw_one_day_spike_count`
- `smoothed_one_day_spike_count`
- `one_day_spike_reduction_count`
- `one_day_spike_reduction_ratio`

`window_summary`: shape `(3, 21)`. It uses all `summary` columns plus:

- `window_id`
- `start`
- `end`

`detail`: shape `(7495, 23)`

Columns:

- `curve_10y2y_change`
- `curve_10y2y_level`
- `dgs2_change`
- `dgs10_change`
- `curve_10y2y_change_prepared_for_curve_change`
- `curve_10y2y_level_prepared_for_curve_state`
- `dgs2_change_prepared_for_curve_move_driver`
- `dgs10_change_prepared_for_curve_move_driver`
- `dgs2_change_filtered_for_curve_move_driver`
- `dgs10_change_filtered_for_curve_move_driver`
- `raw_curve_change_score`
- `raw_curve_state_score`
- `raw_curve_move_driver_score`
- `smoothed_curve_change_score`
- `smoothed_curve_state_score`
- `smoothed_curve_move_driver_score`
- `raw_curve_positioning_score`
- `smoothed_curve_positioning_score`
- `score_diff`
- `raw_curve_positioning`
- `raw_curve_positioning_strength`
- `smoothed_curve_positioning`
- `smoothed_curve_positioning_strength`

### Curve move-driver threshold effect

`summary`: shape `(1, 14)`

Columns:

- `min_abs_value`
- `total_rows`
- `valid_rows`
- `rows_with_front_end_below_threshold`
- `rows_with_long_end_below_threshold`
- `rows_with_either_side_below_threshold`
- `rows_with_both_sides_below_threshold`
- `curve_move_driver_score_changed_count_vs_no_threshold`
- `curve_move_driver_score_changed_ratio_vs_no_threshold`
- `mixed_or_unclear_count_before_threshold`
- `mixed_or_unclear_count_after_threshold`
- `mixed_or_unclear_count_change`
- `curve_positioning_score_changed_count_due_to_threshold`
- `curve_positioning_score_changed_ratio_due_to_threshold`

`detail`: shape `(7495, 15)`

Columns:

- `dgs2_change`
- `dgs10_change`
- `dgs2_change_prepared_for_curve_move_driver`
- `dgs10_change_prepared_for_curve_move_driver`
- `dgs2_change_filtered_for_curve_move_driver`
- `dgs10_change_filtered_for_curve_move_driver`
- `curve_move_driver_score_without_threshold`
- `curve_move_driver_score_with_threshold`
- `curve_move_driver_bucket_without_threshold`
- `curve_move_driver_bucket_with_threshold`
- `curve_positioning_score_without_threshold`
- `curve_positioning_score_with_threshold`
- `curve_positioning_score_diff_due_to_threshold`
- `curve_move_driver_score_changed_by_threshold`
- `curve_positioning_score_changed_by_threshold`

### Curve stabilization cases

`summary`: shape `(5, 28)`

Columns:

- `case_id`
- `total_rows`
- `valid_rows`
- `mean_raw_score`
- `mean_stabilized_score`
- `mean_score_diff`
- `mean_abs_score_diff`
- `max_abs_score_diff`
- `changed_score_count`
- `changed_score_ratio`
- `changed_direction_count`
- `changed_direction_ratio`
- `changed_strength_count`
- `changed_strength_ratio`
- `raw_score_change_count`
- `stabilized_score_change_count`
- `score_change_reduction_count`
- `score_change_reduction_ratio`
- `one_day_spike_count_raw`
- `one_day_spike_count_stabilized`
- `one_day_spike_reduction_count`
- `one_day_spike_reduction_ratio`
- `bucket_change_count_raw`
- `bucket_change_count_stabilized`
- `dominant_raw_direction`
- `dominant_stabilized_direction`
- `dominant_raw_strength`
- `dominant_stabilized_strength`

`window_summary`: shape `(20, 21)`

Columns:

- `case_id`
- `window_id`
- `start`
- `end`
- `obs_count`
- `mean_raw_score`
- `mean_stabilized_score`
- `mean_score_diff`
- `mean_abs_score_diff`
- `changed_score_count`
- `changed_score_ratio`
- `raw_score_change_count`
- `stabilized_score_change_count`
- `one_day_spike_count_raw`
- `one_day_spike_count_stabilized`
- `dominant_raw_rule_case`
- `dominant_stabilized_rule_case`
- `dominant_raw_direction`
- `dominant_stabilized_direction`
- `dominant_raw_strength`
- `dominant_stabilized_strength`

`detail_by_case[neutral_base]`: shape `(7495, 25)`

Columns:

- `curve_change_score`
- `curve_state_score`
- `curve_move_driver_score`
- `raw_curve_change_bucket`
- `stabilized_curve_change_bucket`
- `raw_curve_state_bucket`
- `stabilized_curve_state_bucket`
- `raw_yield_move_driver_bucket`
- `stabilized_yield_move_driver_bucket`
- `raw_curve_positioning_rule_case`
- `stabilized_curve_positioning_rule_case`
- `raw_curve_positioning_score`
- `stabilized_curve_positioning_score`
- `score_diff`
- `raw_curve_positioning`
- `stabilized_curve_positioning`
- `raw_curve_positioning_strength`
- `stabilized_curve_positioning_strength`
- `score_changed`
- `direction_changed`
- `strength_changed`
- `raw_score_change_flag`
- `stabilized_score_change_flag`
- `raw_one_day_spike_flag`
- `stabilized_one_day_spike_flag`

`bucket_transition_summary`: shape `(15, 6)`

Columns:

- `case_id`
- `bucket_type`
- `raw_change_count`
- `stabilized_change_count`
- `change_reduction_count`
- `change_reduction_ratio`

`score_distribution`: shape `(90, 5)`

Columns:

- `case_id`
- `score_type`
- `score`
- `count`
- `ratio`

`diagnostics_by_case` is present only when `include_diagnostics=True`; it is keyed by the same case ids and currently contains the same detail DataFrame values.

### Credit stance persistence cases

`summary`: shape `(4, 14)`

Columns:

- `case_id`
- `change_persistence`
- `state_persistence`
- `covid_first_credit_negative_date`
- `covid_delay_days_vs_base`
- `recovery_mean_score`
- `recovery_negative_score_days`
- `tight_2021q2_mean_score`
- `tight_2021q2_tight_state_ratio`
- `late_2022_max_abs_daily_score_move`
- `late_2022_large_move_gt_0_5_count`
- `late_2022_large_move_gt_1_0_count`
- `full_changed_pair_count`
- `full_changed_pair_ratio`

`window_metrics`: shape `(16, 17)`

Columns:

- `case_id`
- `window_id`
- `obs_count`
- `credit_stance_score_mean`
- `credit_stance_score_min`
- `credit_stance_score_max`
- `credit_stance_score_std`
- `max_abs_daily_score_move`
- `baa10y_mean`
- `baa10y_min`
- `baa10y_max`
- `dominant_credit_state_pair`
- `dominant_credit_state_pair_ratio`
- `changed_pair_count`
- `changed_pair_ratio`
- `changed_change_state_count`
- `changed_spread_state_count`

Extra tables:

- `shock_detection`: `(4, 3)` columns `case_id`, `first_credit_negative_date`, `delay_days_vs_base`
- `recovery_behavior`: `(4, 5)` columns `case_id`, `dominant_credit_state_pair`, `dominant_credit_state_pair_ratio`, `credit_stance_score_mean`, `negative_score_days`
- `tight_spread_behavior`: `(4, 6)` columns `case_id`, `tight_state_count`, `tight_state_ratio`, `tight_pair_count`, `tight_pair_ratio`, `credit_stance_score_mean`
- `late_volatility`: `(4, 4)` columns `case_id`, `max_abs_daily_score_move`, `large_move_gt_0_5_count`, `large_move_gt_1_0_count`
- `full_period_stabilization`: `(4, 6)` columns `case_id`, `changed_pair_count`, `changed_change_state_count`, `changed_spread_state_count`, `changed_pair_ratio`, `non_missing_obs_count`

When `include_diagnostics=True`, `diagnostics` is a dict keyed by:

- `base_p1_p1`
- `case_a_change2_state1`
- `case_b_change1_state2`
- `case_c_change2_state2`

Runtime-observed `diagnostics[base_p1_p1]`: shape `(7495, 21)`.

## Case-based and extra output contracts

Case-based outputs:

- `compare_curve_positioning_stabilization_cases`: `detail_by_case`, optional `diagnostics_by_case`
- `compare_credit_stance_persistence_cases`: optional `diagnostics`

Extra output tables:

- `compare_curve_positioning_stabilization_cases`: `bucket_transition_summary`, `score_distribution`
- `compare_credit_stance_persistence_cases`: `window_metrics`, `shock_detection`, `recovery_behavior`, `tight_spread_behavior`, `late_volatility`, `full_period_stabilization`

## Duplicated summary/display patterns

Repeated mechanics across diagnostics:

- Build a full `detail` table first, then derive `summary`.
- Build `window_summary` by slicing detail for each `(start, end)` tuple, then adding `window_id`, `start`, and `end`.
- Count changed scores through `_series_mismatch_mask(...)`.
- Count transitions through `_count_series_changes(...)`.
- Count one-day spikes through `_count_one_day_spikes(...)`.
- Compute reductions and reduction ratios with repeated `if denominator else pd.NA`.
- Compute valid rows from pairs of raw/stabilized score columns.
- Build case tables by accumulating row dicts and wrapping them in `pd.DataFrame`.
- Select dominant case/state labels through `_curve_dominant_value(...)` or local equivalents.

Duplicated but currently target-specific:

- Credit and curve input-smoothing summary rows share the same pattern, but use target-specific component score column names and output vocabulary.
- Curve stabilization and credit persistence both assemble case/window display tables, but their public table vocabulary differs substantially.
- Curve move-driver threshold is a parameter-effect summary and should preserve its curve-specific threshold vocabulary.

## Safe genericization candidates

Good H2 candidates:

- `_ratio_or_na(numerator, denominator)` style helper.
- A private helper for `mean_abs_diff(detail, raw_col, smoothed_col)` with comparable filtering.
- A private helper for `changed_count(detail, left_col, right_col, tolerance=1e-10, comparable_only=...)`; note credit and curve smoothing currently differ slightly in explicit comparable masking.
- A private window-slicing helper that preserves current inclusive `start`/`end` filtering.
- A private helper to append `window_id`, `start`, and `end` after a summary row.
- A generic row-dict helper for score transition and one-day-spike reduction fields when raw/stabilized score columns are supplied.
- A generic value-count distribution helper only if it preserves current sorting, count type, ratio behavior, and table columns.

Riskier candidates that should wait:

- Unifying public `summary` columns across diagnostics. That would redesign output vocabulary.
- Renaming `window_metrics` to `window_summary` for credit persistence. That would change public keys.
- Replacing `diagnostics`, `diagnostics_by_case`, or `detail_by_case` with one shared key. That would change public API.
- Moving compatibility metadata or diagnostic aliases into YAML. That belongs to Group K or Group I, not H.

## Target-specific vocabulary to preserve

Preserve these public naming choices:

- `raw_credit_*` and `smoothed_credit_*` in credit smoothing.
- `raw_curve_*` and `smoothed_curve_*` in curve smoothing.
- `without_threshold`, `with_threshold`, and `due_to_threshold` vocabulary in move-driver threshold.
- `raw_*` versus `stabilized_*` vocabulary in curve stabilization.
- `window_metrics` and the five specialized credit persistence behavior tables.
- `diagnostics_by_case` for curve stabilization and `diagnostics` for credit persistence.
- `yield_move_driver` public output vocabulary in curve stabilization detail, despite the internal component name `curve_move_driver`.

## Helpers to retain for Groups I/J/K

Retain for Group I schema cleanup:

- `_resolve_rule_mapped_stance_schema(...)`
- `_resolve_rule_mapped_stabilization_config(...)`
- schema-side rule-mapped validation in `module1_schema.py`

Retain for Group J credit adjustment:

- `_build_rule_mapped_stance_score_breakdown(...)`
- `_rule_mapped_adjusted_row(...)`
- credit adjustment metadata/output handling

Retain for Group K compatibility metadata:

- `_RULE_MAPPED_DIAGNOSTIC_COMPAT`
- `_derive_rule_mapped_diagnostic_spec_from_context(...)`
- `_resolve_rule_mapped_diagnostic_config(...)`

Retain during Group H:

- Existing public compare methods and result keys.
- `_series_mismatch_mask(...)`, `_count_series_changes(...)`, `_count_one_day_spikes(...)`, and `_curve_dominant_value(...)` until replacements are proven strictly equal.

## Recommended H2/H3/H4 split

H2 should implement small private count/window helpers only:

- Add helpers for ratio handling, comparable mean absolute difference, mismatch counts, and inclusive window slicing.
- Use focused equality checks against current credit and curve input-smoothing outputs.
- Avoid case-table migration in H2 unless the helper is purely mechanical.

H3 should migrate selected diagnostics:

- Start with `compare_credit_input_smoothing_effect(...)` and `compare_curve_input_smoothing_effect(...)` because their summary/window patterns are closest.
- Then consider the curve stabilization bucket/score-distribution loops if a helper can preserve exact columns and ordering.
- Keep move-driver threshold and credit persistence public vocabulary unchanged.

H4 should clean up leftovers only after migration:

- Remove old local helper closures or private functions only when `rg` confirms no remaining callers.
- Do not remove public wrappers or compatibility helpers.

## Behavior-preservation requirements for future H PRs

Future H PRs should capture before/after outputs and compare:

- result keys for every flag combination;
- every DataFrame column list and column order;
- every DataFrame value;
- dict keys for `detail_by_case`, `diagnostics_by_case`, and `diagnostics`;
- every per-case detail/diagnostic DataFrame column list and values;
- default case id order;
- default window id order;
- behavior when `include_detail=False`;
- behavior when `include_detail=True`;
- behavior when `include_diagnostics=False`;
- behavior when `include_diagnostics=True`.

Exact outputs to compare:

- `compare_credit_input_smoothing_effect(include_detail=False/True)`
- `compare_curve_input_smoothing_effect(include_detail=False/True)`
- `compare_curve_move_driver_threshold_effect(include_detail=False/True)`
- `compare_curve_positioning_stabilization_cases(include_diagnostics=False/True)`
- `compare_credit_stance_persistence_cases(include_diagnostics=False/True)`, if runtime cost remains acceptable
- `compare_horizon_cases(...)` only for the output modes touched by a future PR

## Commands run

- `git status --short --branch`
- `git log --oneline -5`
- `git fetch --prune origin`
- `git branch -r --list 'origin/codex/session/*'`
- `git branch -r --list 'origin/codex/task/*'`
- `git checkout codex/session/260629_1306`
- `git pull --ff-only origin codex/session/260629_1306`
- `git checkout -b codex/task/260630_2028_h1_summary_display_audit`
- `rg -n "def compare_.*\\(" module1.py`
- `rg -n "summary|window_summary|detail_by_case|diagnostics_by_case|bucket_transition_summary|score_distribution" module1.py`
- `rg -n "_summary_row|_window_row|_count_series_changes|_count_one_day_spikes|_series_mismatch_mask|_dominant" module1.py`
- `rg -n "compare_credit_input_smoothing_effect|compare_curve_input_smoothing_effect|compare_curve_move_driver_threshold_effect|compare_curve_positioning_stabilization_cases|compare_credit_stance_persistence_cases" module1.py`
- `sed -n` inspections of relevant `module1.py` sections
- `FRED_API_KEY=dummy poetry run python - <<'PY' ...` runtime inspection for the suggested diagnostics

## Limitations and checks not run

- No production behavior validation was required because this is audit-only.
- No Python syntax check was required because no Python files were modified.
- Runtime inspection for `compare_horizon_cases(...)` was not run because it is a batch historical review diagnostic and can be materially more expensive; its contract was inspected statically.
- Runtime inspection used `FRED_API_KEY=dummy` because the environment did not provide a real key; the inspected diagnostics completed against local data without requiring a successful FRED request.
- No model outputs changed because this PR only adds this report.
