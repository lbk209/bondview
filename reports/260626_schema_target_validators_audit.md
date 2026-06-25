# Module 1 Target-Specific Schema Validators Audit

Date: 2026-06-26

Scope: audit/planning only for target- and component-specific validators in `module1_schema.py`, after PR #18 and PR #19 completed the curve component-score production and diagnostics cleanup.

No production code, schema code, or YAML config was changed by this audit.

## Current Validator Inventory

### Component and Bucket Validators

#### `validate_curve_change_buckets`

- Status: exists and active.
- Call path: called while validating component `curve_change`.
- Rules enforced:
  - `score.buckets` must be a mapping.
  - Bucket names must include `steepening`, `stable`, and `flattening`.
  - `steepening.min` and `flattening.max` must be numeric.
  - `stable.default` must be `true`.
  - `flattening.max < steepening.min`.
  - Stores bucket names in `curve_bucket_names` for later stance validation.
- Affects active config validity: yes.
- Classification: broader future generalization candidate.
- Rationale: the shape is a generic threshold bucket pattern with one default bucket, but the public bucket names and curve stance cross-product still depend on these names today.

#### `validate_curve_state_buckets`

- Status: exists and active.
- Call path: called while validating component `curve_state`.
- Rules enforced:
  - `score.buckets` must be a mapping.
  - Bucket names must include `inverted`, `flat`, `normal`, and `steep`.
  - Bucket boundary fields must be numeric.
  - Ranges must form contiguous ordered intervals.
  - Stores bucket names in `curve_bucket_names` for later stance validation.
- Affects active config validity: yes.
- Classification: broader future generalization candidate.
- Rationale: this is an ordered-range bucket validator. The ordered-range mechanics can become generic later, but current bucket names encode public curve semantics and are used by the curve positioning rule map.

#### `validate_curve_move_driver_buckets`

- Status: exists and active.
- Call path: called while validating component `curve_move_driver`.
- Rules enforced:
  - `score.buckets` must be a mapping.
  - Bucket names must include all five driver categories.
  - Bucket definitions must be mappings.
  - Non-default buckets must have numeric `score` values.
  - The default bucket must be `mixed_or_unclear`.
  - Non-default score values must be unique.
  - Stores bucket names in `curve_bucket_names` for later stance validation.
- Affects active config validity: yes.
- Classification: likely retainable target-specific validator for now, with some broader future generalization possible.
- Rationale: score-bucket validation is generic, but the five bucket names and their sign-combination semantics are still required by `_curve_move_driver_score_from_prepared_inputs()`.

#### Component-level `curve_move_driver_score` validation block

- Status: exists and active.
- Call path: inline component validation block for `function == "curve_move_driver_score"`.
- Rules enforced:
  - Function is only supported on component `curve_move_driver`.
  - Exactly two feature inputs are required.
  - Inputs must be mappings and reference known features.
  - Normalization and score smoothing are rejected for `curve_move_driver_score`.
- Affects active config validity: yes.
- Classification: small adjacent cleanup candidate.
- Rationale: PR #18 made runtime dispatch function-driven, but schema still hard-gates the function to `curve_move_driver`. A small follow-up could align schema with runtime by validating `curve_move_driver_score` by function shape rather than component name. This must preserve the public YAML function name and existing config validity.

#### `input_preparation.min_abs_value` component restriction

- Status: exists and active.
- Call path: inline component validation block for `score.input_preparation`.
- Rules enforced:
  - `input_preparation` is supported only for selected curve and credit components.
  - `min_abs_value` is only supported for component `curve_move_driver`.
  - `min_abs_value` must be numeric, not bool, and non-negative.
- Affects active config validity: yes.
- Classification: small adjacent cleanup candidate.
- Rationale: PR #18 moved min-absolute-value handling into generic prepared score-input mechanics. Schema can likely validate `min_abs_value` based on function support rather than the component name, but this should be kept narrow.

### Credit Validators

#### `validate_credit_cap_block`

- Status: exists and active.
- Call path: used by `validate_credit_spread_stance_parameters`.
- Rules enforced:
  - Cap must be a mapping.
  - Optional `min` and `max` must be numeric and not bool.
  - If both are present, `min < max`.
- Affects active config validity: yes, through active credit `rule_adjustments`.
- Classification: already generic enough in mechanics, but target-specific in naming.
- Rationale: the helper validates a generic numeric cap shape. It can later be renamed or moved to a generic adjustment-cap helper, but no behavior cleanup is needed now.

#### `validate_credit_spread_stance_parameters`

- Status: exists and active.
- Call paths:
  - Directly for active `credit` stance when `function == "credit_spread_stance"` and no `rule_mapped` block exists.
  - Indirectly inside `validate_rule_mapped_stance_schema` when validating credit `rule_mapped.adjustment.config`.
