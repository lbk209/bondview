# Module 1 remaining cleanup reclassification audit

Date: 2026-06-30

## Scope

Audit/planning only. No production code, config, schema, diagnostics, YAML, or tests were changed.

Source material:

- `module1.py`
- `module1_schema.py`
- `data/module1_config.yaml`
- Existing reports under `reports/`

Goal: reclassify the old migration inventory into dependency-based implementation groups using current code as the source of truth.

## Executive conclusion

The remaining cleanup should not follow the old numbered groups. Current code shows three different kinds of remaining work:

1. Production work: mostly `curve_move_driver_score` component dispatch and the retained front-end/long-end sign classifier.
2. Core rule-mapped work: production and trace stance calculation are already mostly generic, but bucket hysteresis and credit adjustment still use target-specific helpers.
3. Diagnostic work: many old rule-score, stabilization, summary, and input-smoothing helpers now exist only because public diagnostics reconstruct alternate scenarios with target-specific paths.

Compatibility metadata should remain a separate late group. `_RULE_MAPPED_DIAGNOSTIC_COMPAT` is active in public rule-mapped diagnostics and should be revisited after diagnostic APIs settle, not migrated into YAML now.

## Dependency Groups

| Group | Name | Purpose |
| --- | --- | --- |
| A | Completed / no-op / already removed | Functions already deleted, generalized, or absent |
| B | Safe small cleanup | Narrow wrapper removal only when caller is not likely to be replaced soon |
| C | Production component calculation cleanup | Component score dispatch, config-driven scoring, irreducible component primitives |
| D | Rule-mapped production/trace core cleanup | Active production stance and trace calculation paths |
| E | Stabilization, hysteresis, and persistence cleanup | Threshold-state, ordered/range bucket, and score-bucket persistence |
| F | Smoothing/input-preparation and parameter-effect diagnostics cleanup | Raw-vs-prepared reconstruction and config override recalculation diagnostics |
| G | Stabilization-case comparison diagnostics cleanup | Curve/credit stabilization case and window comparisons |
| H | Summary/display diagnostics cleanup | Rule-mapped summaries, label reconstruction, value counts, window summaries |
| I | Schema and validator cleanup | Generic validation aligned with final generic mechanisms |
| J | Credit adjustment generalization or plugin decision | Credit intensity and adjustment formula contract |
| K | Compatibility metadata audit / cleanup | Public diagnostic/report compatibility metadata |

## Old Inventory to New Group Mapping

| Old area | New group(s) | Current status |
| --- | --- | --- |
| Thin wrappers around generic helpers | A, B, K | Most named wrappers are absent or already generalized. Compatibility metadata remains active. |
| Hard-coded component score calculators | A, C | Curve change/state calculators are absent; curve move-driver remains production-critical. |
| Target-specific bucket/config accessors | A | `_curve_component_bucket_config` and `_curve_positioning_required_output_cols` are absent in current code. |
| Target-specific rule-score parsing/lookup/case construction | A, F, J | Production uses generic rule-mapped core; remaining target helpers are diagnostic reconstruction or credit adjustment support. |
| Target-specific state/bucket classification | A, D, E, F | `_threshold_state_from_score` is now generic; curve bucket candidates belong to hysteresis cleanup. |
| Target-specific stabilization/persistence | E, F, G | Generic series mechanics exist; curve bucket and legacy credit/curve reconstruction remain. |
| Target-specific state/bucket schema helpers | A, D, F, J | Several old duration helpers are absent; credit accessors remain for diagnostic reconstruction and adjustment. |
| Credit adjustment mechanics | D, J | Active in production rule-mapped adjustment and diagnostic reconstruction. Needs explicit generic/plugin decision. |
| Target-specific validators | I, J | Active validation still protects current semantics; genericization should follow runtime mechanism decisions. |
| Smoothing/input-preparation diagnostics | F | Active public diagnostics; should be genericized as a unit, not helper-by-helper. |
| Stabilization-case diagnostics | G | Active public diagnostics; should be genericized after core hysteresis behavior is generic. |
| Summary/display diagnostics | H, K | Some generic rule-mapped summaries exist; credit/curve display helpers remain. |
| Compatibility metadata | K | Active; keep until diagnostic API cleanup defines what compatibility must remain. |

