# Module 1 state/bucket classification helper audit

Date: 2026-06-30

## Scope

Audit-only review of Module 1 target-specific state and bucket classification helpers. No production code, config, schema, diagnostics, YAML, scoring, labels, or model outputs were changed.

Primary helpers requested:

- `_duration_rule_classify_state`
- `_curve_change_bucket`
- `_curve_state_bucket`
- `_yield_move_driver_bucket`
- `_curve_change_candidate_bucket`
- `_curve_state_candidate_bucket`
- `_yield_move_driver_candidate_bucket`
- `_curve_ordered_threshold_buckets`

Related reusable helpers inspected:

- `_threshold_bucket`
- `_score_bucket`
- `_component_bucket_for_score`
- `_rule_mapped_bucket_candidate`
- `_stabilize_state_series`
- `_threshold_hysteresis_candidate`
- `_stabilize_curve_positioning_rule_buckets`

## Executive conclusion

Several target-specific helper names have already disappeared from the active code. `_curve_change_bucket`, `_curve_state_bucket`, and `_yield_move_driver_bucket` have no definitions or call sites in `module1.py`; raw curve bucket classification now calls `_threshold_bucket` or `_score_bucket` directly.

The remaining target-specific candidate helpers are not needed for zero-buffer raw classification, but they still encode persistence/hysteresis candidate behavior for curve bucket stabilization. They can be generalized only if the generic replacement preserves the exact active-state, boundary, buffer, missing-value, and bucket-order semantics.

## Function inventory and recommendations

| Function | Current status | Classification type | Active call sites | Recommendation |
| --- | --- | --- | --- | --- |
| `_duration_rule_classify_state` | Defined in `module1.py`; called in rule-mapped threshold-state raw classification | Threshold state classification | `_build_rule_mapped_stance_score_breakdown` for `classification: threshold_state` inputs | Generalize now with new helper |
| `_curve_change_bucket` | Not defined; no call sites found | Former threshold bucket wrapper, now absent | None | Delete candidate / already effectively removed |
| `_curve_state_bucket` | Not defined; no call sites found | Former threshold bucket wrapper, now absent | None | Delete candidate / already effectively removed |
| `_yield_move_driver_bucket` | Not defined; no call sites found | Former score/categorical bucket wrapper, now absent | None | Delete candidate / already effectively removed |
| `_curve_change_candidate_bucket` | Defined; called by generic rule-mapped bucket stabilization and legacy curve smoothing reconstruction | Threshold bucket hysteresis candidate for three-bucket min/default/max shape | `_rule_mapped_bucket_candidate`; `_stabilize_curve_positioning_rule_buckets` | Defer to stabilization/hysteresis cleanup |
| `_curve_state_candidate_bucket` | Defined; called by generic rule-mapped bucket stabilization and legacy curve smoothing reconstruction | Ordered/range bucket hysteresis candidate | `_rule_mapped_bucket_candidate`; `_stabilize_curve_positioning_rule_buckets` | Defer to stabilization/hysteresis cleanup |
| `_yield_move_driver_candidate_bucket` | Defined; called only by legacy curve smoothing reconstruction | Score/categorical bucket wrapper around `_score_bucket`; ignores active state and hysteresis | `_stabilize_curve_positioning_rule_buckets` | Replace now with existing generic helper if caller remains; delete with caller if obsolete |
| `_curve_ordered_threshold_buckets` | Defined; used only by `_curve_state_candidate_bucket` | Ordered/range bucket metadata normalization | `_curve_state_candidate_bucket` | Retain temporarily with candidate helper, then generalize as support for ordered/range hysteresis |

## Call-site map

### `_duration_rule_classify_state`

Active call site:

- `module1.py` `_build_rule_mapped_stance_score_breakdown`, threshold-state branch. It builds raw state outputs for any rule-mapped input configured with `classification: threshold_state`.

Configured active uses:

- `duration` stance rule-mapped inputs: `duration_preference`, `duration_rate_shock`, `inflation`, `policy`.
- `credit` stance rule-mapped inputs: `credit_spread_change`, `credit_spread_state`.

Usage classification:

- Active production stance/component calculation path. `_calculate_exposure_stance_score` routes `duration_rule_stance`, `credit_spread_stance`, and `curve_positioning_stance` through `_build_rule_mapped_stance_score_breakdown`.
- Active trace/diagnostic path. Rule-mapped diagnostics also call `_build_rule_mapped_stance_score_breakdown`.

Behavior:

- Missing values return `pd.NA`.
- `value >= thresholds["positive"]` returns `buckets["positive"]`.
- `value <= thresholds["negative"]` returns `buckets["negative"]`.
- Other finite values return `buckets["neutral"]`.

Recommendation:

- Generalize now with a helper such as `_threshold_state_from_score(value, thresholds, state_labels)` or `_threshold_state_from_score(value, thresholds, buckets)`.
- The rename/generalization can preserve behavior exactly because the current helper has no duration-specific behavior. Its name is misleading: it is already used by credit rule-mapped raw state classification as well as duration.

### `_curve_change_bucket`, `_curve_state_bucket`, `_yield_move_driver_bucket`

Active call sites:

- None found. No definitions found.

Current replacement paths:

- Curve change raw buckets use `_threshold_bucket`.
- Curve state raw buckets use `_threshold_bucket`.
- Yield-move driver raw buckets use `_score_bucket`.
- Component bucket labels can also flow through `_component_bucket_for_score`, which dispatches to `_threshold_bucket` or `_score_bucket`.

Usage classification:

- Dead or effectively obsolete code names.

Recommendation:

- Treat as delete candidates / already removed.
- No implementation is needed unless stale documentation or tests still reference the old names.

### `_curve_change_candidate_bucket`

Active call sites:

- `_rule_mapped_bucket_candidate`, when `state_input.component_name == "curve_change"`. This is part of the active rule-mapped stance path and diagnostics for curve positioning.
- `_stabilize_curve_positioning_rule_buckets`, an older curve-specific path used by `_curve_positioning_score_from_component_scores`. That path is used by curve input-smoothing comparison/reconstruction diagnostics.

Usage classification:

- Active production stance path through `_build_rule_mapped_stance_score_breakdown` when curve stabilization config uses a non-zero buffer or persistence.
- Active trace/diagnostic path through rule-mapped diagnostics.
- Smoothing/input-preparation diagnostic reconstruction path through `_curve_positioning_score_from_component_scores`.
- Stabilization/hysteresis-only path when `hysteresis_buffer` is non-zero.

Behavior:

- Missing values return `pd.NA`.
- With `hysteresis_buffer == 0.0`, delegates to `_threshold_bucket`.
- With a non-zero buffer, requires exactly one min-only bucket, one max-only bucket, and one default bucket.
- If active in the positive bucket, it persists until value falls below `positive_threshold - buffer`; it can jump directly to the negative bucket only at `value <= negative_threshold - buffer`.
- If active in the negative bucket, it persists until value rises above `negative_threshold + buffer`; it can jump directly to positive only at `value >= positive_threshold + buffer`.
- If active state is neutral or absent, positive entry requires `value >= positive_threshold + buffer`, and negative entry requires `value <= negative_threshold - buffer`.

Recommendation:

- Defer to stabilization/hysteresis cleanup.
- A generic equivalent is feasible: a `threshold_bucket_hysteresis_candidate(value, bucket_config, active_state, hysteresis_buffer)` helper for exactly one upper tail, one lower tail, and one default bucket could reproduce this behavior.
- Do not replace with plain `_threshold_bucket`; that would remove active-state persistence around thresholds when buffers are enabled.

### `_curve_state_candidate_bucket`

Active call sites:

- `_rule_mapped_bucket_candidate`, when `state_input.component_name == "curve_state"`. This is part of the active rule-mapped stance path and diagnostics for curve positioning.
- `_stabilize_curve_positioning_rule_buckets`, the older curve-specific path used by `_curve_positioning_score_from_component_scores` for smoothing comparison/reconstruction diagnostics.

Usage classification:

- Active production stance path through `_build_rule_mapped_stance_score_breakdown` when curve stabilization config uses a non-zero buffer or persistence.
- Active trace/diagnostic path through rule-mapped diagnostics.
- Smoothing/input-preparation diagnostic reconstruction path through `_curve_positioning_score_from_component_scores`.
- Stabilization/hysteresis-only path when `hysteresis_buffer` is non-zero.

Behavior:

- Missing values return `pd.NA`.
- If `active_state is None` or `hysteresis_buffer == 0.0`, delegates to `_threshold_bucket`.
- With an active state and non-zero buffer, creates ordered intervals from configured min/max boundaries.
- If the current value remains inside the active interval expanded by the buffer, it returns the active state.
- Otherwise, it scans ordered bucket boundaries and applies asymmetric buffered boundaries: for the first boundary it subtracts the buffer; for later boundaries it adds the buffer.
- Falls through to the last ordered bucket.

