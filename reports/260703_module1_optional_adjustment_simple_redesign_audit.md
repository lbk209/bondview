# Module 1 Optional Adjustment Simple Redesign Audit

Date: 2026-07-03

## Short conclusion

The proposed simple optional-adjustment redesign is not materially different from current Module 1 behavior.

Current runtime behavior already implements the two proposed outcomes in substance:

- When rule-mapped `adjustment` config is absent, the final stance score is the base rule score.
- When credit has `adjustment` config, the shared rule-mapped row path applies the existing credit-specific adjustment math.

The main gap is representational, not behavioral: no explicit identity/no-op adjustment object exists. The no-op path is currently an `if adjustment is None: score = base_score` branch. Adding an identity adjustment object would mostly rename or repackage existing behavior and could make the code look more generic than it is, because the adjustment implementation remains credit-specific.

Recommendation: `document_only`.

## Current code path map

Relevant implementation path:

1. `calculate_component_scores()` creates component score columns in `self.scores`.
2. `calculate_exposure_stance()` iterates configured exposure stances and calls `_calculate_exposure_stance_score()`.
3. `_calculate_exposure_stance_score()` routes `duration_rule_stance`, `credit_spread_stance`, and `curve_positioning_stance` through `_build_rule_mapped_stance_score_breakdown()`.
4. `_build_rule_mapped_stance_score_breakdown()` resolves the schema with `_resolve_rule_mapped_stance_schema()`, derives raw and stabilized state columns from component scores, builds each stabilized state tuple, derives the rule case with `_rule_case_from_states()`, and looks up the base score with `_lookup_rule_score()`.
5. `_rule_mapped_adjusted_row()` receives the state tuple, score tuple, base score, and resolved rule-mapped spec. It writes optional base score metadata, then either:
   - returns the base score directly when `spec.adjustment is None`; or
   - applies the configured adjustment path when `spec.adjustment` exists.
6. `calculate_exposure_stance()` labels the final score into direction and strength outputs.

Relevant structures:

- `_RuleMappedStateInputSpec` models each rule-mapped input.
- `_RuleMappedAdjustmentSpec` models optional adjustment metadata outputs, adjustment output, and adjustment config.
- `_RuleMappedStanceSpec.adjustment` is typed as `_RuleMappedAdjustmentSpec | None`.
- `RuleMappedDiagnosticSpec` has generic optional fields for base score, adjustment, adjusted score, and adjustment metadata.

Relevant config:

- `data/module1_config.yaml` defines `rule_mapped` blocks for duration, credit, and curve.
- Duration and curve omit `rule_mapped.adjustment`.
- Credit includes `rule_mapped.adjustment`, `base_rule_score_output`, and `adjusted_score_output`.

## Current no-adjustment behavior

Duration and curve have no `rule_mapped.adjustment` block in config.

During schema resolution, `_resolve_rule_mapped_stance_schema()` initializes `adjustment_spec = None`, reads `rule_mapped.get("adjustment")`, and only creates `_RuleMappedAdjustmentSpec` when that config is present. For duration and curve, the resolved spec therefore has `spec.adjustment is None`.

During row calculation, `_rule_mapped_adjusted_row()` does this:

- If `spec.base_rule_score_output_col` is present, write the base score to that metadata column.
- Read `adjustment = spec.adjustment`.
- If `adjustment is None`, assign `row[spec.score_output_col] = base_score` and return immediately.

So duration and curve already receive identity/no-op adjustment in substance: final rule-mapped score equals base rule score. The identity behavior is implicit in the branch rather than represented as a named identity adjustment object or function.

This means the proposed "absent adjustment config -> identity/no-op adjustment" rule would not change runtime scoring for duration or curve.

## Current credit adjustment behavior

Credit has a `rule_mapped.adjustment` block in config with:

- `metadata_outputs`: `credit_spread_change_intensity`, `credit_spread_state_intensity`
- `adjustment_output`: `rule_adjustment`
- `config`: the existing `credit_rule_adjustments`

The shared `_build_rule_mapped_stance_score_breakdown()` path still calculates credit's raw states, stabilized states, rule case, and base rule score in the same generic row loop used by duration and curve.

However, the adjustment itself remains credit-specific:

- `_rule_mapped_adjusted_row()` only supports adjustment inputs whose classification is `threshold_state`.
- It calculates intensities by calling `_credit_spread_state_intensity()`.
- It applies the adjustment by calling `_adjust_credit_spread_rule_score()`.
- It assumes exactly two intensity values, using `intensities[0]` and `intensities[1]`.
- `module1_schema.py` validates `rule_mapped.adjustment.config` by reusing `validate_credit_spread_stance_parameters()` with the config mapped into `rule_adjustments`.

So credit adjustment is located inside the shared rule-mapped row path, but the implemented adjustment behavior is still effectively credit-specific.

## Diagnostics behavior

Diagnostics are already generic where fields exist and omitted where absent.

