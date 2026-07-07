# Module 1 Target Bucket/Config Accessors Audit

Date: 2026-06-29

## Scope

Audit-only review of the next Module 1 cleanup target: target-specific bucket/config accessors.

Functions audited:

- `_curve_component_bucket_config`
- `_curve_positioning_required_output_cols`

No production code or configuration was changed.

## Recommendation

Implement now.

Both functions can be removed with narrow call-site replacements:

- Delete `_curve_component_bucket_config` and replace call sites directly with the existing generic `_component_score_bucket_config`.
- Delete `_curve_positioning_required_output_cols` and replace call sites with the existing rule-mapped diagnostic metadata path, preserving output-column names through explicit `rule_mapped` metadata.

The implementation should not add a new generic wrapper.

## Current Function Inventory

### `_curve_component_bucket_config`

Exists at `module1.py:1281`.

Current implementation:

```python
def _curve_component_bucket_config(self, component_name: str) -> dict:
    return self._component_score_bucket_config(component_name)
```

Active call sites:

- `module1.py:2467` and `module1.py:2471` in `_curve_change_candidate_bucket`
- `module1.py:2588` and `module1.py:2592` in `_curve_state_candidate_bucket`
- `module1.py:2629` in `_yield_move_driver_candidate_bucket`
- `module1.py:2677`, `module1.py:2678`, and `module1.py:2679` in `_stabilize_curve_positioning_rule_buckets`
- defensive fallback calls at `module1.py:2687`, `module1.py:2694`, and `module1.py:2701` in `_stabilize_curve_positioning_rule_buckets`
- `module1.py:8374` and `module1.py:8382` in `compare_curve_move_driver_threshold_effect`
- `module1.py:8439` and `module1.py:8447` in `compare_curve_move_driver_threshold_effect`

Status: active thin wrapper.

Classification: pure thin wrapper. It adds no validation, no target-specific semantics, no compatibility behavior, and no error-message specialization beyond whatever `_component_score_bucket_config` already provides.

### `_curve_positioning_required_output_cols`

Exists at `module1.py:7322`.

Active call sites:

- `module1.py:7842` in `_summarize_curve_positioning_stance_logic`
- `module1.py:8118` in `_curve_input_smoothing_effect_detail`

Status: active compatibility accessor.

Classification: compatibility accessor with small additional validation. It reads `score_output`, `stance_output`, and `strength_output` from the curve positioning stance config, verifies those columns exist in `self.exposure_stance`, and returns the three column names. It does not calculate model outputs or encode curve bucket logic.

## Generic Replacement Path

### Bucket config

Use `_component_score_bucket_config(component_name)` directly.

That helper already reads:

```text
component_config["components"][component_name]["score"]["buckets"]
```

and validates that the result is a non-empty mapping. This is the exact behavior currently reached through `_curve_component_bucket_config`.

Do not replace these calls with `_component_bucket_config` as a first choice. `_component_bucket_config` is also generic and currently has the same bucket lookup shape, but its error text is oriented to bucket label classification and it is used by label logic. `_component_score_bucket_config` is the closer existing helper for score/bucket classification paths.

No new helper is needed.

### Output columns

Use the existing rule-mapped diagnostic metadata path:

- `_resolve_rule_mapped_diagnostic_config("curve_positioning")`
- `_derive_rule_mapped_diagnostic_spec_from_context(context)`
- `RuleMappedDiagnosticSpec.final_score_col`
- `RuleMappedDiagnosticSpec.stance_label_col`
- `RuleMappedDiagnosticSpec.strength_label_col`

These derive from explicit config metadata:

- top-level stance fields `score_output`, `stance_output`, `strength_output`
- `rule_mapped.score_output`, `rule_mapped.stance_output`, `rule_mapped.strength_output`

`_resolve_rule_mapped_stance_schema` already requires the `rule_mapped` output fields to match the active stance output fields.

No new helper is needed.

## Output-Column Compatibility

`_curve_positioning_required_output_cols` does protect diagnostic/report output compatibility in the sense that it centralizes the current public curve output column names before summary and smoothing diagnostics use them.

Compatibility does not require keeping the accessor. The explicit metadata source already exists in `data/module1_config.yaml`:

- `exposure_stances.curve_positioning.score_output: curve_positioning_score`
- `exposure_stances.curve_positioning.stance_output: curve_positioning`
- `exposure_stances.curve_positioning.strength_output: curve_positioning_strength`
- matching `exposure_stances.curve_positioning.rule_mapped.*_output` fields

The schema also validates these fields:

- `module1_schema.py:2230` through `module1_schema.py:2248` validate `rule_mapped` output fields and require them to match the active stance outputs.
- `module1_schema.py:2664` through `module1_schema.py:2691` validate top-level stance output names and uniqueness.