## Function Inventory

| Item | Exists now | Active call-site status | Group | Classification / recommendation |
| --- | --- | --- | --- | --- |
| `_curve_change_bucket` | No | None | A | Completed/no-op; do not reintroduce. |
| `_curve_state_bucket` | No | None | A | Completed/no-op; do not reintroduce. |
| `_yield_move_driver_bucket` | No | None | A | Completed/no-op; do not reintroduce. |
| `_prepared_input_column_name` | No | None | A | Completed/no-op; current code uses `_diagnostic_input_column_name`. |
| `_filtered_input_column_name` | No | None | A | Completed/no-op; current code uses diagnostic input metadata helpers. |
| `_prepared_filtered_input_specs` | No | None | A | Completed/no-op; current code derives prepared/filtered specs through diagnostic helpers. |
| `_rule_mapped_bucket_classification_from_score` | Yes | Schema and runtime rule-mapped classification checks | D/I | Already generic; retain. |
| `TargetResolution.is_component_level` | No | None | A | Previously removed; do not reintroduce. |
| `TargetResolution.is_stance_level` | No | None | A | Previously removed; do not reintroduce. |
| `_calculate_duration_preference_score` | No | None | A | Previously removed; do not reintroduce. |
| `_curve_component_bucket_labels` | No | None | A | Previously removed; do not reintroduce. |
| `_dependencies_for_target` | No | None | A | Previously removed; do not reintroduce. |
| `_curve_positioning_rule_case` | No | None | A | Previously removed; current code uses configured rule-case output columns. |
| `_filter_curve_diagnostics_window` | No | None | A | Previously removed; do not reintroduce. |
| `_derive_rule_mapped_diagnostic_spec` | No | None | A | Exact old name absent; current `_derive_rule_mapped_diagnostic_spec_from_context` is active. |
| `_derive_rule_mapped_diagnostic_spec_from_context` | Yes | Rule-mapped trace, diagnose, summarize, smoothing diagnostics | K/H | Active compatibility/diagnostic helper; retain until diagnostic API cleanup. |
| `_calculate_weighted_component_score` | No | None | A | Old name absent; current helpers are `_calculate_weighted_feature_component_score` and `_weighted_sum_score`. |
| `_calculate_weighted_stance_score` | No | None | A | Old name absent; current path is `_build_weighted_stance_score_breakdown`. |
| `_calculate_curve_positioning_stance_score` | No | None | A | Old wrapper absent; production uses `_build_rule_mapped_stance_score_breakdown`. |
| `_calculate_duration_rule_stance_score` | No | None | A | Old wrapper absent; production uses `_build_rule_mapped_stance_score_breakdown`. |
| `_calculate_credit_spread_stance_score` | No | None | A | Old wrapper absent; production uses `_build_rule_mapped_stance_score_breakdown`. |
| `_calculate_curve_change_score` | No | None | A | Completed for production; curve change uses `weighted_feature_score`. |
| `_calculate_curve_state_score` | No | None | A | Completed for production; curve state uses fixed-anchor generic scoring. |
| `_calculate_curve_move_driver_score` | Yes | Active production component scoring and raw diagnostic reconstruction | C | Production-critical cleanup; keep YAML function value but reduce generic orchestration in this wrapper. |
| `_curve_move_driver_score_from_prepared_inputs` | Yes | Production via `_calculate_curve_move_driver_score`; curve diagnostics | C/F | Retention candidate as irreducible sign-classifier primitive; remove orchestration/fallback behavior only with equality tests. |
| `_calculate_current_state_component_score` | Yes | Active fixed-anchor scoring and diagnostics | C | Already generic enough; retain. |
| `calculate_component_scores` | Yes | Main production dispatcher | C | Production-critical; remaining issue is `curve_move_driver_score` dispatch shape. |
| `_curve_component_bucket_config` | No | None | A | Completed/no-op; current code uses `_component_score_bucket_config`. |
| `_curve_positioning_required_output_cols` | No | None | A | Completed/no-op; current code uses rule-mapped diagnostic spec fields. |
| `_curve_positioning_rule_scores` | Yes | Only `_curve_positioning_score_from_component_scores` diagnostic reconstruction | F | Do not implement alone; replace with generic reconstruction when smoothing diagnostics are genericized. |
| `_curve_positioning_rule_score` | Yes | Only `_curve_positioning_score_from_component_scores` diagnostic reconstruction | F | Do not implement alone; caller likely replaced in broader diagnostic cleanup. |
| `_duration_rule_scores` | No | None | A | Completed/no-op; rule scores are parsed through generic rule-mapped path. |
| `_credit_spread_rule_scores` | Yes | Only `_credit_stance_score_from_component_scores` diagnostic reconstruction | F/J | Defer; also tied to credit adjustment semantics. |
| `_credit_spread_rule_row_from_states` | Yes | Only `_credit_stance_score_from_component_scores` diagnostic reconstruction | F/J | Defer; caller likely replaced by generic diagnostic reconstruction. |
| `_threshold_state_from_score` | Yes | Active production/trace raw threshold-state classification | D | Already generalized; retain and test around boundaries if touched. |
| `_curve_change_candidate_bucket` | Yes | Rule-mapped curve buckets and legacy curve reconstruction | E | Stabilization/hysteresis cleanup; requires equality tests. |
| `_curve_state_candidate_bucket` | Yes | Rule-mapped curve buckets and legacy curve reconstruction | E | Ordered/range bucket hysteresis cleanup; requires equality tests. |
| `_yield_move_driver_candidate_bucket` | Yes | Only `_stabilize_curve_positioning_rule_buckets` | F/E | Thin score-bucket wrapper, but only caller is broader diagnostic reconstruction; do not clean alone unless caller remains. |
| `_curve_ordered_threshold_buckets` | Yes | Only `_curve_state_candidate_bucket` | E | Retain until generic ordered/range bucket hysteresis exists. |
| `_stabilize_duration_rule_states` | No | None | A | Completed/no-op; duration stabilization uses generic rule-mapped path. |
| `_stabilize_credit_rule_states` | Yes | Only `_credit_stance_score_from_component_scores` diagnostic reconstruction | F/E | Defer to smoothing diagnostic cleanup unless credit reconstruction remains. |
| `_stabilize_curve_positioning_rule_buckets` | Yes | `_curve_positioning_score_from_component_scores` diagnostic reconstruction | F/E | Defer; old curve reconstruction path should be replaced as a unit. |
| `_credit_stance_stabilization_config` | Yes | Only `_stabilize_credit_rule_states` | F/E | Defer with credit smoothing diagnostic reconstruction. |
| `_curve_positioning_stabilization_config` | Yes | Only `_stabilize_curve_positioning_rule_buckets` | F/E | Defer with curve smoothing diagnostic reconstruction. |
| `_duration_rule_component_specs` | No | None | A | Completed/no-op. |
| `_duration_rule_state_components` | No | None | A | Completed/no-op. |
| `_duration_rule_state_thresholds` | No | None | A | Completed/no-op. |
| `_duration_rule_state_buckets` | No | None | A | Completed/no-op. |
| `_credit_spread_component_thresholds` | Yes | Credit diagnostic reconstruction and adjustment intensity inputs | F/J | Retain temporarily; resolve generically from rule-mapped state inputs in diagnostic cleanup. |
| `_credit_stance_state_buckets` | Yes | Credit diagnostic reconstruction and stabilization | F/J | Retain temporarily; duplicate of rule-mapped state input metadata. |
| `_credit_spread_rule_adjustments` | Yes | Credit diagnostic reconstruction | F/J | Retain temporarily; production uses rule-mapped adjustment config. |
| `_credit_spread_state_intensity` | Yes | Production rule-mapped adjustment and diagnostic reconstruction | J/D | Retention candidate requiring explicit generic adjustment decision. |
| `_adjust_credit_spread_rule_score` | Yes | Production rule-mapped adjustment and diagnostic reconstruction | J/D | Retention candidate requiring explicit generic/plugin decision. |
| `validate_curve_change_buckets` | Yes | Active schema validation for component buckets | I/E | Generic threshold-bucket validation candidate, but keep current vocabulary validation until generic buckets/hysteresis land. |
| `validate_curve_state_buckets` | Yes | Active schema validation for ordered intervals | I/E | Generic ordered/range bucket validation candidate; keep until ordered bucket semantics are generic. |
| `validate_curve_move_driver_buckets` | Yes | Active schema validation for move-driver categories | I/C | Retain while sign-classifier primitive depends on fixed category names. |
| `validate_credit_cap_block` | Yes | Active credit adjustment validation | I/J | Generic cap helper candidate; defer with adjustment schema cleanup. |
| `validate_credit_spread_stance_parameters` | Yes | Active legacy credit and rule-mapped adjustment validation | I/J | Retain until credit adjustment schema is generic/plugin-based. |
| `validate_duration_rule_stance_schema` | Yes | Active legacy/draft duration validation | I | Defer; coupled to legacy/draft schema policy. |
| `_validate_credit_spread_stance_inputs` | No | None | A | Completed/no-op; responsibilities covered elsewhere. |
| `_default_credit_input_smoothing_windows` | Yes | `compare_credit_input_smoothing_effect` | F | Diagnostic cleanup; can become generic window defaults. |
| `_raw_credit_component_scores_for_input_smoothing_comparison` | Yes | Credit smoothing diagnostic | F | Diagnostic reconstruction; replace as part of generic input-preparation diagnostics. |
| `_credit_input_smoothing_effect_detail` | Yes | Public credit smoothing diagnostic | F | Diagnostic cleanup; requires output-column/value regression tests. |
| `_credit_input_smoothing_summary_row` | Yes | Public credit smoothing diagnostic | F/H | Generic summary candidate, after generic detail exists. |
| `compare_credit_input_smoothing_effect` | Yes | Public diagnostic entry | F | Keep public API stable while genericizing internals. |
| `_default_curve_input_smoothing_windows` | Yes | `compare_curve_input_smoothing_effect` | F | Diagnostic cleanup; can become generic window defaults. |
| `_raw_curve_component_scores_for_input_smoothing_comparison` | Yes | Curve smoothing diagnostic | F | Diagnostic reconstruction; replace as part of generic input-preparation diagnostics. |
| `_curve_input_smoothing_effect_detail` | Yes | Public curve smoothing diagnostic | F | Diagnostic cleanup; requires output-column/value regression tests. |
| `_curve_input_smoothing_summary_row` | Yes | Public curve smoothing diagnostic | F/H | Generic summary candidate, after generic detail exists. |
| `compare_curve_input_smoothing_effect` | Yes | Public diagnostic entry | F | Keep public API stable while genericizing internals. |
| `compare_curve_move_driver_threshold_effect` | Yes | Public parameter-effect diagnostic | F/C | Belongs with parameter-effect diagnostics; depends on retained move-driver primitive. |
| `_default_curve_stabilization_cases` | Yes | Curve stabilization diagnostic | G | Generic stabilization-case cleanup. |
| `_neutral_curve_positioning_stabilization_overrides` | Yes | Curve stabilization diagnostic | G | Generic case setup candidate. |
| `_default_curve_stabilization_windows` | Yes | Curve stabilization diagnostic | G | Generic window defaults candidate. |
| `_curve_stabilization_case_detail` | Yes | Curve stabilization diagnostic | G | Already uses generic breakdown; can be genericized after hysteresis core. |
| `_curve_stabilization_summary_row` | Yes | Curve stabilization diagnostic | G/H | Generic summary candidate. |
| `_curve_stabilization_window_row` | Yes | Curve stabilization diagnostic | G/H | Generic window summary candidate. |
| `compare_curve_positioning_stabilization_cases` | Yes | Public diagnostic entry | G | Keep public API stable while genericizing internals. |
| `compare_credit_stance_persistence_cases` | Yes | Public diagnostic entry | G/J | Generic persistence-case candidate; tied to credit adjustment outputs. |
| `_summarize_credit_stance_logic` | Yes | Public stance summary dispatch for credit | H/J | Target-specific summary; genericize after adjustment metadata contract is settled. |
| `_summarize_curve_positioning_stance_logic` | Yes | Public stance summary dispatch for curve | H | Generic rule-mapped summary candidate. |
| `_curve_value_counts_with_ratio` | Yes | Curve summary helper | H | Safe generic utility candidate, but only useful inside summary cleanup. |
| `_curve_dominant_value` | Yes | Curve stabilization summaries | G/H | Generic aggregation utility candidate, but only useful inside summary/stabilization diagnostic cleanup. |
| `_credit_stance_labels_for_score` | Yes | Credit smoothing diagnostics | F/H | Defer with diagnostic reconstruction. |
| `_curve_positioning_labels_for_score` | Yes | Curve smoothing and stabilization diagnostics | F/G/H | Defer with diagnostic reconstruction/stabilization summaries. |
| `_credit_stance_score_from_component_scores` | Yes | Credit smoothing diagnostic reconstruction | F/J | Do not implement alone; caller should be replaced by generic diagnostic reconstruction. |
| `_curve_positioning_score_from_component_scores` | Yes | Curve smoothing and parameter-effect diagnostics | F/E | Do not implement alone; caller should be replaced by generic diagnostic reconstruction. |
| `_RULE_MAPPED_DIAGNOSTIC_COMPAT` | Yes | `_derive_rule_mapped_diagnostic_spec_from_context` | K | Active compatibility metadata; keep until public diagnostics are redesigned. |

