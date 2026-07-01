# Module 1 Group K Compat Removal Audit

## Conclusion

Full removal of `_RULE_MAPPED_DIAGNOSTIC_COMPAT` appears feasible. Most entries are already derivable from the active `rule_mapped` YAML or the resolved `_RuleMappedStanceSpec`; several are no longer read by current code.

Output-preserving removal likely needs a small YAML/schema-backed metadata field only for public diagnostic aliases, especially `curve_move_driver -> yield_move_driver` in component summaries. Current diagnostic DataFrame column names for rule cases, state columns, stabilization flags, base scores, adjustments, adjusted scores, and rule metadata are already represented in `rule_mapped`.

## Compatibility Classification

| target | entry | current purpose | classification | proposed action |
| --- | --- | --- | --- | --- |
| duration | `function` | Historical target function name. Current resolver reads `stance_config["function"]`. | obsolete | Delete compat copy. |
| duration | `rule_case_col` | Historical rule-case column. Current spec uses `rule_mapped.rule_case_output`. | derivable | Read from `_RuleMappedStanceSpec.rule_case_output_col`. |
| duration | `state_suffix` | Historical naming hint for state columns. Current spec uses explicit per-input output columns. | obsolete | Delete. |
| duration | `stabilization_change_any_col` | Any-state stabilization-change output. Current spec uses `rule_mapped.stabilization_changed_any_output`. | derivable | Read from `_RuleMappedStanceSpec.stabilization_changed_any_output_col`. |
| credit | `function` | Historical target function name. Current resolver reads `stance_config["function"]`. | obsolete | Delete compat copy. |
| credit | `rule_case_col` | Historical rule-case column. Current spec uses `rule_mapped.rule_case_output`. | derivable | Read from `_RuleMappedStanceSpec.rule_case_output_col`. |
| credit | `state_suffix` | Historical naming hint for state columns. Current spec uses explicit per-input output columns. | obsolete | Delete. |
| credit | `state_column_aliases.credit_spread_state` | Historical state-column alias for `credit_spread_state_category`. Current YAML already declares the exact raw/stabilized output columns. | obsolete | Delete if no consumer is reintroduced. |
| credit | `state_column_overrides.credit_spread_state` | Historical raw/stabilized column override. Current YAML declares `raw_output` and `stabilized_output`. | derivable | Read from each state input spec. |
| credit | `stabilization_change_aliases.credit_spread_change` | Historical suffix alias for `state_stabilization_changed_change_state`. Current YAML declares the exact output column. | derivable | Read from each state input spec. |
| credit | `stabilization_change_aliases.credit_spread_state` | Historical suffix alias for `state_stabilization_changed_spread_state`. Current YAML declares the exact output column. | derivable | Read from each state input spec. |
| credit | `stabilization_change_any_col` | Pair-level stabilization-change output. Current spec uses `rule_mapped.stabilization_changed_any_output`. | derivable | Read from `_RuleMappedStanceSpec.stabilization_changed_any_output_col`. |
| credit | `base_rule_score_col` | Base score output before adjustment. Current spec uses `rule_mapped.base_rule_score_output`. | derivable | Read from `_RuleMappedStanceSpec.base_rule_score_output_col`. |
| credit | `adjustment_col` | Credit adjustment output. Current spec uses `rule_mapped.adjustment.adjustment_output`. | derivable | Read from `_RuleMappedAdjustmentSpec.adjustment_output_col`. |
| credit | `adjusted_score_col` | Adjusted score output. Current spec uses `rule_mapped.adjusted_score_output`. | derivable | Read from `_RuleMappedStanceSpec.adjusted_score_output_col`. |
| credit | `rule_metadata_cols` | Credit adjustment metadata outputs. Current spec uses `rule_mapped.adjustment.metadata_outputs`. | derivable | Read from `_RuleMappedAdjustmentSpec.metadata_output_cols`. |
| curve_positioning | `function` | Historical target function name. Current resolver reads `stance_config["function"]`. | obsolete | Delete compat copy. |
| curve_positioning | `rule_case_col` | Historical rule-case column. Current spec uses `rule_mapped.rule_case_output`. | derivable | Read from `_RuleMappedStanceSpec.rule_case_output_col`. |
| curve_positioning | `state_suffix` | Historical naming hint for bucket columns. Current spec uses explicit per-input output columns. | obsolete | Delete. |
| curve_positioning | `state_column_aliases.curve_move_driver` | Historical state-column alias for `yield_move_driver`. Current YAML already declares `yield_move_driver_bucket_raw` and `yield_move_driver_bucket`. | obsolete | Delete if no consumer is reintroduced. |
| curve_positioning | `component_name_aliases.curve_move_driver` | Public diagnostic component-summary alias from `curve_move_driver` to `yield_move_driver`. | YAML-needed | Add minimal alias metadata if the public component name must stay `yield_move_driver`. |
| curve_positioning | `stabilization_change_any_col` | Any-bucket stabilization-change output. Current spec uses `rule_mapped.stabilization_changed_any_output`. | derivable | Read from `_RuleMappedStanceSpec.stabilization_changed_any_output_col`. |

## Consumer Map

- `_derive_rule_mapped_diagnostic_spec_from_context(...)` is the only direct reader of `_RULE_MAPPED_DIAGNOSTIC_COMPAT`.
- That method currently uses only `component_name_aliases`; all rule case, state output, stabilization-change, base score, adjustment, adjusted score, and rule metadata columns are already read from the resolved `rule_mapped` spec.
- `_ensure_rule_mapped_stabilization_change_flags(...)`, `_rule_mapped_selected_columns(...)`, `diagnose_rule_mapped_stance(...)`, `diagnose_rule_mapped_stance_transitions(...)`, and `summarize_rule_mapped_stance_stability(...)` consume `RuleMappedDiagnosticSpec`, not the compat mapping directly.

## Output-Name Risk

- Removing derivable entries should not change diagnostic DataFrame column names if consumers continue to use `_RuleMappedStanceSpec`.
- Removing obsolete, unread entries should not affect current behavior.
- Removing `component_name_aliases.curve_move_driver` without replacement would change the `component` value in `summarize_rule_mapped_stance_stability("curve_positioning")` from `yield_move_driver` to `curve_move_driver`. Treat that as a public diagnostic vocabulary change unless explicitly approved.
- No current compat entry is needed to preserve credit adjustment column names; those names are already in `rule_mapped.adjustment`.

## Recommended Next Tasks

- K2: Delete unread compat entries and remove any remaining local reliance on derivable compat values. Keep behavior identical by continuing to build diagnostics from `_RuleMappedStanceSpec`.
- K3: Add minimal YAML/schema-backed diagnostic alias metadata only for unavoidable output-preserving names, currently `curve_move_driver -> yield_move_driver`.
- K4: Remove `_RULE_MAPPED_DIAGNOSTIC_COMPAT` after the last consumer reads aliases from schema-backed metadata or no alias is needed.

## Boundaries

No runtime, YAML, schema, diagnostic behavior, scoring, public output names, compatibility behavior, credit adjustment semantics, curve bucket semantics, duration rule semantics, or model outputs were changed by this audit.
