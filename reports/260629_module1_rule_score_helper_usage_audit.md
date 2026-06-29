# Module 1 Rule-Score Helper Usage Audit

Date: 2026-06-29

## Scope

Audit-only review of target-specific rule-score parsing, lookup, and rule-row helpers in Module 1.

Primary functions audited:

- `_curve_positioning_rule_scores`
- `_curve_positioning_rule_score`
- `_duration_rule_scores`
- `_credit_spread_rule_scores`
- `_credit_spread_rule_row_from_states`

No production code, config, schema, diagnostics, or YAML was changed.

## Recommendation

Split the next cleanup.

1. Do not start with target-specific smoothing/input-preparation reconstruction helpers.
2. Treat production and trace rule-score behavior as already generic for duration, credit, and curve through `_build_rule_mapped_stance_score_breakdown(...)`.
3. Defer the remaining target-specific curve and credit rule-score helper cleanup to the smoothing/input-preparation diagnostic cleanup, because their active use is diagnostic reconstruction rather than production stance calculation.

Recommended conclusion by helper:

| Function | Status | Active usage classification | Recommendation |
| --- | --- | --- | --- |
| `_curve_positioning_rule_scores` | Active | Target-specific diagnostic reconstruction | Defer to smoothing/input-preparation diagnostic cleanup |
| `_curve_positioning_rule_score` | Active | Target-specific diagnostic reconstruction | Defer to smoothing/input-preparation diagnostic cleanup |
| `_duration_rule_scores` | Not present | Dead / already removed | No implementation needed |
| `_credit_spread_rule_scores` | Active | Credit smoothing diagnostic reconstruction only | Defer to smoothing/input-preparation diagnostic cleanup |
| `_credit_spread_rule_row_from_states` | Active | Credit smoothing diagnostic reconstruction only; retains credit adjustment mechanics for that reconstruction | Defer to smoothing/input-preparation diagnostic cleanup |

## Generic Rule-Mapped Baseline

Current production stance calculation for `curve_positioning_stance`, `duration_rule_stance`, and `credit_spread_stance` runs through `_build_rule_mapped_stance_score_breakdown(...)`.

Relevant generic mechanics already exist:

- `_parse_rule_scores_n_parts` parses configured `rule_mapped.rule_scores` into tuple keys.
- `_rule_case_from_states` builds rule-case strings.
- `_lookup_rule_score` handles tuple lookup and missing-state handling.
- `_build_rule_mapped_stance_score_breakdown(...)` classifies/stabilizes states or buckets, builds rule cases, looks up base scores, and applies configured credit adjustments through `_rule_mapped_adjusted_row(...)`.

Production stance dispatch in `_calculate_exposure_stance_score(...)` uses `_build_rule_mapped_stance_score_breakdown(...)` for:

- `curve_positioning_stance`
- `duration_rule_stance`
- `credit_spread_stance`

Therefore, the audited target-specific helpers are not in the active production stance calculation path.

## Function Inventory And Call-Site Map

### `_curve_positioning_rule_scores`

Definition: `module1.py:1281`

Active call sites:

- `module1.py:7985` inside `_curve_positioning_score_from_component_scores(...)`

Downstream call chain:

- `_curve_positioning_score_from_component_scores(...)`
- `compare_curve_input_smoothing_effect(...)` through `_curve_input_smoothing_effect_detail(...)`
- `compare_curve_move_driver_threshold_effect(...)`

Classification:

- Target-specific smoothing/input-preparation diagnostic reconstruction path.
- Not active production stance calculation.
- Not needed by generic trace diagnostics; `trace_stance_score("curve_positioning", ...)` uses `_trace_rule_mapped_stance_score(...)` and `_build_rule_mapped_stance_score_breakdown(...)`.

Recommendation:

- Defer to smoothing/input-preparation diagnostic cleanup.
- Replacing this now with `_parse_rule_scores_n_parts` would be mechanically possible, but likely wasted if the target-specific reconstruction path is later replaced by a generic diagnostic reconstruction path.