## Current Status by Area

### Completed / no-op

- Old curve raw bucket helper names are gone.
- Old duration-specific score and rule-score helpers are gone.
- Old curve change/state production score calculators are gone.
- Target-specific bucket/config accessors from the prior audit are gone.
- `_threshold_state_from_score` already exists and replaced the misleading duration-specific raw state classifier.
- Weighted component/stance wrappers named in the old inventory are absent; current code uses generic weighted feature/component and weighted stance breakdown helpers.

### Production-critical cleanup

- `_calculate_curve_move_driver_score`, `_curve_move_driver_score_from_prepared_inputs`, and `calculate_component_scores` remain the main production cleanup unit.
- `_calculate_current_state_component_score` is active but already generic fixed-anchor scoring and should be retained.
- Production stance calculation for duration, credit, and curve is already routed through `_build_rule_mapped_stance_score_breakdown`.

### Rule-mapped production/trace core

- `_build_rule_mapped_stance_score_breakdown` is the active production and trace baseline.
- `_threshold_state_from_score`, `_score_bucket`, `_threshold_bucket`, `_stabilize_state_series`, and `_threshold_hysteresis_candidate` are reusable core helpers.
- The remaining non-generic core issue is bucket hysteresis dispatch by component name in `_rule_mapped_bucket_candidate`.
- Credit adjustment is active in the generic rule-mapped core, but the formula is still implemented by credit-named helpers.

