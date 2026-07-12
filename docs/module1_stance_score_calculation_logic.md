# Module 1 Stance Score Calculation Logic

## 1. Purpose and Scope

This document explains how Module 1 converts component scores into exposure stance outputs.

The stance layer begins after component scores have been calculated. Its responsibility is to produce:

```text
component scores
→ numeric stance score
→ stance direction
→ stance strength
```

This document focuses on stance calculation. Feature construction and component score calculation are outside its scope except where their outputs are consumed as stance inputs.

The current Module 1 exposure stances are:

- `duration`
- `credit`
- `usd_exposure`
- `curve_positioning`

---

## 2. Overall Calculation Architecture

### 2.1 End-to-End Stance Flow

The runtime sequence is:

```text
calculate_component_scores()
→ calculate_exposure_stance()
→ _calculate_exposure_stance_score()
→ numeric stance score
→ direction label
→ strength label
```

`calculate_exposure_stance()` iterates through the configured `exposure_stances`.

For each stance, it:

1. reads the stance configuration;
2. calculates the numeric stance score;
3. converts the score into a stance-specific direction label;
4. converts the score magnitude into a strength label;
5. writes the score, direction, and strength outputs.

The score calculation itself is routed by `_calculate_exposure_stance_score()`.

### 2.2 Stance Score Calculation Paths

Module 1 currently supports two stance score calculation paths:

| Calculation path | Current stances |
|---|---|
| Weighted sum | `usd_exposure` |
| Rule mapped | `duration`, `credit`, `curve_positioning` |

The distinction is based on the calculation model, not on whether the implementation is reusable.

The weighted-sum path directly combines component scores numerically.

The rule-mapped path converts component scores into states or buckets, builds a rule case, and looks up a configured rule score.

### 2.3 Configuration and Runtime Responsibilities

The YAML configuration defines the model structure, including:

- stance inputs;
- input weights;
- state classifications;
- state thresholds or buckets;
- state stabilization settings;
- rule-score tables;
- optional score adjustment;
- output column names;
- direction labels;
- strength labels.

Python implements the reusable mechanics that:

- interpret and validate the configuration;
- select the configured component scores;
- calculate weighted sums;
- classify and stabilize rule states;
- construct rule cases;
- look up rule scores;
- apply configured adjustment behavior;
- assign direction and strength labels.

The model-specific stance structure should remain in configuration where possible. Runtime code should provide the common calculation mechanics.

---

## 3. Weighted-Sum Calculation Path

### 3.1 General Calculation

A weighted-sum stance directly combines one or more component score columns:

```text
stance_score =
    component_score_1 × weight_1
  + component_score_2 × weight_2
  + ...
```

The runtime sequence is:

```text
configured component inputs
→ validate component columns and weights
→ calculate each weighted contribution
→ sum the contributions
→ final stance score
```

The internal breakdown contains:

- each source component score;
- each configured weight;
- each weighted contribution;
- the final stance score.

Conceptually:

```text
component contribution = component score × configured weight
final stance score = sum of component contributions
```

### 3.2 Behavior of the Weighted-Sum Path

The weighted-sum path does not use:

- state classification;
- state stabilization;
- rule cases;
- rule-score lookup;
- base rule scores;
- rule adjustments.

The weighted sum is already the final numeric stance score used for direction and strength labeling.

The weighted-sum implementation preserves missing inputs. If a required component score is missing for a row, the final weighted stance score is also missing for that row.

---

## 4. Rule-Mapped Calculation Pipeline

The rule-mapped path is used by duration, credit, and curve positioning.

Although their outer configuration uses stance-specific function names, all three are routed to the same rule-mapped calculation builder:

```text
duration_rule_stance
credit_spread_stance
curve_positioning_stance
        ↓
_build_rule_mapped_stance_score_breakdown()
```

Their common calculation sequence is:

```text
component scores
→ state or bucket classification
→ state stabilization
→ rule-case construction
→ base rule-score lookup
→ optional score adjustment
→ final stance score
```

### 4.1 Rule-Mapped Schema Resolution

The rule-mapped calculation begins with:

```text
_resolve_rule_mapped_stance_schema()
```

This resolves the configured `rule_mapped` block into internal specifications describing:

- stance identity and outputs;
- state inputs;
- source component-score columns;
- classification methods;
- state output columns;
- stabilization settings;
- rule-case output;
- rule-score mapping;
- optional adjustment metadata.

The primary internal specification types are:

```text
_RuleMappedStateInputSpec
_RuleMappedAdjustmentSpec
_RuleMappedStanceSpec
```

The resolved stance specification contains:

```text
adjustment: _RuleMappedAdjustmentSpec | None
```

Therefore, adjustment is an optional extension of the rule-mapped path rather than a separate stance calculation architecture.

### 4.2 Required Component Scores

Each configured rule state input points to a component score column.

Before classification, the runtime verifies that every required score column exists.

Examples include:

```text
duration_preference
    source score: duration_preference_score

credit_spread_state
    source score: credit_spread_state_score

curve_change
    source score: curve_change_score
```

The source scores are copied into the rule-mapped breakdown and remain available for diagnostics.

### 4.3 State and Bucket Classification

Each rule input defines one of three classification methods.

#### 4.3.1 Threshold State

`threshold_state` converts a numeric score into positive, neutral, or negative semantic states.

Conceptually:

```text
if score >= positive threshold:
    positive state
elif score <= negative threshold:
    negative state
else:
    neutral state
```

The semantic state names are stance-specific.

Examples:

```text
duration_preference:
    positive → favorable
    neutral  → neutral
    negative → unfavorable

credit_spread_state:
    positive → wide
    neutral  → normal
    negative → tight
```

Thresholds may come from stance-level state thresholds or from the relevant component label thresholds, depending on the stance configuration.

#### 4.3.2 Threshold Bucket

`threshold_bucket` classifies a score using the source component's configured numeric bucket ranges.

Examples include:

```text
curve_change:
    steepening
    stable
    flattening

curve_state:
    inverted
    flat
    normal
    steep
```

The bucket structure may use:

- minimum boundaries;
- maximum boundaries;
- exclusive boundaries;
- a default bucket;
- ordered numeric ranges.

#### 4.3.3 Score Bucket

`score_bucket` maps an exact configured score value to a named bucket.

This is used for discrete scores whose values already represent specific cases.

For example, `curve_move_driver_score` maps to cases such as:

```text
bull_parallel
bear_parallel
front_end_down_long_end_up
front_end_up_long_end_down
mixed_or_unclear
```

### 4.4 State Stabilization

After raw classification, each rule input is stabilized.

The stabilization settings are:

```text
hysteresis_buffer
min_state_persistence
```

The sequence is:

```text
numeric component score
→ raw state
→ hysteresis-aware candidate state
→ persistence requirement
→ stabilized state
```

#### 4.4.1 Hysteresis

Hysteresis reduces repeated state switching near a classification boundary.

The threshold required to enter a new state can differ from the threshold used to remain in the active state.

#### 4.4.2 Minimum State Persistence

Minimum state persistence requires a candidate state to remain active for the configured number of observations before replacing the current state.

A value of `1` means that no additional persistence delay is required.

#### 4.4.3 Stabilization Outputs

The breakdown records:

- the raw state;
- the stabilized state;
- whether stabilization changed each state;
- whether stabilization changed any state in the rule case.

The rule case is built from stabilized states, not raw states.

### 4.5 Rule-Case Construction

For each row, the stabilized states are collected in configured input order:

```text
state_tuple = (
    stabilized_state_1,
    stabilized_state_2,
    ...
)
```

The tuple is converted into a pipe-delimited rule case:

```text
_rule_case_from_states(state_tuple)
```

Examples:

```text
favorable|no_shock|inflation_falling|policy_easing

negative|tight

steepening|flat|front_end_down_long_end_up
```

The ordering of the rule-case parts is defined by the configured `state_inputs`.

If any required state is missing, the rule case and resulting score remain missing.

### 4.6 Base Rule-Score Lookup

The base score is looked up from the configured rule-score table:

```text
base_score = rule_scores[state_tuple]
```

