# Module 1 Hard-Coded Component Score Calculators Audit

Date: 2026-06-26

Scope: remaining cleanup work for Module 1 "Hard-coded component score calculators", focused on curve component scoring and production dispatch.

This is an audit and implementation plan only. No production code or config was changed.

## Current Status

### `_calculate_curve_change_score`

- Status: absent.
- Production path: absent as a named function. `curve_change` now uses `function: weighted_feature_score` in `data/module1_config.yaml`, with a single explicit `curve_10y2y_change` input and `weight: 1.0`.
- Current active implementation: `calculate_component_scores()` dispatches `weighted_feature_score` to `_calculate_weighted_feature_component_score()`, which applies configured feature lookup, input preparation, normalization, weighted sum, smoothing, clipping, and output assignment.
- Remaining hard-coded assumptions: no active production calculator branch hard-codes `curve_10y2y_change`. Diagnostic code still directly lists `curve_10y2y_change` when building curve smoothing review detail.
- Assessment: completed for production scoring. Diagnostic hard-coding is outside the calculator path, but could be included in a later diagnostics cleanup if desired.

### `_calculate_curve_state_score`

- Status: absent.
- Production path: absent as a named function. `curve_state` now uses `function: weighted_feature_score` plus `state_transform: fixed_anchor` in `data/module1_config.yaml`.
- Current active implementation: `calculate_component_scores()` routes fixed-anchor scores to `_calculate_current_state_component_score()`, which supports fixed-anchor `single_feature_score` and fixed-anchor `weighted_feature_score`.
- Remaining hard-coded assumptions: no active production calculator branch hard-codes `curve_10y2y_level`. Diagnostic code still directly lists `curve_10y2y_level` when building curve smoothing review detail. Schema validation still treats `curve_state` as one of the named current-state components and has component-specific curve-state bucket validation.
- PR confirmation: PR #14 effects are visible. The former active `_calculate_curve_state_score` path is gone, and fixed-anchor weighted-feature scoring covers `curve_state`.
- Assessment: completed for production scoring. Remaining component-specific schema validation is intentional validation of current public semantics, not an active score calculator.

### `_calculate_curve_move_driver_score`

- Status: exists in `module1.py`.
- Production path: active. `calculate_component_scores()` dispatches to this method only when `function == "curve_move_driver_score"` and `component_name == "curve_move_driver"`.
- Current responsibilities:
  - Reads ordered `score.inputs` from config, with fallback to hard-coded `["dgs2_change", "dgs10_change"]`.
  - Validates exactly two inputs.
  - Looks up feature series in `self.features`.
  - Applies configured input preparation.
  - Applies `input_preparation.min_abs_value` dead-zone filtering.
  - Looks up `curve_move_driver` bucket config by component name.
  - Calls `_curve_move_driver_score_from_prepared_inputs()`.
- Remaining hard-coded assumptions:
  - Component name `curve_move_driver`.
  - Fallback feature names `dgs2_change` and `dgs10_change`.
  - Bucket config lookup for `curve_move_driver`.
  - Production dispatcher requires both the YAML function name and component name.
- Assessment: unresolved production cleanup target. The method mixes generic mechanics with the domain-specific two-input classifier. It should be reduced or replaced by a generic config-driven dispatcher path while preserving the public YAML function name `curve_move_driver_score`.

### `_curve_move_driver_score_from_prepared_inputs`

- Status: exists in `module1.py`.
- Production path: active through `_calculate_curve_move_driver_score()`. It is also used by curve diagnostics.
- Current responsibilities:
  - Optionally looks up `curve_move_driver` bucket config when not provided.
  - Extracts bucket scores by hard-coded bucket names.
  - Validates exactly one default bucket score.
  - Encodes front-end vs long-end sign combinations:
    - both down -> `bull_parallel`
    - both up -> `bear_parallel`
    - front down / long up -> `front_end_down_long_end_up`
    - front up / long down -> `front_end_up_long_end_down`
    - default -> `mixed_or_unclear`
  - Applies missing-value masking.
- Remaining hard-coded assumptions:
  - Bucket names and their sign semantics.
  - Optional fallback bucket lookup for component `curve_move_driver`.
- Assessment: partially retainable. The sign-combination classifier is likely an irreducible domain primitive unless the project introduces a more general configured two-input sign-classification mechanic. However, fallback bucket lookup should be removed or avoided in production callers, and the retained primitive should consume prepared inputs and bucket metadata only.