### Diagnostic reconstruction

- `_curve_positioning_rule_scores`, `_curve_positioning_rule_score`, `_credit_spread_rule_scores`, `_credit_spread_rule_row_from_states`, `_credit_stance_score_from_component_scores`, and `_curve_positioning_score_from_component_scores` are tied to diagnostics that reconstruct alternate raw/prepared or parameter-effect scenarios.
- These should not be polished one by one unless the broader diagnostic reconstruction path remains.

### Schema and validators

- Generic rule-mapped validation already covers much of the active stance schema.
- Target-specific validators remain behavior-sensitive because they protect active bucket vocabularies, curve move-driver sign categories, credit adjustment config, and legacy/draft duration schema support.
- Schema cleanup should follow runtime genericization, not lead it, except for narrow changes that validate an already-final generic runtime mechanism.

## Cross-Group Dependencies

- C before F: Generic input-preparation diagnostics should reuse the final `curve_move_driver_score` production helper shape.
- C before I: Schema changes for `curve_move_driver_score` should align with final runtime dispatch and retained primitive responsibilities.
- E before G: Stabilization-case diagnostics should not be generalized before ordered/range bucket hysteresis and score-bucket persistence behavior are represented generically.
- E before I: Generic bucket/hysteresis validators should follow generic runtime bucket hysteresis helpers.
- F before H: Summary helpers for smoothing diagnostics should be genericized after detail reconstruction is generic.
- J before I/H: Credit adjustment schema and summaries depend on whether adjustment becomes a generic weighted intensity adjustment or remains a credit plugin.
- K after F/G/H: Compatibility metadata should be audited after public diagnostic APIs settle.

