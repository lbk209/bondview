# Module 1 Credit Adjustment J1 Audit

Date: 2026-06-30

## Executive Recommendation

Do not implement a broad J2 genericization yet. Retain the current credit adjustment implementation temporarily, while treating a generic threshold-state intensity adjustment as the desired end-state.

The current intensity math is generic: it measures how far a threshold-state input has moved beyond its positive or negative threshold, clamps that distance to `[0.0, 1.0]`, and returns `0.0` for neutral states. The current adjustment math is also mostly generic: it applies per-rule-case weights to input intensities, adds the result to the base rule score, and clamps with default or per-case caps.

However, the active YAML and schema are still credit-shaped. The adjustment config uses `change_intensity_weight` and `level_intensity_weight`, and the validator requires exactly the credit state inputs and those two weight field names. A code-only genericization would either hide credit-specific assumptions behind generic names or add an internal compatibility mapping that becomes another behavior-sensitive contract. That should wait until the runtime adjustment contract is explicit.

Recommended direction:

1. Immediate J2 posture: retain the current helpers or make only a very narrow internal cleanup if it does not claim to be fully generic.
2. Target design: generic threshold-state intensity adjustment, not a credit-specific plugin.
3. Defer schema/YAML contract cleanup to Group I after Group J defines the runtime contract.
4. Defer diagnostic reconstruction cleanup to Group F and display/summary cleanup to Group H.

## Current Production Adjustment Flow

The production path is active inside generic rule-mapped stance calculation:

1. Credit stance config still declares `function: credit_spread_stance`, but the active score path uses the nested `rule_mapped` block with `function: rule_mapped_stance`.
2. `_build_rule_mapped_stance_score_breakdown` resolves the rule-mapped spec, calculates raw and stabilized states for each state input, looks up the base rule score, and delegates adjusted scoring to `_rule_mapped_adjusted_row`.
3. `_rule_mapped_adjusted_row` is the production adjustment dispatch point. It initializes metadata output columns, handles missing base states/scores, requires all adjusted inputs to be `threshold_state`, calculates one intensity per state input by calling `_credit_spread_state_intensity`, and then calls `_adjust_credit_spread_rule_score`.
4. `_adjust_credit_spread_rule_score` uses the state-pair key, per-case `change_intensity_weight` and `level_intensity_weight`, default/per-case caps, and returns adjusted score plus rule adjustment.

Production-critical columns from this flow are:

- `credit_spread_change_state_raw`
- `credit_spread_change_state`
- `credit_spread_state_category_raw`
- `credit_spread_state_category`
- `state_stabilization_changed_change_state`
- `state_stabilization_changed_spread_state`
- `state_stabilization_changed_pair`
- `credit_state_pair`
- `base_rule_score`
- `credit_spread_change_intensity`
- `credit_spread_state_intensity`
- `rule_adjustment`
- `adjusted_credit_stance_score` where present in reconstruction contexts
- `credit_stance_score`
- `credit_stance`
- `credit_stance_strength`

## Current Diagnostic Reconstruction Flow

The public smoothing diagnostic reconstructs credit stance scores from raw component inputs:

1. `compare_credit_input_smoothing_effect` calls `_credit_input_smoothing_effect_detail`.
2. `_credit_input_smoothing_effect_detail` builds raw credit component scores, keeps production smoothed scores and stances, and calls `_credit_stance_score_from_component_scores` for the raw-score reconstruction.
3. `_credit_stance_score_from_component_scores` reads credit-specific thresholds, legacy rule scores, state buckets, rule adjustments, and stabilization settings, then calls `_credit_spread_rule_row_from_states` row by row.
4. `_credit_spread_rule_row_from_states` duplicates the active adjustment math by calling `_credit_spread_state_intensity` for the change and level inputs, then `_adjust_credit_spread_rule_score`.

This path is diagnostic reconstruction only. It is not the production score source, but it is user-facing diagnostic behavior and must remain behavior-preserving until Group F handles the smoothing/input-preparation diagnostics.

Diagnostic equality checks should cover:

- `raw_credit_spread_change_score`
- `smoothed_credit_spread_change_score`
- `raw_credit_spread_state_score`
- `smoothed_credit_spread_state_score`
- `raw_credit_stance_score`
- `smoothed_credit_stance_score`
- `credit_stance_score_diff`
- `raw_credit_stance`
- `raw_credit_stance_strength`
- `smoothed_credit_stance`
- `smoothed_credit_stance_strength`

## Config Fields Involved

Component threshold inputs:

- `components.credit_spread_change.label.thresholds.positive`
- `components.credit_spread_change.label.thresholds.negative`
- `components.credit_spread_change.label.labels`
- `components.credit_spread_state.label.thresholds.positive`
- `components.credit_spread_state.label.thresholds.negative`
- `components.credit_spread_state.label.labels`

Legacy credit stance fields still used by diagnostic reconstruction:

- `exposure_stances.credit.state_buckets`
- `exposure_stances.credit.state_stabilization`
- `exposure_stances.credit.rule_scores`
- `exposure_stances.credit.rule_adjustments.default_cap`
- `exposure_stances.credit.rule_adjustments.states`
- per-state `change_intensity_weight`
- per-state `level_intensity_weight`
- optional per-state `cap`

Active rule-mapped production fields:

- `exposure_stances.credit.rule_mapped.state_inputs`
- each state input `classification: threshold_state`
- each state input `source_score`
- each state input raw/stabilized/stabilization-changed outputs
- each state input `state_buckets`
- `rule_mapped.state_stabilization`
- `rule_mapped.rule_case_output`
- `rule_mapped.stabilization_changed_any_output`
- `rule_mapped.rule_scores`
- `rule_mapped.base_rule_score_output`
- `rule_mapped.adjustment.metadata_outputs`
- `rule_mapped.adjustment.adjustment_output`
- `rule_mapped.adjustment.config`
- `rule_mapped.adjusted_score_output`
- `rule_mapped.score_output`
- `rule_mapped.stance_output`
- `rule_mapped.strength_output`

## Schema And Validator Areas

`validate_credit_cap_block` is schema/validation support for the current adjustment caps. The cap contract is generic in shape, but the messages and caller are credit-specific.

`validate_credit_spread_stance_parameters` is credit-specific validation. It requires the two credit state-bucket groups, credit state stabilization keys, complete credit state-pair rule scores, complete credit rule-adjustment state coverage, and the two weight fields `change_intensity_weight` and `level_intensity_weight`.

The generic `rule_mapped` validator has only a shallow generic adjustment block. It validates metadata output names and `adjustment_output`, then validates `adjustment.config` by synthesizing a credit stance object and calling `validate_credit_spread_stance_parameters`. That means generic rule-mapped adjustment validation is currently credit-specific in practice.

These validators should wait until the runtime adjustment contract is decided. Changing schema first would either bless the current credit-specific shape as generic or require config changes before the runtime needs are settled.

## Function Classification

| Function/helper | Classification |
|---|---|
| `_credit_spread_state_intensity` | Active production rule-mapped adjustment path; diagnostic reconstruction only; candidate for generic threshold-state intensity mechanism; temporary retention candidate |
| `_adjust_credit_spread_rule_score` | Active production rule-mapped adjustment path; diagnostic reconstruction only; candidate for generic weighted/capped adjustment mechanism; temporary retention candidate |
| `_rule_mapped_adjusted_row` | Active production rule-mapped adjustment path; production/trace dispatch point; candidate for a future generic adjustment interface; temporary retention candidate |
| `_build_rule_mapped_stance_score_breakdown` | Active production and trace rule-mapped path; should remain stable except for a future narrow adjustment dispatch change |
| `_credit_spread_rule_adjustments` | Config accessor/helper; diagnostic reconstruction only; temporary retention candidate |
| `_credit_spread_component_thresholds` | Config accessor/helper; diagnostic reconstruction only; temporary retention candidate |
| `_credit_stance_state_buckets` | Config accessor/helper; diagnostic reconstruction only; temporary retention candidate |
| `_credit_stance_score_from_component_scores` | Diagnostic reconstruction only; Group F candidate; temporary retention candidate |
| `_credit_spread_rule_scores` | Config accessor/helper; diagnostic reconstruction only; temporary retention candidate |
| `_credit_spread_rule_row_from_states` | Diagnostic reconstruction only; candidate to reuse future generic mechanism after production contract stabilizes; temporary retention candidate |
| `_credit_input_smoothing_effect_detail` | Diagnostic reconstruction/display support only; Group F candidate; temporary retention candidate |
| `compare_credit_input_smoothing_effect` | Public diagnostic API; diagnostic reconstruction only; Group F candidate; temporary retention candidate |
| `validate_credit_cap_block` | Schema/validation support; candidate for generic cap validator after adjustment contract exists |
| `validate_credit_spread_stance_parameters` | Schema/validation support; credit-specific validator; should wait for Group I/J contract work |
| generic `rule_mapped.adjustment` validation | Schema/validation support; generic shell with credit-specific delegated validation; should wait for runtime contract |