The lookup is performed by:

```text
_lookup_rule_score()
```

The YAML rule-score mapping is the model definition. Python does not calculate the base rule score from a generic formula.

This allows different stances to express different economic relationships while using the same lookup mechanics.

### 4.7 Optional Score Adjustment

After the base score is found, the row is passed to:

```text
_rule_mapped_adjusted_row()
```

This method has two behaviors.

#### 4.7.1 No-Adjustment Behavior

When the resolved stance specification has no adjustment configuration:

```text
spec.adjustment is None
```

the result is:

```text
final stance score = base rule score
```

No identity-adjustment object or no-op adjustment columns are created.

Duration and curve positioning currently use this behavior.

#### 4.7.2 Configured Adjustment Behavior

When adjustment configuration exists, the base score is modified by the configured adjustment mechanics.

The adjustment path may produce:

- a base rule-score column;
- adjustment input metadata;
- an adjustment amount;
- an adjusted final score.

Credit currently uses this behavior.

The current implementation of the adjustment math is credit-specific. Adjustment should therefore be understood as:

```text
common rule-mapped pipeline
+ credit-specific score adjustment extension
```

It is not yet a fully generic adjustment framework for arbitrary rule-mapped stances.

---

## 5. Stance Configurations and Differences

The shared calculation mechanisms are described above. This section lists the actual stances and explains only their configuration or behavior differences.

### 5.1 Configuration Summary

| Stance | Calculation path | Component-score inputs | Classification | Adjustment | Final score output |
|---|---|---|---|---|---|
| `duration` | Rule mapped | `duration_preference_score`, `duration_rate_shock_score`, `inflation_pressure_score`, `policy_stance_score` | Threshold states | No | `duration_rule_stance_score` |
| `credit` | Rule mapped | `credit_spread_change_score`, `credit_spread_state_score` | Threshold states | Credit-specific | `credit_stance_score` |
| `usd_exposure` | Weighted sum | `fx_score` | Not applicable | Not applicable | `usd_exposure_stance_score` |
| `curve_positioning` | Rule mapped | `curve_change_score`, `curve_state_score`, `curve_move_driver_score` | Threshold buckets and score bucket | No | `curve_positioning_score` |

### 5.2 Duration Stance

Duration uses four rule inputs:

```text
duration_preference
duration_rate_shock
inflation
policy
```

Their source scores are:

```text
duration_preference_score
duration_rate_shock_score
inflation_pressure_score
policy_stance_score
```

The state names are:

| Input | Positive | Neutral | Negative |
|---|---|---|---|
| `duration_preference` | `favorable` | `neutral` | `unfavorable` |
| `duration_rate_shock` | `bullish_shock` | `no_shock` | `bearish_shock` |
| `inflation` | `inflation_rising` | `inflation_stable` | `inflation_falling` |
| `policy` | `policy_tightening` | `policy_stable` | `policy_easing` |

Duration defines stance-level classification thresholds:

```text
positive: 0.25
negative: -0.25
```

Its current stabilization settings use:

- a `0.05` hysteresis buffer for every input;
- persistence of `2` observations for duration preference, inflation, and policy;
- persistence of `1` observation for the short-horizon duration shock.

A duration rule case contains four parts:

```text
duration preference
| duration rate shock
| inflation
| policy
```

The configured rule table maps all valid state combinations to base duration scores.

Duration has no `rule_mapped.adjustment` block. Therefore:

```text
duration_rule_stance_score = base duration rule score
```

Duration-specific behavior is primarily its four-dimensional rule definition and stabilization settings. It does not use a separate post-lookup score formula.

### 5.3 Credit Stance

Credit uses two rule inputs:

```text
credit_spread_change
credit_spread_state
```

Their source scores are:

```text
credit_spread_change_score
credit_spread_state_score
```

The state names are:

| Input | Positive | Neutral | Negative |
|---|---|---|---|
| `credit_spread_change` | `positive` | `neutral` | `negative` |
| `credit_spread_state` | `wide` | `normal` | `tight` |

Credit does not define separate stance-level state thresholds. Its threshold-state classification therefore uses the relevant component label thresholds.