Recommendation:

- Defer to stabilization/hysteresis cleanup.
- A generic equivalent is feasible: an `ordered_threshold_bucket_hysteresis_candidate(value, bucket_config, active_state, hysteresis_buffer)` helper could use normalized ordered intervals plus the same expanded-active-interval and buffered-boundary scan.
- Exact preservation needs focused tests because the current boundary rule is not a generic `_threshold_bucket` call with widened ranges; it has active-state persistence and index-dependent boundary buffer direction.

### `_yield_move_driver_candidate_bucket`

Active call sites:

- `_stabilize_curve_positioning_rule_buckets` only.

Usage classification:

- Smoothing/input-preparation diagnostic reconstruction path.
- Stabilization wrapper in name only; it ignores `active_state` and `hysteresis_buffer`.

Behavior:

- Delegates directly to `_score_bucket`.
- Missing values return `pd.NA` via `_score_bucket`.
- Exact score matches return configured bucket names; unmatched values fall back to the configured default bucket if present.

Recommendation:

- Replace now with existing `_score_bucket` if `_stabilize_curve_positioning_rule_buckets` remains.
- If `_stabilize_curve_positioning_rule_buckets` is later removed or replaced by the generic rule-mapped path, `_yield_move_driver_candidate_bucket` can disappear.
- Generic score/categorical bucket persistence does not need this function. If categorical persistence is needed later, it should be handled by `_stabilize_state_series` with `_score_bucket` as the candidate classifier.

### `_curve_ordered_threshold_buckets`

Active call sites:

- `_curve_state_candidate_bucket` only.

Usage classification:

- Support helper for ordered/range bucket hysteresis.

Behavior:

- Converts bucket config rules into interval metadata with `lower`, `upper`, and inclusivity flags.
- Sorts by lower bound, using negative infinity for open-lower buckets.
- Does not validate contiguity itself; current curve-state contiguity is validated in `module1_schema.py`.

Recommendation:

- Retain temporarily while `_curve_state_candidate_bucket` remains.
- Later generalize into support code for a generic ordered/range bucket hysteresis helper.

## Generic helper candidates

1. `_threshold_state_from_score(value, thresholds, labels)`

   Generic replacement for `_duration_rule_classify_state` and the local `classify_raw_state` closure in credit-specific code, if that code is still retained. Exact behavior should be `pd.NA` for missing, positive boundary inclusive, negative boundary inclusive, neutral otherwise.

2. `_threshold_bucket_hysteresis_candidate(value, bucket_config, active_state, hysteresis_buffer)`

   Generic equivalent for `_curve_change_candidate_bucket`. It should support a one-min-only bucket, one-max-only bucket, and one default bucket. It must preserve direct positive-to-negative and negative-to-positive transition thresholds exactly.

3. `_ordered_threshold_bucket_hysteresis_candidate(value, bucket_config, active_state, hysteresis_buffer)`

   Generic equivalent for `_curve_state_candidate_bucket`. It should normalize ordered min/max intervals, preserve inclusive/exclusive semantics, expand the active interval by the buffer, and reproduce the current boundary scan behavior exactly.

4. `_score_bucket` as the generic categorical candidate classifier

   No new helper is required for `_yield_move_driver_candidate_bucket` unless future categorical hysteresis needs behavior beyond plain score equality plus default fallback.

## Immediate replacement candidates

- `_duration_rule_classify_state`: generalize now with a behavior-identical threshold-state helper.
- `_yield_move_driver_candidate_bucket`: replace with direct `_score_bucket` inside the only remaining caller, if that caller remains.
- `_curve_change_bucket`, `_curve_state_bucket`, `_yield_move_driver_bucket`: no current code to replace; old names are already absent.

## Retain temporarily

- `_curve_change_candidate_bucket`
- `_curve_state_candidate_bucket`
- `_curve_ordered_threshold_buckets`

These should stay until generic hysteresis helpers are implemented with tests that prove identical output.

## Defer to stabilization/hysteresis cleanup

- Generic bucket hysteresis should be handled as a broader cleanup because the current mechanism is only partly generic:
  - `_stabilize_state_series` is generic.
  - `_threshold_hysteresis_candidate` is generic for positive/neutral/negative threshold states.
  - Bucket hysteresis is still curve-specific through `_rule_mapped_bucket_candidate` dispatch on `component_name`.

This means bucket hysteresis is currently treated as curve-only even though the mechanism can be generic.

## Behavior-preservation risks