Direct generic output resolution is safe if the implementation uses the existing `RuleMappedDiagnosticSpec` fields and retains an explicit local check that the resolved columns exist where the current function performed that check. For `_summarize_curve_positioning_stance_logic`, `trace_stance_score("curve_positioning", ...)` already passes through `_trace_rule_mapped_stance_score`, which checks the same resolved output columns against `ctx.data`. For `_curve_input_smoothing_effect_detail`, keep a local direct check against `self.exposure_stance.columns` or allow the existing column access to fail only if the project accepts less tailored error messages. Prefer preserving the explicit check locally during the cleanup.

## Scope Control

The implementation should not touch:

- rule-score parsing
- state or bucket classification mechanics
- stabilization behavior
- schema validators
- smoothing/input-preparation comparison diagnostics beyond replacing the two audited accessors
- compatibility metadata beyond using the existing output metadata already present in config

No YAML config changes are required.

## Proposed Implementation Plan

1. Delete `_curve_component_bucket_config`.
2. Replace every `_curve_component_bucket_config(...)` call with `_component_score_bucket_config(...)`.
3. Delete `_curve_positioning_required_output_cols`.
4. In `_summarize_curve_positioning_stance_logic`, resolve curve output columns through the existing rule-mapped diagnostic spec:
   - call `_resolve_rule_mapped_diagnostic_config("curve_positioning")`
   - call `_derive_rule_mapped_diagnostic_spec_from_context(context)`
   - use `spec.final_score_col`, `spec.stance_label_col`, and `spec.strength_label_col`
5. In `_curve_input_smoothing_effect_detail`, use the same metadata-backed spec fields for `score_output`, `stance_output`, and `strength_output`; preserve the current explicit `self.exposure_stance` column check locally if retaining the current error behavior is important.

Likely files to change:

- `module1.py`

Likely files not to change:

- `data/module1_config.yaml`
- `module1_schema.py`

## Required Validation For Implementation

Minimum:

```bash
python -m py_compile module1.py
```

Recommended focused smoke checks:

- load Module 1 config
- run config validation if the project exposes a lightweight validator command/function
- run `trace_stance_score("curve_positioning", include_raw_input=False, include_labels=False)` after normal prerequisite calculation
- run `summarize_stance_logic("curve_positioning")` after normal prerequisite calculation
- run `compare_curve_input_smoothing_effect(include_detail=False)` after normal prerequisite calculation
- run `compare_curve_move_driver_threshold_effect(include_detail=False)` after normal prerequisite calculation

Because this cleanup should only replace access paths with equivalent metadata-backed paths, production model scores, bucket labels, stance labels, and stance strength values should not change.

## Risk Assessment

Production output values: low risk if replacements are direct and no classification/scoring/stabilization logic is changed.

Production output columns: should not change because the output column names remain sourced from explicit stance and rule-mapped metadata.

Diagnostic output columns: moderate risk only if `_curve_positioning_required_output_cols` is removed without preserving metadata-backed column resolution and existence checks. Use `RuleMappedDiagnosticSpec` fields to avoid this.

YAML config or schema validation: should not change. If implementation appears to require YAML or schema edits, stop before implementation because that would broaden the task beyond target-specific accessor removal.

Model semantics: should not change.

## Commands Run

```bash
git status --short --branch
git branch --show-current
git log --oneline -5
git fetch --prune origin
git branch -r --list 'origin/codex/session/*'
git branch -r
gh --version
gh auth status
rg -n "_curve_component_bucket_config|_curve_positioning_required_output_cols|_component_bucket_config|_component_bucket_labels|required_output_cols|output_columns|bucket" .
rg --files
rg -n "def _curve_component_bucket_config|_curve_component_bucket_config\\(|def _curve_positioning_required_output_cols|_curve_positioning_required_output_cols\\(" module1.py
rg -n "score_output|stance_output|strength_output|raw_output|stabilized_output|metadata_output" data/module1_config.yaml module1.py module1_schema.py
nl -ba module1.py | sed -n '1260,1305p'
nl -ba module1.py | sed -n '1450,1700p'
nl -ba module1.py | sed -n '1710,1810p'
nl -ba module1.py | sed -n '2140,2365p'
nl -ba module1.py | sed -n '2430,2755p'
nl -ba module1.py | sed -n '6200,6810p'
nl -ba module1.py | sed -n '6795,7310p'
nl -ba module1.py | sed -n '7300,7868p'
nl -ba module1.py | sed -n '7868,8465p'
nl -ba data/module1_config.yaml | sed -n '930,1045p'
nl -ba module1_schema.py | sed -n '2220,2705p'
```

No production model run or behavior validation was required because this was an audit-only task and no production code or configuration changed.
