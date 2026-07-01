# Module 1 Group I Schema Parity Audit

## Conclusion

Broad schema generalization is not recommended yet. The current validator is partly capability-based already, especially for `rule_mapped` stances, but several target-specific blocks still protect intentional model structure and public vocabulary.

One clear parity gap was found: `validate_rule_mapped_stance_schema(...)` treats per-state-input output fields as optional, while runtime `_resolve_rule_mapped_stance_schema(...)` requires `raw_output`, `stabilized_output`, and `stabilization_changed_output` for every `rule_mapped.state_inputs[]` entry. That check should apply equally to duration, credit, and curve because all three active stances use the same runtime rule-mapped resolver.

The active config still validates cleanly: strict Module 1 config validation returned issue count `0`.

## Parity Matrix

| Validation capability | Duration | Curve | Credit | Recommendation |
| --- | --- | --- | --- | --- |
| Stance `score_output`, `stance_output`, `strength_output` | shared | shared | shared | Keep shared top-level and `rule_mapped` output checks. |
| Component score function allow-list | shared | shared | shared | Keep shared. |
| Component score inputs and output uniqueness | shared | shared | shared | Keep shared. |
| Threshold labels and bucket labels | shared | shared | shared | Keep shared. |
| Normalization and smoothing horizon references | shared | shared | shared | Keep shared. |
| `input_preparation.smoothing` | shared for supported prepared-input components | shared | shared | Keep capability-based, but preserve current supported-component policy. |
| `input_preparation.min_abs_value` | not applicable | shared by `curve_move_driver_score` function | not applicable | Keep function-scoped. |
| `diagnostics.prepared_inputs` | not applicable today | shared where enabled | shared where enabled | Keep shared diagnostics validation. |
| Current-state / `fixed_anchor` behavior | not applicable | target-specific for `curve_state` | target-specific for `credit_spread_state` | Retain explicit current-state component list unless a generic marker is added. |
| Curve threshold/ordered/score bucket validators | not applicable | target-specific | not applicable | Retain explicit curve bucket vocabulary and ordering checks. |
| Rule-mapped `state_inputs` shape | shared | shared | shared | Add missing required-output checks in I2. |
| Rule-mapped classification and bucket parity | shared | shared | shared | Keep shared. |
| Rule-mapped state stabilization | shared | shared | shared | Keep shared via `_resolve_rule_mapped_stabilization_config(...)`. |
| Rule-score key arity and cross-product coverage | shared | shared | shared | Keep shared; legacy duration/credit/curve checks may remain for compatibility. |
| Direction/strength label dependencies | shared | shared | shared | Keep shared. |
| Credit `rule_adjustments`, caps, intensity weights | not applicable | not applicable | target-specific | Defer to Group J; do not genericize in Group I first. |
| Compatibility aliases and diagnostic metadata | defer | defer | defer | Defer to Group K. |

## Findings

### Safe Shared-Validation Candidates

- Require `rule_mapped.state_inputs[].raw_output`, `stabilized_output`, and `stabilization_changed_output` as non-empty strings for every rule-mapped state input. Runtime already requires these fields for all rule-mapped stances.
- Keep shared `rule_mapped` checks for output matching, state-input name uniqueness, classification validity, state/bucket value uniqueness, stabilization keys, and rule-score cross-product completeness.
- Keep component-level validation shared where the runtime is already function-driven: score function allow-list, feature references, output uniqueness, label modes, horizon references, and prepared-input diagnostics.

### Intentionally Target-Specific Checks

- Credit adjustment validation should remain explicit. The active adjustment contract uses credit-specific state pairs, `change_intensity_weight`, `level_intensity_weight`, and caps.
- Curve bucket validators should remain explicit. They protect public bucket vocabulary and boundary semantics for `curve_change`, `curve_state`, and `curve_move_driver`.
- Duration legacy/draft stance validation should remain explicit while draft duration stances still use `duration_rule_stance` directly.
- Current-state fixed-anchor validation should remain tied to `credit_spread_state` and `curve_state` unless the YAML gains an explicit generic capability marker.

### Possible Validation Gaps

- `rule_mapped.state_inputs[]` output columns are runtime-required but schema-optional today. This is likely validation drift and should be the first Group I implementation target.
- The active stances carry both legacy target-specific fields and `rule_mapped` fields. The validator intentionally skips legacy credit/duration/curve stance blocks when `rule_mapped` is present, so Group I should avoid assuming those duplicated fields are canonical without a separate compatibility decision.
- `rule_mapped.adjustment.config` validation is generic only in shape; when present, it delegates to the credit-specific adjustment validator. That is correct for the current model, but not a generic adjustment contract.

### Defer To Group J Or Group K

- Defer credit adjustment genericization, including generic weighted intensity terms and generic cap semantics, to Group J.
- Defer moving diagnostic aliases or `_RULE_MAPPED_DIAGNOSTIC_COMPAT` concepts into YAML to Group K.
- Defer any runtime scoring, diagnostic, or public output changes. Group I should validate config contracts only.

## Recommended Next Tasks

- I2: implement small shared validator helper primitives only where parity is clear. Start with required `rule_mapped.state_inputs[]` output-field validation and, if useful, small helpers for repeated non-empty-string and stabilization checks.
- I3: apply parity fixes to rule-mapped stance validation, starting with the required-output-field gap and adding focused negative in-memory validation cases.
- I4: optional cleanup of credit/curve/duration-specific validators, keeping plugin-like target-specific validation explicit unless Group J or Group K changes the contract.

## Do-Not-Touch List For Group I

- Do not genericize credit `rule_adjustments` before Group J defines the runtime adjustment contract.
- Do not move compatibility metadata or diagnostic aliases into YAML; that belongs to Group K.
- Do not weaken strict validator checks to make the code look more generic.
- Do not force duration, curve, and credit into identical YAML structure.
- Do not change runtime scoring, diagnostics, public outputs, or model behavior.

## Commands Run

- `sed -n` inspections of `module1_schema.py`, `module1.py`, and `data/module1_config.yaml`.
- `rg -n` searches for rule-mapped, stabilization, adjustment, bucket, and prior cleanup references.
- `FRED_API_KEY=dummy poetry run python - <<'PY' ...` strict config validation smoke check: issue count `0`.

No Python, YAML, runtime, diagnostics, schema behavior, compatibility metadata, or production model outputs were changed by this audit.