- Boundary values:
  - `_duration_rule_classify_state` uses inclusive `>= positive` and `<= negative`.
  - `_threshold_bucket` uses inclusive or exclusive bounds based on config keys.
  - `_curve_state_candidate_bucket` applies buffer-adjusted boundaries and respects interval upper inclusivity in the scan.

- Missing values:
  - `_duration_rule_classify_state`, `_threshold_bucket`, `_score_bucket`, and curve candidate helpers return `pd.NA` for missing values.
  - `_stabilize_state_series` does not update active state on missing values.

- Ordered bucket transitions:
  - `_curve_state_candidate_bucket` is not equivalent to simply expanding all intervals and applying `_threshold_bucket`.
  - It first checks active-state expanded interval, then uses an ordered boundary scan.

- Active-state persistence:
  - `_curve_change_candidate_bucket` and `_curve_state_candidate_bucket` depend on `active_state`.
  - `_yield_move_driver_candidate_bucket` ignores active state.

- Hysteresis buffers:
  - Current production config has curve buffers at `0.0`, but diagnostics can pass overrides.
  - Duration uses non-zero buffers through `_threshold_hysteresis_candidate`, not the duration raw classifier.

- Score bucket labels:
  - `_score_bucket` uses exact float equality for configured `score` values.
  - Unmatched values fall back to the configured default bucket if present.

- Categorical bucket labels:
  - `curve_move_driver` bucket labels map multiple categories to positive/negative label keys, while score buckets themselves remain distinct.

- Default/fallback bucket order:
  - `_threshold_bucket` records a default bucket while scanning and returns it only after no explicit rule matches.
  - `_score_bucket` behaves similarly.
  - Generic replacements must not reorder fallback behavior.

## Proposed next implementation grouping

1. Small safe cleanup:
   - Introduce `_threshold_state_from_score`.
   - Replace `_duration_rule_classify_state` call sites.
   - Optionally replace the local credit `classify_raw_state` closure if it remains in live code.
   - Verify with syntax checks and focused equality checks for representative boundary/missing values.

2. Score/categorical wrapper cleanup:
   - Replace `_yield_move_driver_candidate_bucket` with `_score_bucket` in `_stabilize_curve_positioning_rule_buckets`, or delete it as part of removing that legacy diagnostic reconstruction path.

3. Broader stabilization cleanup:
   - Add generic threshold-bucket hysteresis and ordered/range bucket hysteresis helpers.
   - Route `_rule_mapped_bucket_candidate` by `classification` and bucket shape rather than `component_name`.
   - Preserve curve-change and curve-state output with regression tests around buffers, missing values, direct transitions, active-state persistence, and exact boundaries.

4. Schema/config follow-up:
   - If generic ordered/range bucket hysteresis becomes configuration-supported beyond curve state, move curve-specific bucket-shape validation toward generic reusable validation while preserving existing curve constraints.

## Commands run

- `git status --short --branch`
- `git log --oneline -5`
- `git branch --all --list`
- `git fetch --prune origin`
- `git branch -r --list 'origin/codex/session/*'`
- `rg --files`
- `rg -n "_duration_rule_classify_state|_curve_change_bucket|_curve_state_bucket|_yield_move_driver_bucket|_curve_change_candidate_bucket|_curve_state_candidate_bucket|_yield_move_driver_candidate_bucket|_curve_ordered_threshold_buckets|_threshold_bucket|_score_bucket|_stabilize_state_series|_stabilize_rule_scores" module1.py module1_schema.py data/module1_config.yaml`
- `rg -n "def _curve_change_bucket|def _curve_state_bucket|def _yield_move_driver_bucket|_curve_change_bucket\\(|_curve_state_bucket\\(|_yield_move_driver_bucket\\(" module1.py`
- `rg -n "_stabilize_curve_positioning_rule_buckets|_curve_positioning_score_from_component_scores|curve_positioning_stance|_build_rule_mapped_stance_score_breakdown|_duration_rule_classify_state|_curve_change_candidate_bucket|_curve_state_candidate_bucket|_yield_move_driver_candidate_bucket|_curve_ordered_threshold_buckets|_threshold_bucket|_score_bucket" module1.py`
- `rg -n "classification: (threshold_state|threshold_bucket|score_bucket)|state_stabilization|buckets:|state_buckets:" data/module1_config.yaml`
- Targeted `nl -ba ... | sed -n ...` reads of `module1.py`, `module1_schema.py`, and `data/module1_config.yaml`.

## Validation

No production code changed, so no behavior validation or model run was required. No Python syntax check was required because no Python files were modified.