The current credit stabilization settings use:

```text
hysteresis_buffer: 0.0
min_state_persistence: 1
```

for both inputs. The stabilization pipeline still runs, but these settings do not delay or buffer state changes.

A credit rule case is a two-part state pair:

```text
credit spread change state
| credit spread level state
```

Examples:

```text
positive|wide
neutral|normal
negative|tight
```

The state pair selects the base credit rule score.

#### 5.3.1 Credit Intensity

Credit adds a severity measure for each active threshold state.

For a neutral state:

```text
intensity = 0.0
```

For a positive state:

```text
intensity =
    (score - positive_threshold)
    / positive_threshold
```

For a negative state:

```text
intensity =
    (negative_threshold - score)
    / abs(negative_threshold)
```

The result is clamped to:

```text
[0.0, 1.0]
```

This produces:

```text
credit_spread_change_intensity
credit_spread_state_intensity
```

The state identifies the category. The intensity measures how far the score has moved into that active non-neutral category.

#### 5.3.2 Credit Adjustment Formula

Each credit state pair has configured weights for the two intensity values:

```text
raw adjustment =
    change_intensity_weight × credit_spread_change_intensity
  + level_intensity_weight × credit_spread_state_intensity
```

The adjusted score is then capped:

```text
credit_stance_score =
    clamp(
        base_rule_score + raw adjustment,
        lower cap,
        upper cap
    )
```

The output `rule_adjustment` records the difference between the final capped score and the base score:

```text
rule_adjustment =
    credit_stance_score - base_rule_score
```

A state pair may use the default cap or define its own cap.

#### 5.3.3 Credit-Specific Implementation Constraint

The adjustment path currently assumes:

- every adjustment input uses `threshold_state`;
- intensity is calculated with credit threshold-state semantics;
- there are two intensity values;
- the first intensity belongs to credit-spread change;
- the second intensity belongs to credit-spread level;
- the final adjustment is calculated by `_adjust_credit_spread_rule_score()`.

Therefore, the presence of an adjustment specification does not by itself make the implementation generic for other stances.

### 5.4 USD Exposure Stance

USD exposure is the only current weighted-sum stance.

Its configuration is:

```text
input: fx_score
weight: 1.0
```

Therefore:

```text
usd_exposure_stance_score = fx_score × 1.0
```

It does not use state classification, stabilization, rule cases, rule-score lookup, or adjustment.

### 5.5 Curve Positioning Stance

Curve positioning uses three rule inputs:

```text
curve_change
curve_state
curve_move_driver
```

Their source scores are:

```text
curve_change_score
curve_state_score
curve_move_driver_score
```

The inputs use different classification methods:

| Input | Classification | Cases |
|---|---|---|
| `curve_change` | `threshold_bucket` | `stable`, `steepening`, `flattening` |
| `curve_state` | `threshold_bucket` | `inverted`, `flat`, `normal`, `steep` |
| `curve_move_driver` | `score_bucket` | `bull_parallel`, `bear_parallel`, `front_end_down_long_end_up`, `front_end_up_long_end_down`, `mixed_or_unclear` |

The current curve stabilization settings use:

```text
hysteresis_buffer: 0.0
min_state_persistence: 1
```

for all three inputs.

A curve rule case contains three parts:

```text
curve change
| curve state
| curve move driver
```

The configured rule table maps each valid combination to a curve-positioning score.

Curve positioning has no `rule_mapped.adjustment` block. Therefore:

```text
curve_positioning_score = base curve rule score
```

Its stance-specific behavior lies in combining two range-based buckets with one discrete score bucket. It does not use a separate post-lookup score formula.

---

## 6. Direction and Strength Outputs

The calculation paths produce numeric stance scores. `calculate_exposure_stance()` then derives direction and strength labels from those final scores.

### 6.1 Direction Labels

The current global direction thresholds are:

```text
positive score: score >= 0.5
negative score: score <= -0.5
neutral score:  -0.5 < score < 0.5
```

Each stance maps these generic categories to its own labels:

| Stance | Positive | Neutral | Negative |
|---|---|---|---|
| `duration` | `duration_positive` | `duration_neutral` | `duration_negative` |
| `credit` | `credit_positive` | `credit_neutral` | `credit_negative` |
| `usd_exposure` | `usd_positive` | `usd_neutral` | `usd_negative` |
| `curve_positioning` | `long_end` | `neutral` | `short_end` |

Direction is always based on the final numeric score:

- the weighted-sum score for USD exposure;
- the base rule score for duration and curve;
- the adjusted score for credit.

### 6.2 Strength Labels

The current strength labels are:

```text
weak
moderate
strong
```

Neutral direction always receives the configured neutral strength:

```text
neutral direction → weak
```

For a non-neutral stance, the current implementation evaluates score magnitude in this order:

```text
abs(score) <= 0.5       → weak
0.5 < abs(score) <= 1.0 → moderate
abs(score) > 1.0        → strong
```

Because the moderate check is evaluated before the strong check, a score magnitude of exactly `1.0` is currently labeled `moderate`.

### 6.3 Output Tables

The runtime stores numeric stance scores in:

```text
self.stance_scores
```

It stores the full stance outputs in:

```text
self.exposure_stance
```

For each stance, `self.exposure_stance` contains:

```text
numeric stance score
stance direction
stance strength
```

---

## 7. Breakdown and Diagnostic Interpretation

The calculation builders produce structured breakdown data that can explain how a stance score was obtained.

### 7.1 Weighted-Sum Breakdown

A weighted-sum breakdown can contain:

```text
source component scores
configured weights
weighted contributions
final stance score
```

For USD exposure, this explains the direct contribution from `fx_score`.

### 7.2 Rule-Mapped Breakdown

A rule-mapped breakdown can contain:

```text
source component scores
raw states or buckets
stabilized states or buckets
per-input stabilization-change flags
any-state-changed flag
rule case
base rule score, when configured as an output
adjustment metadata, when adjustment exists
rule adjustment, when adjustment exists
final stance score
```

Adjustment-related columns are produced only when the stance has adjustment configuration.

Therefore:

```text
credit:
    base score and adjustment fields can be present

duration:
    no adjustment fields

curve positioning:
    no adjustment fields
```

No no-op adjustment columns should be produced for duration or curve merely to make their diagnostics resemble credit.

### 7.3 Diagnostic Responsibility

Diagnostics should explain the configured calculation path without redefining it.

They should:

- derive available fields from the resolved stance configuration;
- preserve the distinction between weighted-sum and rule-mapped stances;
- expose credit adjustment metadata only where configured;
- use the same component-score and state definitions as runtime calculation;
- avoid maintaining a separate scoring interpretation.

---

## 8. Summary

### 8.1 Calculation Paths

```text
weighted-sum stance:
    component scores
    → weighted contributions
    → final score

rule-mapped stance without adjustment:
    component scores
    → raw states or buckets
    → stabilized states or buckets
    → rule case
    → base rule score
    → final score

rule-mapped stance with credit adjustment:
    component scores
    → raw states
    → stabilized states
    → state pair
    → base rule score
    → intensity-based credit adjustment
    → capped final score
```

### 8.2 Current Stance Mapping

```text
duration:
    rule mapped
    no adjustment
    final score = base duration rule score

credit:
    rule mapped
    credit-specific adjustment
    final score = capped base score plus intensity-based adjustment

usd_exposure:
    weighted sum
    final score = fx_score × 1.0

curve_positioning:
    rule mapped
    no adjustment
    final score = base curve rule score
```

### 8.3 Main Runtime Functions

```text
calculate_exposure_stance()
    calculates the score, direction, and strength outputs for every stance

_calculate_exposure_stance_score()
    routes a stance to the weighted-sum or rule-mapped calculation path

_build_weighted_stance_score_breakdown()
    builds weighted contributions and the final weighted stance score

_build_rule_mapped_stance_score_breakdown()
    builds classifications, stabilized states, rule cases, and rule-mapped scores

_rule_mapped_adjusted_row()
    returns the base score when adjustment is absent
    or applies the current credit-specific adjustment when configured
```