## Items Not to Implement Alone

- `_yield_move_driver_candidate_bucket`: only useful through `_stabilize_curve_positioning_rule_buckets`; do not clean separately if that caller will be replaced.
- `_curve_positioning_rule_scores` and `_curve_positioning_rule_score`: only diagnostic reconstruction; defer to F.
- `_credit_spread_rule_scores` and `_credit_spread_rule_row_from_states`: only diagnostic reconstruction and credit adjustment support; defer to F/J.
- `_stabilize_credit_rule_states`, `_credit_stance_stabilization_config`, `_stabilize_curve_positioning_rule_buckets`, `_curve_positioning_stabilization_config`: old reconstruction paths; defer unless diagnostic reconstruction remains.
- `_credit_stance_labels_for_score` and `_curve_positioning_labels_for_score`: diagnostics-only label reconstruction; defer with F/G/H.
- `_curve_value_counts_with_ratio` and `_curve_dominant_value`: utility cleanup is low value until summary/stabilization diagnostics are genericized.

## Safe Small Cleanup Candidates

Current code leaves fewer safe small cleanups than the old inventory suggests.

- `_curve_value_counts_with_ratio` could become a generic value-count helper, but it is only used by curve summary display. Prefer doing it inside H.
- `_curve_dominant_value` could become a generic dominant-value helper, but it is only used by stabilization summaries. Prefer doing it inside G/H.
- `_yield_move_driver_candidate_bucket` is a thin `_score_bucket` wrapper, but its only caller is likely to be replaced in F/E, so do not prioritize it as a standalone cleanup.