- Rules enforced:
  - `state_buckets` for `credit_spread_change` and `credit_spread_state`.
  - `state_stabilization` for both credit state inputs.
  - Complete two-part `rule_scores` cross-product.
  - Credit `rule_adjustments.default_cap`.
  - Credit `rule_adjustments.states` coverage for every state pair.
  - Required adjustment weights `change_intensity_weight` and `level_intensity_weight`.
  - Optional per-state caps.
- Affects active config validity: yes.
- Classification: likely retainable target-specific validator for now.
- Rationale: generic rule-mapped validation already covers state inputs, stabilization, and rule-score coverage. The remaining credit-specific adjustment formula contract still requires credit-specific validation until adjustment config has a generic schema with named terms, weights, caps, and metadata outputs.

#### `_validate_credit_spread_stance_inputs`

- Status: absent in the current repository.
- Call path: none.
- Rules enforced: none.
- Affects active config validity: no.
- Classification: absent / not applicable.
- Rationale: the current code has no such function. Its likely responsibilities are covered by `validate_credit_spread_stance_parameters`, generic component score-output validation, and generic `rule_mapped` state-input validation.

### Duration Validators

#### `validate_duration_rule_stance_schema`

- Status: exists and active.
- Call paths:
  - Active `duration` stance when `function == "duration_rule_stance"` and no `rule_mapped` block exists.
  - Draft `duration_rule_stance` validation.
- Rules enforced:
  - Stance must be a mapping with `function: duration_rule_stance`.
  - Output names must be non-empty strings.
  - `rule_state_components` must be an ordered list and exactly match the four duration components.
  - `inputs` must include the expected four component score outputs and no extras.
  - `state_thresholds` must define numeric positive/negative thresholds.
  - `state_buckets` must define positive/neutral/negative values for each rule-state component.
  - `state_stabilization` is validated through `_resolve_rule_mapped_stabilization_config`.
  - `rule_scores` must parse as four-part numeric keys and cover the full state cross-product.
  - Direction and strength labels must be present.
- Affects active config validity: yes, especially because the current `duration` stance has both legacy fields and a `rule_mapped` block, while draft duration stances still use this validator directly.
- Classification: broader future generalization candidate.
- Rationale: many rules are now expressible through `rule_mapped`, but legacy and draft duration schemas still depend on this function. Removing or generalizing it is coupled to a broader migration of duration draft/legacy schema handling.

### Rule-Mapped Generic Validators

#### `validate_rule_mapped_stance_schema`

- Status: exists and active; already generic enough for many target shapes.
- Call path: any stance with `rule_mapped`.
- Rules enforced:
  - `rule_mapped.function` and output fields.
  - Ordered `state_inputs`.
  - `source_score` references configured component outputs.
  - `threshold_state`, `threshold_bucket`, and `score_bucket` classifications.
  - Bucket-classified inputs match component bucket names.
  - Classification matches inferred bucket style from component `score.buckets`.
  - `state_stabilization` shape via `_resolve_rule_mapped_stabilization_config`.
  - `rule_scores` parse as N-part numeric case keys and cover the declared cross-product.
  - Optional adjustment metadata/output fields.
  - Delegates credit adjustment config to `validate_credit_spread_stance_parameters`.
- Affects active config validity: yes.
- Classification: already generic enough, with one credit-specific adjustment hook.
- Rationale: this is the main target for future consolidation. It already absorbs much of duration, credit, and curve stance validation.

#### `_parse_rule_scores_n_parts`

- Status: exists and active; generic.
- Rules enforced: rule-score mapping, string keys, exact key part count, no empty parts, no duplicates after normalization, numeric values.
- Affects active config validity: yes through duration and `rule_mapped`.
- Classification: already generic enough.

#### `_rule_mapped_bucket_classification_from_score`

- Status: exists and active; generic.
- Rules enforced: infers `threshold_bucket` versus `score_bucket` from component `score.buckets`; flags mixed range and score styles.
- Affects active config validity: yes through `rule_mapped`.
- Classification: already generic enough.

#### `_resolve_rule_mapped_stabilization_config`

- Status: exists and active; generic.
- Rules enforced: required component list, no unknown stabilization component keys, per-component mapping, allowed fields, required `hysteresis_buffer` and `min_state_persistence`, numeric/integer constraints.
- Affects active config validity: yes through duration and `rule_mapped`.
- Classification: already generic enough.

### Curve Positioning Legacy Inline Block

- Status: exists and active only when curve positioning lacks a `rule_mapped` block.
- Current active config relevance: mostly compatibility path. Active `curve_positioning` includes `rule_mapped`, so this block is bypassed for current config.
- Rules enforced:
  - Curve state-stabilization keys and fields.
  - Expected rule-score key coverage across curve component buckets.
  - Numeric rule-score values.