### `_curve_positioning_rule_score`

Definition: `module1.py:2427`

Active call sites:

- `module1.py:7994` inside `_curve_positioning_score_from_component_scores(...)`

Downstream call chain:

- `_curve_positioning_score_from_component_scores(...)`
- `compare_curve_input_smoothing_effect(...)` through `_curve_input_smoothing_effect_detail(...)`
- `compare_curve_move_driver_threshold_effect(...)`

Classification:

- Target-specific smoothing/input-preparation diagnostic reconstruction path.
- Duplicates generic lookup behavior covered by `_lookup_rule_score(...)` and generic rule-case construction.
- Not active production stance calculation.
- Not active generic trace path.

Recommendation:

- Defer to smoothing/input-preparation diagnostic cleanup.
- If cleanup happens before diagnostic replacement, a narrow replacement could call `_lookup_rule_score((curve_change_bucket, curve_state_bucket, yield_move_driver_bucket), rule_scores, context="curve positioning")`, but that still leaves the surrounding target-specific reconstruction path intact.

### `_duration_rule_scores`

Definition: not found in `module1.py`.

Active call sites:

- None.

Classification:

- Dead / already removed from Python code.
- Duration rule scores remain in YAML metadata and are consumed through `exposure_stances.duration.rule_mapped.rule_scores`.
- Production duration stance calculation uses `_build_rule_mapped_stance_score_breakdown(...)`.

Recommendation:

- No implementation needed.
- Do not change YAML or schema as part of this rule-score helper cleanup.

### `_credit_spread_rule_scores`

Definition: `module1.py:2791`

Active call sites:

- `module1.py:7484` inside `_credit_stance_score_from_component_scores(...)`

Downstream call chain:

- `_credit_spread_rule_scores(...)`
- `_credit_stance_score_from_component_scores(...)`
- `_credit_input_smoothing_effect_detail(...)`
- `compare_credit_input_smoothing_effect(...)`

Classification:

- Target-specific smoothing/input-preparation diagnostic reconstruction path.
- Not active production stance calculation.
- Not active generic trace path.
- Still needed only because `compare_credit_input_smoothing_effect(...)` reconstructs raw credit stance scores through target-specific code.

Recommendation:

- Defer to smoothing/input-preparation diagnostic cleanup.
- Generic parsing via `_parse_rule_scores_n_parts(..., expected_parts=2, ...)` is available, but applying it only here would polish a helper chain that should probably disappear or be replaced when the credit smoothing diagnostic becomes generic.

### `_credit_spread_rule_row_from_states`

Definition: `module1.py:3140`

Active call sites:

- `module1.py:7495` inside `_credit_stance_score_from_component_scores(...)`

Downstream call chain:

- `_credit_spread_rule_row_from_states(...)`
- `_credit_stance_score_from_component_scores(...)`
- `_credit_input_smoothing_effect_detail(...)`
- `compare_credit_input_smoothing_effect(...)`

Classification:

- Target-specific smoothing/input-preparation diagnostic reconstruction path.
- Still needed only because the credit smoothing diagnostic reconstructs raw credit stance from raw component scores.
- Contains target-specific credit adjustment behavior via `_credit_spread_state_intensity(...)` and `_adjust_credit_spread_rule_score(...)`.
- Generic production rule-mapped calculation already handles the same adjustment shape through `_rule_mapped_adjusted_row(...)`, but this helper is still the active reconstruction path for the credit smoothing diagnostic.

Recommendation:

- Defer to smoothing/input-preparation diagnostic cleanup.
- Do not delete now because it supports an active public diagnostic.
- Do not generalize now unless the next task explicitly replaces the credit smoothing reconstruction with the generic rule-mapped breakdown mechanics.

## Credit-Only Diagnostic Chain Verification

The suspected chain is confirmed:

```text
_credit_spread_rule_scores
_credit_spread_rule_row_from_states
_credit_stance_score_from_component_scores
_credit_input_smoothing_effect_detail
compare_credit_input_smoothing_effect
```