Net recommendation: skip a separate B task unless a future implementation explicitly keeps the caller and can remove a wrapper with trivial equality checks.

## Items Requiring Equality or Regression Tests

- C: `_calculate_curve_move_driver_score`, `_curve_move_driver_score_from_prepared_inputs`, and `calculate_component_scores`.
  - Compare `curve_move_driver_score`, `curve_move_driver_label`, `curve_positioning_score`, `curve_positioning`, and `curve_positioning_strength`.
- E: `_curve_change_candidate_bucket`, `_curve_state_candidate_bucket`, `_curve_ordered_threshold_buckets`, `_rule_mapped_bucket_candidate`.
  - Test missing values, boundaries, active-state persistence, hysteresis buffers, ordered bucket transitions, and zero-buffer equivalence.
- F: Credit/curve input-smoothing diagnostics and `compare_curve_move_driver_threshold_effect`.
  - Compare diagnostic detail/summary columns and representative values.
- G: Curve stabilization and credit persistence diagnostics.
  - Compare case/window summaries, diagnostics keys, and output columns.
- H: Summary/display diagnostics.
  - Compare returned dict keys, DataFrame column names, label/strength distributions, and value counts.
- I/J: Schema and adjustment cleanup.
  - Compare config validation issues for current config and malformed fixtures, plus production credit stance outputs.