- Affects active config validity: not for current `curve_positioning` because `rule_mapped` is present.
- Classification: broader future generalization candidate or eventual compatibility cleanup.
- Rationale: the generic `rule_mapped` validator covers this shape for current config. Removing the legacy block should be deferred until legacy curve stance support is intentionally retired.

## Post-PR #18/#19 Relevance

- No curve bucket validator became obsolete solely because PR #18 made `curve_move_driver_score` dispatch function-driven.
- No curve bucket validator became obsolete solely because PR #19 moved curve diagnostics to config-derived inputs.
- The curve bucket validators still protect public bucket vocabulary used by labels, rule-mapped curve positioning, diagnostics, and compatibility outputs.
- `validate_curve_move_driver_buckets` still protects the bucket names consumed by the retained domain classifier primitive.
- The only clear mismatch with the more config-driven runtime design is the schema block that restricts `curve_move_driver_score` to component name `curve_move_driver`, plus the component-name restriction for `input_preparation.min_abs_value`.
- There is no urgent conflict that invalidates current config or runtime behavior.

## Duplication Analysis

Duplicated validation patterns across target validators:

- Mapping shape checks for config sections.
- Required ordered state-input/component lists.
- Positive/neutral/negative threshold-state buckets.
- Bucket name coverage between component `score.buckets` and stance declarations.
- Stabilization config validation.
- Rule-score parsing and full cross-product coverage.
- Numeric score/cap/weight validation.
- Direction and strength label validation.

Existing generic helpers that already absorb duplication:

- `validate_anchor_block` for fixed-anchor scoring.
- `validate_bucket_label_mode` for component bucket labels.
- `_parse_rule_scores_n_parts` for N-part rule-score parsing.
- `_rule_mapped_bucket_classification_from_score` for threshold-bucket versus score-bucket detection.
- `_resolve_rule_mapped_stabilization_config` for per-state stabilization.
- `validate_rule_mapped_stance_schema` for generic state/bucket inputs, stabilization, rule-score cross-products, and output metadata.

Potential future generic helpers:

- Generic threshold bucket validator: required bucket names, boundary fields, default bucket handling, and threshold ordering.
- Generic ordered-range bucket validator: validates range bucket boundaries and contiguous intervals.
- Generic score-bucket validator: score-valued buckets, exactly-one default bucket, unique non-default scores.
- Generic function-scoped score-input validator: expected input count and feature references by `score.function`.
- Generic adjustment config validator: default caps, per-case caps, weighted metadata terms, coverage keyed by rule-state cross-product.
- Generic legacy-to-rule-mapped consistency validator: verifies legacy stance fields and `rule_mapped` fields remain equivalent while both exist.

## Risk Assessment

Safe to change soon:

- Component-level `curve_move_driver_score` validation can likely be changed from component-name-guarded to function-shape-guarded.
- `input_preparation.min_abs_value` can likely be validated based on functions/mechanics that use dead-zone filtering instead of only component name.
- Small helper extraction for generic cap validation could be safe if it does not change error behavior materially, but it is not necessary now.

Should be deferred:

- Replacing the three curve bucket validators with generic bucket validators should wait until a generic bucket schema contract is designed and negative tests are added.
- Generalizing `validate_duration_rule_stance_schema` should wait until duration legacy and draft schema handling is migrated or explicitly retained.
- Generalizing credit adjustment validation should wait until adjustment config is represented as generic rule-mapped adjustment metadata instead of credit-specific weights.
- Removing the legacy curve positioning inline block should wait until compatibility policy for non-`rule_mapped` curve positioning is decided.

Protect public YAML compatibility:

- Curve bucket validators protect public bucket names and rule-score key vocabulary.
- Duration legacy/draft validator protects the active legacy fields and draft config shape.
- Credit adjustment validator protects active rule-adjustment keys and formula inputs.
- `rule_mapped` validator protects all active stance rule cases and output metadata.

Coupled to production scoring assumptions:

- `validate_curve_move_driver_buckets` is coupled to the retained sign-combination classifier.
- Fixed-anchor component validation is coupled to current-state scoring.
- Credit adjustment validation is coupled to the credit stance adjustment formula in runtime.
- Duration rule-state validation is coupled to legacy duration stance runtime and draft comparison paths.

## Proposed Implementation Task Groups

### Group A: Small adjacent schema alignment for `curve_move_driver_score`

Goal: align schema validation with PR #18 runtime dispatch without broad validator generalization.

Likely changes:

- Change `curve_move_driver_score` validation to be function-shape based.
- Keep exactly-two configured feature inputs required.
- Keep no normalization and no score smoothing for the categorical score.
- Keep current config valid.
- Decide whether `curve_move_driver_score` may remain semantically named and practically intended for `curve_move_driver` only, or whether schema should allow another component to use the same function if it follows the shape.
- Validate `input_preparation.min_abs_value` based on `function == "curve_move_driver_score"` rather than `component_name == "curve_move_driver"`, if the function remains the only dead-zone user.

Likely files:

- `module1_schema.py`

Validation:

- `python -m py_compile module1_schema.py`
- Strict `validate_module1_config` / `load_module1_config` issue count must remain zero.
- Positive in-memory schema case: current config.
- Negative in-memory schema cases:
  - `curve_move_driver_score` with one input.
  - `curve_move_driver_score` with normalization.
  - `curve_move_driver_score` with score smoothing.
  - `min_abs_value` on a non-supported function.

Risk and revertability:

- Low to moderate.
- Revertible independently.
- This is the only validator cleanup I would consider implementing now.

### Group B: Generic bucket schema helpers

Goal: replace curve-specific bucket mechanics with generic threshold/range/score bucket validators while preserving bucket vocabulary.

Likely changes:

- Add generic threshold-bucket, ordered-range-bucket, and score-bucket validators.
- Express curve change/state/move-driver required bucket names as validator inputs.
- Preserve all existing error coverage for current public bucket semantics.

Likely files:

- `module1_schema.py`

Validation:

- `python -m py_compile module1_schema.py`
- Strict config validation issue count zero.
- In-memory negative cases for missing buckets, unknown bucket declarations in `rule_mapped`, mixed bucket styles, nonnumeric range bounds, noncontiguous ranges, duplicate score buckets, missing default bucket, and wrong default bucket.

Risk and revertability:

- Moderate.
- Revertible if isolated, but should not be mixed with runtime or YAML changes.
- Defer until after a small test harness for schema negative cases exists.

### Group C: Rule-mapped legacy stance consolidation

Goal: reduce duplication between legacy duration/credit/curve stance validators and `validate_rule_mapped_stance_schema`.

Likely changes:

- Decide whether legacy stance fields remain required while `rule_mapped` exists.
- If retained, validate consistency between legacy fields and `rule_mapped`.
- If deprecated, stop validating legacy blocks for active stances with `rule_mapped` and move draft-only logic into a dedicated draft validator.
- Possibly replace legacy curve positioning block with generic `rule_mapped` validation only.

Likely files:

- `module1_schema.py`
- Possibly `data/module1_config.yaml` in a later migration, if legacy fields are removed or relocated.

Validation:

- Strict config validation issue count zero.
- In-memory positive cases for current active duration, credit, and curve stances.
- In-memory negative cases for missing state inputs, missing stabilization keys, incomplete rule-score cross-products, output mismatches, and draft duration schemas.
- Focused smoke checks for rule-mapped diagnostics if schema migration touches output metadata.

Risk and revertability:

- High.
- Defer. This is a broad schema/compatibility migration.

### Group D: Generic adjustment config schema

Goal: move credit adjustment validation out of credit-specific parameter validation into a generic rule-mapped adjustment schema.

Likely changes:

- Define adjustment metadata terms and weights in config generically.
- Validate default and per-case caps generically.
- Validate per-case adjustment coverage against rule-score cross-products.
- Preserve credit adjustment formula semantics or explicitly migrate them in a later behavior-sensitive task.

Likely files:

- `module1_schema.py`
- `module1.py`
- Possibly `data/module1_config.yaml`

Validation:

- Strict config validation issue count zero.
- Before/after production comparison for credit stance score, label, and strength.
- In-memory negative cases for missing weights, bad caps, incomplete adjustment states, unknown adjustment states, and output metadata mismatch.

Risk and revertability:

- High.
- Defer. It is coupled to production credit behavior.

## Recommendation

Implement at most Group A now.

Group A is a small adjacent follow-up because PR #18 changed production dispatch to be function-driven while schema validation still has a component-name guard for `curve_move_driver_score` and `min_abs_value`. This is narrow, local to `module1_schema.py`, and should not alter current config validity or production outputs.

Postpone Groups B, C, and D.

Validators that should intentionally remain target-specific for now:

- `validate_curve_change_buckets`
- `validate_curve_state_buckets`
- `validate_curve_move_driver_buckets`
- `validate_credit_spread_stance_parameters`
- `validate_duration_rule_stance_schema`
- The legacy curve positioning inline block

These validators still protect public YAML compatibility, active rule-score vocabulary, or production assumptions. Broad generalization should wait until there is a dedicated schema negative-case test harness and a clear compatibility decision for legacy stance fields.

