# Module 1 Group K3 Remaining Alias Decision

## Conclusion

Recommended category: **needed, but should move to YAML/schema-backed metadata**.

The remaining alias does not affect scoring, diagnostic DataFrame column names, transitions, or model outputs. It affects one public diagnostic summary value: the `component` value in `summarize_rule_mapped_stance_stability("curve_positioning")` for the curve move-driver row.

K4 should preserve the current `yield_move_driver` diagnostic vocabulary by moving this single alias to minimal YAML/schema-backed metadata, then remove `_RULE_MAPPED_DIAGNOSTIC_COMPAT`.

## Alias Impact Map

| item | finding |
| --- | --- |
| current alias | `curve_positioning.component_name_aliases.curve_move_driver -> yield_move_driver` |
| direct consumer | `_derive_rule_mapped_diagnostic_spec_from_context(...)` reads `_RULE_MAPPED_DIAGNOSTIC_COMPAT[stance_name].component_name_aliases` when building `RuleMappedDiagnosticSpec.component_names`. |
| downstream consumer | `_rule_mapped_component_state_summary(...)` uses `spec.component_names[idx]` as the `component` value for each row. |
| public method affected | `summarize_rule_mapped_stance_stability("curve_positioning")` through its `component_state_summary` DataFrame. |
| exact output affected | `component_state_summary["component"]`, third row. Current value: `yield_move_driver`. Without alias: `curve_move_driver`. |
| methods not affected | `diagnose_rule_mapped_stance("curve_positioning")` and `diagnose_rule_mapped_stance_transitions("curve_positioning")` use columns derived from `rule_mapped` output fields, not `component_names`. |

## Public-Output Risk Summary

- DataFrame column names: no change if the alias is removed. The active YAML already declares `yield_move_driver_bucket_raw` and `yield_move_driver_bucket`.
- DataFrame values: one value changes in `summarize_rule_mapped_stance_stability("curve_positioning")["component_state_summary"]["component"]`.
- Summary labels: the displayed component vocabulary changes from `yield_move_driver` to `curve_move_driver`.
- Model outputs: no impact.
- Runtime scoring and config semantics: no impact.

The alias is therefore display vocabulary, but it is still public-facing diagnostic vocabulary. Because current columns already use `yield_move_driver_*`, preserving the `yield_move_driver` summary value keeps the summary aligned with existing diagnostic column names.

## Method Necessity Note

`summarize_rule_mapped_stance_stability(...)` still appears useful. It summarizes rule-case transitions, score distribution, stance/strength shares, and per-component stabilization behavior. The `component_state_summary` output is the only observed consumer of `RuleMappedDiagnosticSpec.component_names`.

If this summary is later considered redundant, method removal should be handled by a separate diagnostic-method cleanup audit, not by Group K alias cleanup.

## Recommended K4 Direction

Move the remaining alias to minimal YAML/schema-backed metadata, then delete `_RULE_MAPPED_DIAGNOSTIC_COMPAT`.

The narrow metadata shape should only cover rule-mapped diagnostic display aliases that cannot be derived from existing `rule_mapped` output fields. It should not introduce a broad metadata system.

## Check Performed

A non-mutating runtime check confirmed:

- current curve component summary values: `curve_change`, `curve_state`, `yield_move_driver`;
- simulated no-alias curve component summary values: `curve_change`, `curve_state`, `curve_move_driver`;
- `diagnose_rule_mapped_stance("curve_positioning")` columns remain YAML/spec-derived;
- `diagnose_rule_mapped_stance_transitions("curve_positioning")` columns remain YAML/spec-derived.

No runtime, YAML, schema, diagnostic behavior, public output names, scoring, model outputs, credit adjustment semantics, curve bucket semantics, or duration rule semantics were changed by this audit.