## Retained Target-Specific Functions With Reason

- `_curve_move_driver_score_from_prepared_inputs`: retain as the front-end/long-end sign-combination classifier unless a generic configured sign-classification primitive is introduced.
- `_credit_spread_state_intensity` and `_adjust_credit_spread_rule_score`: retain until the project decides whether credit adjustment is generic weighted threshold-state intensity or a credit-specific plugin.
- `validate_curve_move_driver_buckets`: retain while the move-driver primitive depends on fixed bucket names and sign semantics.
- `validate_credit_spread_stance_parameters`: retain until adjustment config has a generic/plugin schema.
- `validate_duration_rule_stance_schema`: retain while legacy/draft duration stance schemas remain supported.
- `_RULE_MAPPED_DIAGNOSTIC_COMPAT`: retain for active public diagnostic/report compatibility until diagnostic APIs settle.

## Compatibility Metadata Recommendation

Keep `_RULE_MAPPED_DIAGNOSTIC_COMPAT` as a separate Group K item. It is active today through `_derive_rule_mapped_diagnostic_spec_from_context` and controls public diagnostic aliases such as `yield_move_driver` and credit state column aliases.

Do not migrate these aliases into YAML unless the project decides they are stable model schema rather than report/API compatibility. Do not remove compatibility metadata as part of production/helper cleanup. Reaudit it after F, G, and H define the future diagnostic API surface.

## Recommended Next Implementation Order

1. Production component calculation cleanup (C)
   - Focus on `curve_move_driver_score` dispatch and narrowing `_curve_move_driver_score_from_prepared_inputs`.
   - Preserve active YAML function value `curve_move_driver_score`.

2. Stabilization/hysteresis core genericization (E)
   - Add generic threshold-bucket and ordered/range bucket hysteresis candidates.
   - Route `_rule_mapped_bucket_candidate` by classification/bucket shape rather than component name.

3. Credit adjustment decision (J)
   - Decide generic weighted threshold-state intensity adjustment vs credit-specific plugin.
   - Keep public credit outputs and adjustment metadata unchanged.

4. Smoothing/input-preparation and parameter-effect diagnostics cleanup (F)
   - Replace credit/curve raw reconstruction with generic component/stance input-preparation diagnostics.
   - Include `compare_curve_move_driver_threshold_effect` as parameter-effect diagnostics if it fits.

5. Stabilization-case diagnostics cleanup (G)
   - Generalize curve stabilization and credit persistence case comparisons after E.

6. Summary/display diagnostics cleanup (H)
   - Consolidate rule-mapped summaries, labels-for-score reconstruction, value counts, dominant values, and window summaries.

7. Schema and validator cleanup (I)
   - Align validators with generic runtime mechanisms and the adjustment decision.
   - Preserve active custom stance function names: `duration_rule_stance`, `credit_spread_stance`, `curve_positioning_stance`.
   - Preserve `rule_mapped.function: rule_mapped_stance`.

8. Compatibility metadata audit/cleanup (K)
   - Reevaluate `_RULE_MAPPED_DIAGNOSTIC_COMPAT` after diagnostic APIs settle.

Skip a standalone B task for now unless a future change exposes a truly isolated wrapper removal with no soon-to-be-replaced caller.

## Commands Run

- `git status --short --branch`
- `git log --oneline -5`
- `git branch --all --list`
- `git fetch --prune origin`
- `git branch -r --list 'origin/codex/session/*'`
- `rg --files reports`
- `rg -n` searches for all old inventory function/constant names in `module1.py`, `module1_schema.py`, `data/module1_config.yaml`, and `reports/`
- Targeted `nl -ba ... | sed -n ...` reads of `module1.py` and `module1_schema.py`
- Targeted `sed -n ...` reads of existing audit reports

## Validation

No production code changed, so no behavior validation or model run was required. No Python syntax check was required because no Python files were modified.