## Option Comparison

### Option A: Generic Threshold-State Intensity Adjustment

This is the best target design. `_credit_spread_state_intensity` is not conceptually credit-specific. It only needs:

- a numeric value;
- a stabilized state label;
- positive/negative thresholds;
- configured positive/neutral/negative state labels;
- a zero-threshold behavior;
- clamping bounds, currently `[0.0, 1.0]`.

`_adjust_credit_spread_rule_score` is also mostly generic. It needs:

- base rule score;
- ordered state tuple;
- ordered intensity values;
- rule-case adjustment config;
- per-input weights;
- default cap;
- optional per-case cap;
- final score clamp.

The missing piece is a real generic config contract. A clean contract would need to declare:

- adjustment type, for example `threshold_state_intensity_weighted_cap`;
- eligible state input classifications;
- intensity method per input, or one shared default;
- metadata output mapping from state input to intensity output column;
- rule-case key format and complete coverage requirements;
- per-rule-case weights keyed by state input name or metadata output name, not credit terms;
- default cap and optional per-rule-case cap;
- adjustment output column;
- adjusted score output column;
- missing-value behavior;
- cap fallback behavior;
- clamping behavior for intensities;
- compatibility behavior for legacy configs, if legacy config remains supported.

Risk: without the contract above, a code-only generic helper would still depend on credit-specific weight fields and exactly two inputs.

### Option B: Credit-Specific Plugin Behind Generic Interface

This is not recommended as the main direction. A plugin interface is useful if future adjustments need domain-specific nonlinear formulas, external inputs, or special state semantics. The current credit adjustment does not require that.

If a plugin interface is still introduced later, it should be narrow:

- plugin id/type on `rule_mapped.adjustment`;
- inputs: resolved rule-mapped spec, state tuple, score tuple, base score, thresholds by input, buckets by input, and adjustment config;
- output: row fragment containing metadata columns, optional adjustment output, and final score output;
- required behavior: preserve missing handling, column names, numeric values, and errors for malformed config.

That interface should be a fallback extension point, not the first implementation. Otherwise the code keeps a credit-specific formula but adds plugin dispatch complexity.

### Option C: Retain Current Implementation Temporarily

This is the recommended immediate sequence. It avoids changing behavior while the adjustment contract is still implicit and credit-shaped.

Benefits:

- avoids production score risk;
- avoids schema churn before the desired generic YAML shape is known;
- avoids changing public smoothing diagnostics before Group F;
- avoids changing summary/display diagnostics before Group H;
- avoids introducing a generic abstraction that still secretly depends on credit-only weight names.

Cost:

- leaves credit-named helpers in the active production path for now;
- delays cleanup of generic `rule_mapped.adjustment` validation;
- leaves diagnostic reconstruction duplicated until Group F.

## Recommended Option And Rationale

Recommended immediate option: Option C, with Option A as the explicit target design.

Do not choose Option B now. The current behavior is better described as threshold-state intensity plus weighted capped adjustment than as a credit-domain plugin. A plugin would be justified only if future stances need non-threshold inputs, nonlinear formulas, external domain state, or intentionally domain-specific adjustment logic.

The blocker to immediate Option A is not the math. The blocker is the current contract. The runtime, YAML, and schema do not yet declare generic per-input adjustment weights. They declare credit-specific `change_intensity_weight` and `level_intensity_weight`. Until that is resolved, genericizing the implementation would be mostly cosmetic.

## J2 Implementation Implications

J2 should not change production outputs, public APIs, config names, YAML stance function names, or `_RULE_MAPPED_DIAGNOSTIC_COMPAT`.

If J2 proceeds before schema/config changes are allowed, it should be limited to one of these:

- no production code change, with this report as the design decision record; or
- a narrow internal extraction of the threshold-state intensity formula that preserves the current credit wrapper and does not claim full generic adjustment support.

A full J2 generic runtime should wait until the generic adjustment contract can represent per-input weights without credit-specific names. If that work is authorized, J2 should first define the runtime contract, then migrate production dispatch, then add equality checks before touching diagnostics or schema cleanup.

## Deferrals To Groups F, H, And I

Group F should own smoothing/input-preparation diagnostic reconstruction cleanup. In particular, `_credit_stance_score_from_component_scores`, `_credit_spread_rule_row_from_states`, `_credit_spread_rule_scores`, `_credit_spread_rule_adjustments`, `_credit_spread_component_thresholds`, `_credit_stance_state_buckets`, `_credit_input_smoothing_effect_detail`, and `compare_credit_input_smoothing_effect` should remain untouched until that diagnostic path is explicitly migrated.

