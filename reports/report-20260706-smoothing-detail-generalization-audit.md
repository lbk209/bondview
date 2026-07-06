# Smoothing Detail Generalization Audit

Date: 2026-07-06

## Executive Recommendation

Preferred path: replace `_credit_input_smoothing_effect_detail(...)` and
`_curve_input_smoothing_effect_detail(...)` with one shared rule-mapped
input-smoothing detail helper, but keep the existing credit and curve summary-row
helpers for a separate task.

The shared detail helper is feasible because both targets now use the same
rule-mapped stance reconstruction path and the existing rule-mapped diagnostic
spec already exposes the YAML-declared source score columns, final score column,
stance column, strength column, raw/stabilized state output columns, and
component metadata. The implementation should preserve the current public detail
column names through an explicit old-to-new mapping layer or through a
target-specific display-prefix hook.

Fallback path if a full shared helper feels too broad: keep separate detail
helpers and first remove only the hard-coded YAML-derived score/stance references
by resolving component score outputs and stance outputs from
`module1_config.yaml` and `RuleMappedDiagnosticSpec`.

## Evidence From Current Code

Relevant functions:

| function/helper | location | notes |
|---|---:|---|
| `compare_smoothing_effect(...)` | `module1.py:7523` | Public dispatcher; still branches separately for credit and curve detail and summary-row helpers. |
| `_credit_input_smoothing_effect_detail(...)` | `module1.py:7659` | Builds credit detail with hard-coded score, stance, strength, and special source feature columns. |
| `_curve_input_smoothing_effect_detail(...)` | `module1.py:8001` | Builds curve detail; already uses rule-mapped spec for stance outputs, but still hard-codes component score output names and display columns. |
| `_credit_input_smoothing_summary_row(...)` | `module1.py:7719` | Summary metrics depend on current credit detail column names. |
| `_curve_input_smoothing_summary_row(...)` | `module1.py:8081` | Summary metrics depend on current curve detail column names and aligned-pair change logic. |
| `_recalculate_component_scores_for_input_preparation_diagnostic(...)` | `module1.py:1925` | Already reconstructs raw component score columns from component config using `score.output` with a prefix. |
| `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(...)` | `module1.py:1995` | Already reconstructs raw rule-mapped stance from raw component scores using rule-mapped config/spec. |
| `_prepared_filtered_input_columns(...)` | `module1.py:6501` | Builds prepared/filtered diagnostic input columns from config-driven prepared-input diagnostics. |
| `_resolve_rule_mapped_diagnostic_config(...)` | `module1.py:6742` | Resolves target rule-mapped context. |
| `_derive_rule_mapped_diagnostic_spec_from_context(...)` | `module1.py:6777` | Produces `RuleMappedDiagnosticSpec`, including source score columns and stance output columns. |

### Hard-Coded YAML-Derived Score Outputs

`_credit_input_smoothing_effect_detail(...)` hard-codes these YAML-derived score
output names:

- `module1.py:7691`: `detail["smoothed_credit_spread_change_score"] = self.scores["credit_spread_change_score"]`
- `module1.py:7694`: `detail["smoothed_credit_spread_state_score"] = self.scores["credit_spread_state_score"]`
- `module1.py:7703`: `detail["raw_credit_stance_score"] = raw_stance["score"]`
- `module1.py:7704`: `self.exposure_stance["credit_stance_score"]`

The first two correspond to `data/module1_config.yaml:259` and `:292` component
`score.output`. The stance score corresponds to `data/module1_config.yaml:768`
and `:871`.

`_curve_input_smoothing_effect_detail(...)` hard-codes these component score
output names:

- `module1.py:8054`: `self.scores["curve_change_score"]`
- `module1.py:8055`: `self.scores["curve_state_score"]`
- `module1.py:8056`: `self.scores["curve_move_driver_score"]`

These correspond to `data/module1_config.yaml:414`, `:458`, and `:515`.

The curve helper does not hard-code the final stance score/label/strength lookup;
it resolves those through `RuleMappedDiagnosticSpec` at `module1.py:8019-8027`
and then indexes `self.exposure_stance` with `score_output`, `stance_output`, and
`strength_output` at `module1.py:8065-8077`.

### Other Hard-Coded YAML-Derived Names

Credit helper:

- Feature/source columns are hard-coded: `baa10y_change`, `baa10y`, and
  `baa10y_level` at `module1.py:7679-7684`. These are YAML-derived raw/feature
  names from `data/module1_config.yaml:261` and `:294`, plus the raw data column.
- Stance output columns are hard-coded: `credit_stance_score`,
  `credit_stance`, and `credit_stance_strength` at `module1.py:7704-7715`.
- Detail display column names are hard-coded around the target vocabulary, such
  as `raw_credit_stance_score`, `smoothed_credit_stance_score`, and
  `credit_stance_score_diff`.

Curve helper:

- Component names are resolved from config with
  `_diagnostic_component_names_for_target(target)` and
  `_score_input_features_for_diagnostic_components(...)`, so the feature/source
  side is more generic than credit.
- Stance output names come from `RuleMappedDiagnosticSpec`, not literals.
- Detail display column names are still hard-coded, such as
  `raw_curve_positioning_score`, `smoothed_curve_positioning_score`, and
  `score_diff`.

Summary-row helpers:

- Both summary-row helpers hard-code current detail column names. That is not
  directly a YAML-derived lookup problem, but it is a current-output-contract
  issue. Any detail generalization that changes detail columns must either update
  summary-row helpers with a mapping or preserve the old columns exactly.

## Feasibility Assessment

Genuinely shared detail construction:

- prerequisite checks for `features`, `scores`, `exposure_stance`, component
  config, and stance config;
- resolving the rule-mapped target context/spec;
- recalculating raw component scores with
  `_recalculate_component_scores_for_input_preparation_diagnostic(...)`;
- building prepared/filtered input columns with `_prepared_filtered_input_columns(...)`;
- reconstructing raw rule-mapped stance with
  `_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(...)`;
- adding smoothed component scores from `self.scores` by iterating
  `spec.score_input_cols`;
- adding raw and smoothed final stance score, stance label, and strength label
  from `raw_stance` and `self.exposure_stance`;
- computing score difference as smoothed final score minus raw final score.

Target-specific parts that remain:

- Detail display naming. Current credit output uses `credit_stance` in final
  stance columns, while current curve output uses `curve_positioning`.
- Component score display names currently include target-specific prefixes such
  as `smoothed_credit_spread_change_score` and
  `smoothed_curve_move_driver_score`.
- Credit adds special raw/source context columns (`baa10y_change`, `baa10y`) that
  are not covered by the generic curve feature loop. These could be replaced by a
  config-driven source-feature loop plus an optional raw-data source hook for
  `baa10y`.
- Summary semantics differ slightly: credit uses `_changed_count_for_valid_pairs`
  for changed counts, while curve uses `_changed_count_for_aligned_pairs`.

Conclusion:

A shared detail helper is cleanly feasible if it accepts a small target profile
or derives one from `RuleMappedDiagnosticSpec` plus optional display-name rules.
The hard part is not the data calculation; it is preserving existing diagnostic
column names and summary-row contracts.

## Proposed Implementation Plan

1. Add a private helper such as `_rule_mapped_input_smoothing_effect_detail(target, profile=None)`.
2. Resolve `context` and `spec` with the existing rule-mapped diagnostic helpers.
3. Build raw component scores with `_recalculate_component_scores_for_input_preparation_diagnostic(spec.target, apply_input_preparation=False, output_prefix="raw_")`.
4. Build source/prepared/filtered input columns from config. For credit, either:
   - keep a small hook that adds `baa10y` from raw data, or
   - defer that source-context cleanup and preserve it in a target profile.
5. Add smoothed component score columns by iterating `spec.score_input_cols`, not by indexing literal score names.
6. Add raw/smoothed final stance score, stance label, and strength from `raw_stance` plus `spec.final_score_col`, `spec.stance_label_col`, and `spec.strength_label_col`.
7. Preserve old detail column names through an explicit mapping:
   - `credit_stance_score` -> `smoothed_credit_stance_score`
   - raw stance `score` -> `raw_credit_stance_score`
   - `curve_positioning_score` -> `smoothed_curve_positioning_score`
   - raw stance `score` -> `raw_curve_positioning_score`
   - component score outputs should keep current `raw_...` and `smoothed_...` names.
8. Route `compare_smoothing_effect(...)` through the shared detail helper for both credit and curve, but keep `_credit_input_smoothing_summary_row(...)` and `_curve_input_smoothing_summary_row(...)` initially.
9. Validate exact equality against the current implementation for credit and curve with explicit windows, comparing `summary`, `window_summary`, and `detail`.

Validation strategy:

- Run `python -m py_compile module1.py`.
- Use local data to compare old-vs-new credit and curve outputs for:
  - explicit legacy windows;
  - historical-context default windows;
  - `include_detail=True` and `include_detail=False`.
- Compare DataFrames with `pandas.testing.assert_frame_equal(..., check_dtype=True)`.
- Confirm no changes to scoring, labels, stance calculation, smoothing parameters,
  historical review scoring, or model outputs.

## Dispatch Duplication In `compare_smoothing_effect(...)`

`compare_smoothing_effect(...)` currently has a small target branch:

- credit -> `_credit_input_smoothing_effect_detail(...)` and `_credit_input_smoothing_summary_row(...)`;
- curve -> `_curve_input_smoothing_effect_detail(...)` and `_curve_input_smoothing_summary_row(...)`.

This can be reduced in the same implementation task if the shared detail helper
is introduced, but only for detail construction. The summary-row function should
remain target-specific in the first implementation because its output metrics,
changed-count helper, and detail column names are part of the public diagnostic
contract.