`_credit_spread_rule_scores` and `_credit_spread_rule_row_from_states` were not found outside this chain.

Conclusion: both should be deferred to smoothing/input-preparation diagnostic cleanup.

## Usage Classification Table

| Call site | Helper | Usage classification | Notes |
| --- | --- | --- | --- |
| `module1.py:7985` | `_curve_positioning_rule_scores` | Target-specific smoothing/input-preparation diagnostic reconstruction | Used only by `_curve_positioning_score_from_component_scores(...)` |
| `module1.py:7994` | `_curve_positioning_rule_score` | Target-specific smoothing/input-preparation diagnostic reconstruction | Used only by `_curve_positioning_score_from_component_scores(...)` |
| `module1.py:8139` | `_curve_positioning_score_from_component_scores` | Target-specific smoothing/input-preparation diagnostic reconstruction | Reconstructs raw curve stance in `_curve_input_smoothing_effect_detail(...)` |
| `module1.py:8388` | `_curve_positioning_score_from_component_scores` | Target-specific diagnostic reconstruction | Computes curve stance without move-driver threshold |
| `module1.py:8396` | `_curve_positioning_score_from_component_scores` | Target-specific diagnostic reconstruction | Computes curve stance with move-driver threshold |
| `module1.py:7484` | `_credit_spread_rule_scores` | Target-specific smoothing/input-preparation diagnostic reconstruction | Used only by `_credit_stance_score_from_component_scores(...)` |
| `module1.py:7495` | `_credit_spread_rule_row_from_states` | Target-specific smoothing/input-preparation diagnostic reconstruction | Used only by `_credit_stance_score_from_component_scores(...)` |
| `module1.py:7609` | `_credit_stance_score_from_component_scores` | Target-specific smoothing/input-preparation diagnostic reconstruction | Reconstructs raw credit stance in `_credit_input_smoothing_effect_detail(...)` |
| `module1.py:7741` | `_credit_input_smoothing_effect_detail` | Public diagnostic | Entry path from `compare_credit_input_smoothing_effect(...)` |
| `module1.py:3229` | `_build_rule_mapped_stance_score_breakdown` | Active production stance calculation path | Used for duration, credit, and curve production stance scores |
| `module1.py:6846` | `_build_rule_mapped_stance_score_breakdown` | Active trace/diagnostic path that should be preserved | Generic rule-mapped trace |
| `module1.py:8551` and `module1.py:8556` | `_build_rule_mapped_stance_score_breakdown` | Active curve stabilization diagnostic path | Already generic; not a target-specific rule-score helper problem |

## Proposed Next Implementation Grouping

### Group 1: No-op or small production/trace cleanup

No primary audited helper appears to need production/trace cleanup now:

- `_duration_rule_scores` is already gone.
- Production and trace rule-score calculation already use generic rule-mapped helpers.
- Curve stabilization diagnostics already use generic rule-mapped breakdowns.

If a small cleanup is desired before smoothing diagnostics, limit it to dead-code deletion only where static inspection confirms no active public diagnostic call sites. Among the primary helpers, only `_duration_rule_scores` is a delete candidate, but it is already absent.

### Group 2: Smoothing/input-preparation diagnostic cleanup

Handle these together:

- `_curve_positioning_rule_scores`
- `_curve_positioning_rule_score`
- `_curve_positioning_score_from_component_scores`
- `_credit_spread_rule_scores`
- `_credit_spread_rule_row_from_states`
- `_credit_stance_score_from_component_scores`
- `_credit_input_smoothing_effect_detail`
- `_curve_input_smoothing_effect_detail`
- `compare_credit_input_smoothing_effect(...)`
- `compare_curve_input_smoothing_effect(...)`
- `compare_curve_move_driver_threshold_effect(...)`, if its alternate-input reconstruction can share the same generic mechanism