Group H should own summary/display diagnostic changes. It should not depend on renamed credit adjustment columns or changed credit stance output columns.

Group I should own schema/validator cleanup after the runtime contract is explicit. `validate_credit_cap_block`, `validate_credit_spread_stance_parameters`, and the generic `rule_mapped.adjustment` validation should not be generalized before the adjustment contract is decided.

## Behavior-Preservation Requirements

Any future implementation must preserve:

- production `credit_stance_score`, `credit_stance`, and `credit_stance_strength`;
- production state columns and stabilization changed columns;
- `credit_state_pair` formatting;
- base rule score lookup and missing-state behavior;
- intensity values, including neutral `0.0`, zero-threshold `0.0`, and `[0.0, 1.0]` clamping;
- adjustment values and adjusted scores;
- default cap and per-case cap fallback behavior;
- errors for missing rule-adjustment state keys;
- trace output shape;
- public smoothing diagnostic output shape and values until Group F changes them intentionally.

Future equality checks should cover these production/trace columns:

- `credit_spread_change_score`
- `credit_spread_state_score`
- `credit_spread_change_state_raw`
- `credit_spread_change_state`
- `credit_spread_state_category_raw`
- `credit_spread_state_category`
- `state_stabilization_changed_change_state`
- `state_stabilization_changed_spread_state`
- `state_stabilization_changed_pair`
- `credit_state_pair`
- `base_rule_score`
- `credit_spread_change_intensity`
- `credit_spread_state_intensity`
- `rule_adjustment`
- `credit_stance_score`
- `credit_stance`
- `credit_stance_strength`

Future diagnostic equality checks should cover:

- `raw_credit_spread_change_score`
- `smoothed_credit_spread_change_score`
- `raw_credit_spread_state_score`
- `smoothed_credit_spread_state_score`
- `raw_credit_stance_score`
- `smoothed_credit_stance_score`
- `credit_stance_score_diff`
- `raw_credit_stance`
- `raw_credit_stance_strength`
- `smoothed_credit_stance`
- `smoothed_credit_stance_strength`

## Functions That Should Not Be Touched Yet

Do not touch these until the relevant follow-up group owns the change:

- `_credit_stance_score_from_component_scores`
- `_credit_spread_rule_row_from_states`
- `_credit_spread_rule_scores`
- `_credit_spread_rule_adjustments`
- `_credit_spread_component_thresholds`
- `_credit_stance_state_buckets`
- `_credit_input_smoothing_effect_detail`
- `compare_credit_input_smoothing_effect`
- `validate_credit_cap_block`
- `validate_credit_spread_stance_parameters`
- generic `rule_mapped.adjustment` validation
- `_RULE_MAPPED_DIAGNOSTIC_COMPAT`

Also do not rename these YAML function values:

- `duration_rule_stance`
- `credit_spread_stance`
- `curve_positioning_stance`
- `rule_mapped.function: rule_mapped_stance`

## Commands Run

- `git status --short --branch`
- `git fetch --prune origin`
- `git branch -r --list 'origin/codex/session/*'`
- `git switch -c codex/task/260630_1705_credit_adjustment_j1_audit origin/codex/session/260629_1306`
- `rg -n "_credit_spread_state_intensity|_adjust_credit_spread_rule_score|_rule_mapped_adjusted_row|_build_rule_mapped_stance_score_breakdown|_credit_spread_rule_adjustments|_credit_spread_component_thresholds|_credit_stance_state_buckets|_credit_stance_score_from_component_scores|_credit_spread_rule_scores|_credit_spread_rule_row_from_states|_credit_input_smoothing_effect_detail|compare_credit_input_smoothing_effect" module1.py`
- `rg -n "validate_credit_cap_block|validate_credit_spread_stance_parameters|rule_adjustments|metadata_outputs|adjustment_output|adjusted_score_output" module1_schema.py data/module1_config.yaml`
- `nl -ba module1.py | sed -n '2260,2495p'`
- `nl -ba module1.py | sed -n '2840,3285p'`
- `nl -ba module1.py | sed -n '7550,7835p'`
- `nl -ba data/module1_config.yaml | sed -n '250,325p'`
- `nl -ba data/module1_config.yaml | sed -n '760,875p'`
- `nl -ba module1_schema.py | sed -n '1450,1785p'`
- `nl -ba module1_schema.py | sed -n '2480,2660p'`

No production behavior validation was required because no production code, config, schema, diagnostics, YAML, or tests changed. No Python syntax check was required because no Python files changed.