`_derive_rule_mapped_diagnostic_spec_from_context()` maps the resolved rule-mapped spec into `RuleMappedDiagnosticSpec`. It sets:

- `base_rule_score_col` from `rule_mapped_spec.base_rule_score_output_col`
- `adjustment_col` from `adjustment.adjustment_output_col` only when adjustment exists
- `adjusted_score_col` from `rule_mapped_spec.adjusted_score_output_col`
- `rule_metadata_cols` from `adjustment.metadata_output_cols` only when adjustment exists

`_rule_mapped_selected_columns()` only includes those optional columns when the corresponding diagnostic spec fields are non-null. As a result, credit diagnostics include adjustment-related fields, while duration and curve diagnostics omit them.

That behavior is already consistent with optional adjustment as a schema-level feature.

## Gap analysis

| aspect | current behavior | proposed simple redesign | material difference? | notes |
|---|---|---|---|---|
| absent adjustment config | `spec.adjustment is None` causes final score to equal base score | absent adjustment config uses identity/no-op adjustment | No | Runtime result is already identity/no-op in substance. |
| explicit identity abstraction | No identity object/function; implemented as an early branch | Possibly explicit identity/no-op adjustment | Mostly naming only | Could clarify vocabulary, but not scoring behavior. |
| credit adjustment | Credit config creates `_RuleMappedAdjustmentSpec`; row path applies credit intensity and credit rule adjustment math | Keep current credit-specific path unchanged | No | This exactly preserves current credit behavior. |
| rule-mapped row sharing | Duration, credit, and curve all route through `_build_rule_mapped_stance_score_breakdown()` | Same shared path | No | The proposed redesign does not consolidate a separate runtime path. |
| optional adjustment dataclass shape | `_RuleMappedStanceSpec.adjustment` is already optional | Same concept | No | Specs are already shaped for optional adjustment. |
| schema validation | Adjustment is optional; when config exists, validation is still credit-shaped | Keep credit path unchanged | No | No schema simplification follows from the simple redesign. |
| diagnostics | Generic optional diagnostic fields are included only when present | Possibly more consistently named no-op fields | Minor or no | Adding no-op columns for duration/curve would change diagnostics behavior and is outside scope. |
| duration/curve adjustment readiness | Duration and curve have no adjustment config and no generic adjustment math | Identity object might imply they are adjustment-ready | Risk | Could overstate genericity without adding real generic adjustment support. |
| runtime simplification | Current branch is short and direct | Identity object/function would still need dispatch or branching | No | Likely adds indirection instead of reducing logic. |

## Potential benefits

Real runtime simplification: low. The existing no-adjustment branch is already minimal, and credit adjustment still needs the existing credit-specific calls.

Clearer naming/documentation only: moderate. A short code comment or design note could make it easier to say "absence of adjustment means final score equals base score."

Better diagnostic consistency: low under the proposed constraints. Diagnostics already include adjustment columns generically where configured and omit them where absent. Adding explicit no-op diagnostic fields for duration/curve would change diagnostics behavior.

No meaningful benefit: high for runtime behavior. The proposed simple redesign does not materially change scoring, validation, config interpretation, or diagnostics.

Risky abstraction with little gain: moderate. Introducing an identity-adjustment object could imply there is a generic adjustment framework, while the actual adjustment math remains credit-specific.

## Potential risks

An explicit identity-adjustment object or function could add unnecessary abstraction around a single direct branch.

It could make `_rule_mapped_adjusted_row()` more complex without changing output behavior.

It could obscure that the non-identity adjustment still depends on credit-specific concepts: credit spread state intensity, two threshold-state inputs, credit rule adjustment weights, and credit caps.

It could create a misleading impression that duration and curve are ready for non-identity adjustments. They are rule-mapped and optional-adjustment-shaped, but they do not currently have generic adjustment math or config semantics.

It could create pressure to add no-op diagnostic columns for duration and curve, which would alter diagnostics behavior despite no model change.

## Recommendation

Recommendation: `document_only`.

Do not implement the simple redesign as runtime code now. Current behavior already matches the proposed behavior in substance, and the remaining difference is mostly wording or representation.

The only useful near-term action would be documentation-level clarification, such as a report, design note, or a narrowly scoped future comment stating that missing `rule_mapped.adjustment` intentionally means "final score equals base rule score." That should not be coupled to an identity-adjustment class or any duration/curve adjustment work.

Defer any real adjustment redesign until a full generic credit adjustment redesign is being considered. At that point, the meaningful design question is not identity/no-op handling; it is whether credit-specific intensity and adjustment logic should become a generic adjustment interface, remain credit-specific, or be split behind a named adjustment type.

## Validation

This task is report-only.

Validation run:

- `git diff --check` - passed with no output.

No Python syntax check is required because no Python files should be changed.

No production equality check is required because runtime code, schema validation, YAML config, diagnostics behavior, scoring behavior, and model outputs should not change.