Goal: replace target-specific reconstruction engines with a generic metadata-driven rule-mapped reconstruction path, or retire the reconstruction helpers if the diagnostics are redesigned.

## Wasted-Work Risk

Replacing `_credit_spread_rule_scores` with `_parse_rule_scores_n_parts` or `_credit_spread_rule_row_from_states` with `_rule_case_from_states` / `_lookup_rule_score` now would reduce local duplication but leave the target-specific smoothing diagnostic engine in place.

That work is likely to be thrown away if the later smoothing/input-preparation diagnostic cleanup replaces the whole reconstruction path with generic rule-mapped mechanics.

The same applies to `_curve_positioning_rule_scores` and `_curve_positioning_rule_score`: they duplicate generic parsing/lookup behavior, but only inside curve diagnostic reconstruction paths.

## Functions Not To Delete Yet

Do not delete these yet:

- `_curve_positioning_rule_scores`
- `_curve_positioning_rule_score`
- `_credit_spread_rule_scores`
- `_credit_spread_rule_row_from_states`

Reason: each supports active public diagnostics, even though not production stance calculation.

Do not alter these as part of this cleanup:

- `_build_rule_mapped_stance_score_breakdown(...)`
- `_rule_mapped_adjusted_row(...)`
- `_rule_case_from_states(...)`
- `_lookup_rule_score(...)`
- `_parse_rule_scores_n_parts`
- schema validation
- YAML rule-score metadata

## Validation

No production model run was required because this was audit-only and no production code or configuration changed.

## Commands Run

```bash
sed -n '1,260p' /home/lbk/.codex/attachments/f04e6abb-a9cc-4030-a236-0206bd346959/pasted-text.txt
git status --short --branch
git fetch --prune origin
git branch -r --list 'origin/codex/session/*'
date +%y%m%d_%H%M
rg -n "_curve_positioning_rule_scores|_curve_positioning_rule_score|_duration_rule_scores|_credit_spread_rule_scores|_credit_spread_rule_row_from_states|_credit_stance_score_from_component_scores|_credit_input_smoothing_effect_detail|compare_credit_input_smoothing_effect|_parse_rule_scores_n_parts|_rule_case_from_states|_lookup_rule_score|_build_rule_mapped_stance_score_breakdown" module1.py module1_schema.py reports data/module1_config.yaml
rg -n "def _.*rule.*score|def _.*rule.*row|def _.*rule_case|rule_scores|rule_case" module1.py
rg -n "duration_rule_scores|_duration_.*rule|duration_rule" module1.py data/module1_config.yaml reports
rg -n "_curve_positioning_score_from_component_scores|_credit_stance_score_from_component_scores|_credit_spread_rule_scores\\(|_credit_spread_rule_row_from_states\\(|_curve_positioning_rule_scores\\(|_curve_positioning_rule_score\\(" module1.py
rg -n "def _duration_rule_scores|_duration_rule_scores\\(" module1.py
nl -ba module1.py | sed -n '1270,1365p'
nl -ba module1.py | sed -n '1540,1695p'
nl -ba module1.py | sed -n '2200,2438p'
nl -ba module1.py | sed -n '2427,2458p'
nl -ba module1.py | sed -n '2780,3188p'
nl -ba module1.py | sed -n '3188,3250p'
nl -ba module1.py | sed -n '3190,3325p'
nl -ba module1.py | sed -n '7440,7645p'
nl -ba module1.py | sed -n '7645,7765p'
nl -ba module1.py | sed -n '7958,8020p'
nl -ba module1.py | sed -n '8060,8298p'
nl -ba module1.py | sed -n '8300,8410p'
nl -ba module1.py | sed -n '8520,8595p'
nl -ba module1.py | sed -n '8595,8788p'
nl -ba module1.py | sed -n '8788,8860p'
nl -ba data/module1_config.yaml | sed -n '560,760p'
nl -ba data/module1_config.yaml | sed -n '760,890p'
nl -ba data/module1_config.yaml | sed -n '890,1040p'
```