Minimal safe dispatch cleanup:

- replace the detail-builder branch with one shared detail helper;
- keep a small mapping from target to summary-row helper;
- leave not-applicable and smoothing-layer availability logic unchanged.

## Current Diagnostic Meaning And Column Mapping

A shared helper can preserve current diagnostic meaning and values if it preserves
the current detail column contract. If the implementation chooses normalized
generic columns internally, it must map them back before returning public detail.

Important old-to-new mapping to validate:

| current public detail column | config/spec source |
|---|---|
| `raw_credit_spread_change_score` | `raw_` + `credit_spread_change_score` from credit `spec.score_input_cols` |
| `smoothed_credit_spread_change_score` | `credit_spread_change_score` from credit `spec.score_input_cols` |
| `raw_credit_spread_state_score` | `raw_` + `credit_spread_state_score` from credit `spec.score_input_cols` |
| `smoothed_credit_spread_state_score` | `credit_spread_state_score` from credit `spec.score_input_cols` |
| `raw_credit_stance_score` | raw reconstructed stance score for credit |
| `smoothed_credit_stance_score` | credit `spec.final_score_col` |
| `raw_credit_stance` | raw reconstructed stance direction for credit |
| `smoothed_credit_stance` | credit `spec.stance_label_col` |
| `raw_credit_stance_strength` | raw reconstructed stance strength for credit |
| `smoothed_credit_stance_strength` | credit `spec.strength_label_col` |
| `raw_curve_change_score` | `raw_` + `curve_change_score` from curve `spec.score_input_cols` |
| `smoothed_curve_change_score` | `curve_change_score` from curve `spec.score_input_cols` |
| `raw_curve_state_score` | `raw_` + `curve_state_score` from curve `spec.score_input_cols` |
| `smoothed_curve_state_score` | `curve_state_score` from curve `spec.score_input_cols` |
| `raw_curve_move_driver_score` | `raw_` + `curve_move_driver_score` from curve `spec.score_input_cols` |
| `smoothed_curve_move_driver_score` | `curve_move_driver_score` from curve `spec.score_input_cols` |
| `raw_curve_positioning_score` | raw reconstructed stance score for curve |
| `smoothed_curve_positioning_score` | curve `spec.final_score_col` |
| `raw_curve_positioning` | raw reconstructed stance direction for curve |
| `smoothed_curve_positioning` | curve `spec.stance_label_col` |
| `raw_curve_positioning_strength` | raw reconstructed stance strength for curve |
| `smoothed_curve_positioning_strength` | curve `spec.strength_label_col` |

## `_target_smoothing_layers(...)` Assessment

`_target_smoothing_layers(...)` is appropriately config-derived: it inspects
target-group components and reports whether component configs declare
`score.input_preparation.smoothing` or `score.smoothing`.

It still feels broader than the implemented diagnostic paths because it can
report score-level smoothing for duration, while `compare_smoothing_effect(...)`
currently returns `not_implemented` for score-level comparison. That is acceptable
if it is treated strictly as an availability helper, not as proof that a
diagnostic implementation exists for every available layer.

A future implementation could make this clearer by separating:

- `_target_smoothing_layers(...)`: config-declared smoothing availability;
- `_implemented_smoothing_diagnostic_layers(...)`: diagnostic implementation coverage.

That separation is not required for the detail-generalization task.

## Non-Goals

- Do not change scoring.
- Do not change labels.
- Do not change stance calculation.
- Do not change smoothing parameters.
- Do not change model outputs.
- Do not change historical review scoring.
- Do not change decision logic.

## Validation

Commands run:

```bash
rg -n "self\\.scores\\[" module1.py
rg -n "_credit_input_smoothing_effect_detail|_curve_input_smoothing_effect_detail|compare_smoothing_effect" module1.py
rg -n "score:|output:" data/module1_config.yaml
rg -n "_recalculate_component_scores_for_input_preparation_diagnostic|_reconstruct_rule_mapped_stance_for_input_preparation_diagnostic|_prepared_filtered_input_columns|_derive_rule_mapped_diagnostic_spec_from_context|_resolve_rule_mapped_diagnostic_config|RuleMappedDiagnosticSpec" module1.py
nl -ba module1.py | sed -n '6200,6350p'
nl -ba module1.py | sed -n '6348,6485p'
nl -ba module1.py | sed -n '6485,6675p'
nl -ba module1.py | sed -n '7410,8178p'
nl -ba data/module1_config.yaml | sed -n '250,320p'
nl -ba data/module1_config.yaml | sed -n '760,875p'
nl -ba data/module1_config.yaml | sed -n '405,530p'
nl -ba data/module1_config.yaml | sed -n '900,1030p'
```

No Python files, schema files, or YAML files were changed. No production syntax
validation was required for this audit-only report.