## Supporting Paths

### `_calculate_current_state_component_score`

- Status: exists and active.
- Component-specific logic: no `curve_state` special branch remains. The method dispatches by `state_transform: fixed_anchor` and score `function`, not by component name.
- Remaining behavior-sensitive details:
  - Fixed-anchor weighted-feature inputs may omit `weight` only when there is one input and no explicit weights are present. This matches the schema behavior from PR #15.
  - The method is still limited to fixed-anchor current-state scoring, which is appropriate for its helper name.
- Assessment: completed for the `curve_state` cleanup intent.

### `calculate_component_scores`

- Status: exists and active production dispatcher.
- Component-name-based routing:
  - Fixed-anchor scoring is generic through `score.state_transform`.
  - `single_feature_score` and `weighted_feature_score` are generic through `score.function`.
  - `curve_move_driver_score` is still routed with `function == "curve_move_driver_score" and component_name == "curve_move_driver"`.
- Assessment: partially resolved. The dispatcher should remain the production dispatcher, but the `curve_move_driver` component-name guard is the main remaining production dispatch cleanup item.

## Completed Work Confirmation

- `_calculate_curve_state_score` cleanup appears complete for production scoring: the named function is absent, and `curve_state` runs through fixed-anchor generic scoring.
- PR #14 effects are visible:
  - `curve_state` uses `weighted_feature_score` with `state_transform: fixed_anchor`.
  - `_calculate_current_state_component_score()` has a generic fixed-anchor weighted-feature path.
  - No active `_calculate_curve_state_score` function remains.
- PR #15 effects are visible:
  - `module1_schema.py` only requires fixed-anchor weighted input weights when there are multiple inputs or any explicit weight is present.
  - `curve_change` explicitly has `weight: 1.0` under its `weighted_feature_score` input.

## Proposed Implementation Task Groups

### Group 1: Generic categorical two-input score dispatch for `curve_move_driver_score`

Purpose: remove generic mechanics from `_calculate_curve_move_driver_score()` and reduce component-name-based dispatch in `calculate_component_scores()` while keeping the YAML function value `curve_move_driver_score`.

Likely changes:

- Add or extend a generic component-score helper that:
  - accepts any configured categorical two-input score function that maps ordered `score.inputs` to prepared input series;
  - validates input count at runtime;
  - reads features only from `score.inputs`;
  - applies configured input preparation;
  - applies generic `min_abs_value` filtering where validation permits it;
  - passes prepared series and configured buckets to a classifier primitive;
  - lets `calculate_component_scores()` keep smoothing, clipping, and output assignment in the existing shared path.
- Change `calculate_component_scores()` so `curve_move_driver_score` dispatch is function-driven and no longer requires `component_name == "curve_move_driver"` in runtime dispatch.
- Remove the fallback to hard-coded `["dgs2_change", "dgs10_change"]`.

Likely files:

- `module1.py`
- `module1_schema.py` if validation is adjusted to support the generic dispatch shape while preserving current config validity.

Expected validation:

- `python -m py_compile module1.py module1_schema.py`
- strict `load_module1_config()` / `validate_module1_config()` smoke check
- non-destructive score calculation smoke check through `calculate_features()` and `calculate_component_scores()`
- focused equivalence comparison of old vs new `curve_move_driver_score`, labels, and downstream `curve_positioning` outputs on the checked-in raw data

Behavior-output comparison needs:

- Required. This is production scoring. Compare `curve_move_driver_score`, `curve_move_driver_label`, `curve_positioning_score`, `curve_positioning`, and `curve_positioning_strength` before and after.
- Expected result: no output changes.

Independence and coupling:

- Coupled with `_calculate_curve_move_driver_score()` and `calculate_component_scores()` because changing one without the other would leave duplicate or misleading dispatch.
- Independent from `curve_change` and `curve_state` production scoring, which already use generic paths.

Revert risk:

- Likely independently revertible as one task PR if isolated to curve-move-driver runtime dispatch and validation.
- Depends on no prior task beyond the current PR #14/#15 state.
- Should be done before diagnostics cleanup, because diagnostics should call the final production helper shape.

### Group 2: Retain and narrow the curve-move-driver classifier primitive

Purpose: make `_curve_move_driver_score_from_prepared_inputs()` a small domain classifier, not a generic config lookup or production orchestration helper.

Likely changes:

- Require `bucket_config` as an explicit argument.
- Remove fallback lookup of `curve_move_driver` bucket config from the classifier primitive.
- Keep the sign-combination mapping if the public semantics remain unchanged.
- Consider renaming only if the project accepts public-internal cleanup; otherwise leave the name to minimize churn.
- Keep bucket names in the primitive only if schema validation explicitly protects their semantics, or introduce config metadata for sign categories in a later broader migration.

Likely files:

- `module1.py`
- Possibly `module1_schema.py` if adding stricter validation that required bucket names remain available for the retained primitive.

Expected validation:

- `python -m py_compile module1.py module1_schema.py`
- targeted tests or smoke checks for `_curve_move_driver_score_from_prepared_inputs()` with representative prepared inputs and configured buckets
- production score equivalence check after `calculate_component_scores()`
- diagnostics smoke checks for `compare_curve_move_driver_threshold_effect()` because it calls the primitive directly

Behavior-output comparison needs:

- Required. Output should be exactly unchanged for production scores and diagnostics summaries.

Independence and coupling:

- Tightly coupled to Group 1 if Group 1 changes the production caller. It can be included in the same implementation task or done immediately after Group 1.
- It is less safe as a standalone first task because current diagnostics rely on the optional fallback behavior.

Revert risk:

- Revertible independently only if diagnostics are updated in the same PR to pass bucket config explicitly.
- Should happen with or after Group 1.

### Group 3: Diagnostics-only hard-coded curve input cleanup

Purpose: remove remaining hard-coded feature names from curve diagnostics where practical, after production dispatch is generic.

Likely changes:

- Replace direct feature lists in curve smoothing and threshold diagnostics with resolved `score.inputs` and diagnostic `input_roles` from config.
- Ensure diagnostic output column names stay stable unless explicitly approved otherwise.
- Keep compatibility aliases such as `yield_move_driver` only where required for current public diagnostic outputs.

Likely files:

- `module1.py`
- `data/module1_config.yaml` only if existing diagnostic metadata is insufficient, but config changes should be avoided unless necessary.

Expected validation:

- `python -m py_compile module1.py`
- smoke checks for `compare_curve_input_smoothing_effect()` and `compare_curve_move_driver_threshold_effect()`
- output column comparison for diagnostics detail/summary keys

Behavior-output comparison needs:

- Required for diagnostics output columns and values.
- Production model outputs should not change.

Independence and coupling:

- Depends on Group 1/2 if diagnostics should reuse the final prepared-input/classifier mechanics.
- Independent from production score dispatch once Group 1/2 are complete.

Revert risk:

- Revertible independently if limited to diagnostics.
- Lower production risk, but public diagnostic output compatibility should still be checked.

## Retention Candidates

- `_calculate_current_state_component_score()`: retain as a generic fixed-anchor current-state helper. It is not a component-specific calculator in the current code.
- `_curve_move_driver_score_from_prepared_inputs()`: retain only as a small component-level classifier primitive if the project accepts the front-end vs long-end sign-combination logic as irreducible domain behavior. It should not own input lookup, preparation, bucket lookup, smoothing, clipping, or output assignment.
- `_calculate_curve_move_driver_score()`: still a cleanup target. It may remain temporarily as a compatibility wrapper, but should be removed or reduced once generic categorical two-input dispatch exists.
- Curve-specific bucket validators in `module1_schema.py`: likely retain for now as public semantics protection, not as score calculator logic. Generalizing them would be a broader schema migration and is not required for the next cleanup batch.

## Recommendation

Proceed by grouped task units, not method-by-method.

Recommended next batch:

1. Implement Group 1 and Group 2 together if the edit is small enough: generic function-driven dispatch for `curve_move_driver_score`, no hard-coded fallback feature names, and a narrowed classifier primitive that receives prepared inputs and bucket config explicitly.
2. Run before/after production output comparisons for curve component scores, labels, and curve positioning stance outputs.
3. Follow with Group 3 as a separate diagnostics-only task if hard-coded diagnostic feature references remain after the production cleanup.

Rationale: `_calculate_curve_move_driver_score()`, `_curve_move_driver_score_from_prepared_inputs()`, and the `calculate_component_scores()` dispatch branch are tightly coupled. Splitting them method-by-method would create intermediate states that are technically valid but misleading: either generic dispatch still calls a component-specific wrapper, or the classifier remains responsible for config lookup after callers have already resolved config. `curve_change` and `curve_state` do not need implementation tasks for production scoring in this cleanup group.

