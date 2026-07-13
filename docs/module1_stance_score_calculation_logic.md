# Module 1 Stance Score Calculation Logic

## 1. Purpose and Scope

This document explains how Module 1 derives exposure stance scores from component scores.

Feature construction and component score calculation are outside the scope of this document.

The current Module 1 exposure stances are:

* `duration`
* `credit`
* `usd_exposure`
* `curve_positioning`


---

## 2. Overall Calculation Architecture

### 2.1 Stance Calculation and Runtime Dispatch

`calculate_exposure_stance()` consumes the calculated component scores and processes each configured exposure stance.

It delegates numeric score calculation according to the configured calculation path:

```text
calculate_exposure_stance()
└── _calculate_exposure_stance_score()
    ├── _build_weighted_stance_score_breakdown()
    └── _build_rule_mapped_stance_score_breakdown()
```

`calculate_exposure_stance()` coordinates calculation and storage of the stance outputs. `_calculate_exposure_stance_score()` selects the configured calculation path, and the corresponding builder calculates the numeric stance score.

After the score is calculated, `calculate_exposure_stance()` derives and stores the corresponding direction and strength labels.

### 2.2 Stance Score Calculation Paths

Module 1 currently supports two stance score calculation paths:

| Calculation path | Current stances                           | How the score is produced                                                                                                 |
|---|---|---|
| Weighted sum     | `usd_exposure`                            | Direct arithmetic combination of component scores                                                                         |
| Rule mapped      | `duration`, `credit`, `curve_positioning` | Classification of component scores into states or buckets, followed by rule-case construction and configured score lookup |

The weighted-sum path combines numeric component scores directly.

The rule-mapped path is used when the relationship among component conditions is represented by a finite rule table rather than a direct arithmetic formula.

### 2.3 Primary and Derived Outputs

The numeric stance score is the primary result of stance calculation and the information-preserving output available to downstream consumers.

Direction and strength labels are derived from that score for human-readable interpretation, diagnostics and audit, plotting and reporting, and historical review.

---

## 3. Weighted-Sum Calculation Path

A weighted-sum stance multiplies each configured component score by its weight and sums the results.

```text
stance_score =
    component_score_1 × weight_1
  + component_score_2 × weight_2
  + ...
```

The current weighted-sum stance is `usd_exposure`.

Implementation reference:

```text
_build_weighted_stance_score_breakdown()
```

---

## 4. Rule-Mapped Calculation

### 4.1 What Rule Mapping Does

A rule-mapped stance converts numeric component scores into named conditions, stabilizes those conditions, combines them into one rule case, and looks up the configured base score for that case. If an adjustment is configured, it is applied after the lookup.

The conceptual flow is:

```text
numeric component scores
→ named states or buckets
→ stabilized conditions
→ combined rule case
→ configured base score
→ optional adjustment
→ final stance score
```

A duration example is:

```text
duration_preference_score
→ favorable

duration_rate_shock_score
→ no_shock

inflation_pressure_score
→ inflation_falling

policy_stance_score
→ policy_easing
```

These conditions are combined into:

```text
favorable|no_shock|inflation_falling|policy_easing
```

The configured duration rule table then supplies the score assigned to that exact case.

The same general mechanism is used by duration, credit, and curve positioning. Their differences are mainly:

* which component scores they use;
* how those scores are classified;
* what names they assign to the classified conditions;
* how many conditions form the rule case;
* which rule-score table they use;
* whether they apply a post-lookup adjustment.

The complete runtime process is coordinated by:

```text
_build_rule_mapped_stance_score_breakdown()
```

It returns the final stance score together with explanatory breakdown data for the classifications, stabilization results, rule case, base score, and any configured adjustment.



### 4.2 Step 1: Convert Component Scores into States or Buckets

A finite rule table cannot use every possible numeric score directly. Each rule input is therefore converted into a named condition.

A condition may be a state or a bucket, depending on the input’s classification method.

The current rule-mapped path supports three classification methods:

```text
threshold_state
    compare the score with positive and negative thresholds

threshold_bucket
    locate the score within configured numeric ranges

score_bucket
    match a discrete score value to its configured bucket
```

#### 4.2.1 Threshold State

`threshold_state` converts a numeric score into one of three semantic states:

```text
if score >= positive threshold:
    positive state
elif score <= negative threshold:
    negative state
else:
    neutral state
```

The positive, neutral, and negative state names depend on the stance.

Examples:

| Rule input            | Positive    | Neutral   | Negative      |
| -------------------- | ---------- | ------- | ------------ |
| `duration_preference` | `favorable` | `neutral` | `unfavorable` |
| `credit_spread_state` | `wide`      | `normal`  | `tight`       |

Conceptually:

```text
duration_preference_score above its positive threshold
→ favorable

credit_spread_state_score below its negative threshold
→ tight
```

Implementation reference:

```text
_threshold_state_from_score()
```

#### 4.2.2 Threshold Bucket

`threshold_bucket` locates a numeric score within one of several configured ranges.

Unlike `threshold_state`, it is not limited to three positive, neutral, and negative categories. It can represent several ordered conditions.

Examples:

| Rule input     | Ordered buckets                       |
| ------------- | ------------------------------------ |
| `curve_change` | `steepening`, `stable`, `flattening`  |
| `curve_state`  | `inverted`, `flat`, `normal`, `steep` |

Conceptually:

```text
curve_change_score falls within the configured steepening range
→ steepening

curve_change_score falls within the configured central range
→ stable

curve_state_score falls within the configured inverted range
→ inverted
```

The exact boundaries, inclusiveness rules, and default bucket are defined by the component configuration.

Implementation references:

```text
_threshold_bucket()
```

#### 4.2.3 Score Bucket

`score_bucket` maps an exact discrete score value directly to its configured bucket.

This method is used when the component score already represents a specific case rather than a position within a continuous numeric range.

`curve_move_driver` uses this method because each configured score corresponds to a particular yield-move pattern.

Examples:

| Discrete score meaning                                                   | Resulting bucket             |
| ----------------------------------------------------------------------- | -------------------------- |
| Score configured for a parallel bullish move                             | `bull_parallel`              |
| Score configured for a parallel bearish move                             | `bear_parallel`              |
| Score configured for front-end yields falling while long-end yields rise | `front_end_down_long_end_up` |
| Score configured for front-end yields rising while long-end yields fall  | `front_end_up_long_end_down` |
| Score configured for no clear directional pattern                        | `mixed_or_unclear`           |

Conceptually:

```text
curve_move_driver_score matches the configured bull-parallel score
→ bull_parallel

curve_move_driver_score matches the configured mixed-or-unclear score
→ mixed_or_unclear
```

Implementation reference:

```text
_score_bucket()
```

### 4.3 Step 2: Stabilize the Classified Conditions

In the rule-mapped path, threshold-based classification converts continuous component scores into discrete conditions. When a component score moves back and forth across a classification boundary, its condition changes each time, which changes the rule case and may repeatedly change the stance score.

The stabilization process reduces this behavior:

```text
numeric component score
→ raw classified condition
→ hysteresis
→ minimum persistence
→ stabilized condition
```

The stabilized condition, rather than the raw classified condition, is used to construct the rule case.

#### 4.3.1 Hysteresis

Hysteresis gives the currently active condition some tolerance near a classification boundary.

A score may therefore need to move farther across a boundary to enter a new condition than it needs to remain in the current condition.

This reduces repeated switching caused by small movements around the threshold.

#### 4.3.2 Minimum Persistence

After hysteresis produces a candidate condition, minimum persistence determines how long that candidate must remain before it replaces the active condition.

```text
min_state_persistence = 1
→ accept the candidate condition immediately

min_state_persistence > 1
→ switch only after the candidate persists for the required observations
```

Hysteresis controls whether a new condition becomes a candidate. Minimum persistence controls when that candidate becomes the active stabilized condition.

Implementation references:

```text
_classify_state_series_with_hysteresis()
_apply_state_persistence()
```

### 4.4 Step 3: Construct the Rule Case and Look Up the Base Score

The stabilized conditions are joined in the configured input order to form the rule case.

For example:

```text
favorable|no_shock|inflation_falling|policy_easing
```

The order is significant because the rule-score table uses this ordered combination as its lookup key:

```text
base_score = rule_scores[rule_case]
```

The rule-score table defines the base score assigned to each valid rule case. If any required condition is missing, the rule case and its base score are also missing.

Implementation references:

```text
_rule_case_from_states()
_lookup_rule_score()
```


### 4.5 Step 4: Apply an Optional Adjustment

After base-score lookup, the stance follows one of two paths.

```text
No adjustment:
    final stance score = base score

Configured adjustment:
    final stance score = adjusted base score
```

Duration and curve positioning currently use the no-adjustment path.

Credit currently adds an intensity-based adjustment.

Implementation reference:

```text
_rule_mapped_adjusted_row()
```

---

## 5. Stance Configurations and Differences

### 5.1 Configuration Summary

| Stance | Calculation path | Component-score inputs | Classification | Adjustment | Final score output |
| --- | --- | --- | --- | --- | --- |
| `duration` | Rule mapped | `duration_preference_score`, `duration_rate_shock_score`, `inflation_pressure_score`, `policy_stance_score` | Threshold states | No | `duration_rule_stance_score` |
| `credit` | Rule mapped | `credit_spread_change_score`, `credit_spread_state_score` | Threshold states | Credit-specific | `credit_stance_score` |
| `curve_positioning` | Rule mapped | `curve_change_score`, `curve_state_score`, `curve_move_driver_score` | Threshold buckets and score bucket | No | `curve_positioning_score` |
| `usd_exposure` | Weighted sum | `fx_score` | Not applicable | Not applicable | `usd_exposure_stance_score` |

Duration uses stance-level thresholds. Credit reuses component label thresholds, while curve positioning reuses component bucket definitions.

### 5.2 Duration Stance

Duration uses four threshold-state inputs. Their configured order determines the order of conditions in the duration rule case.

| Rule-case order | Rule input            | Source component score      | Positive condition  | Neutral condition  | Negative condition  |
| -------------- | -------------------- | -------------------------- | ------------------ | ----------------- | ------------------ |
| 1               | `duration_preference` | `duration_preference_score` | `favorable`         | `neutral`          | `unfavorable`       |
| 2               | `duration_rate_shock` | `duration_rate_shock_score` | `bullish_shock`     | `no_shock`         | `bearish_shock`     |
| 3               | `inflation`           | `inflation_pressure_score`  | `inflation_rising`  | `inflation_stable` | `inflation_falling` |
| 4               | `policy`              | `policy_stance_score`       | `policy_tightening` | `policy_stable`    | `policy_easing`     |

For example, the conditions selected from these four rows form a rule case in the same order:

```text
favorable|no_shock|inflation_falling|policy_easing
```

The current input definitions, classification thresholds, stabilization settings, rule-score mapping, and output names are defined under `exposure_stances.duration` in the loaded Module 1 configuration. The main relevant fields are `rule_mapped.state_inputs`, `state_thresholds`, `state_stabilization`, and `rule_scores`.

Duration uses the ordered four-condition rule table and its stabilization configuration without a post-lookup adjustment.


### 5.3 Credit Stance

Credit uses two threshold-state component-score inputs. Each component score contributes:

```text
component score
├── classified condition
└── intensity within that condition
```

The two conditions form the credit rule case and select a base score. The two intensities preserve additional magnitude information used to adjust that base score.

| Rule-case order | Rule input             | Source component score       | Positive condition | Neutral condition | Negative condition | Intensity output                 |
| --------------- | ---------------------- | ---------------------------- | ------------------ | ----------------- | ------------------ | -------------------------------- |
| 1               | `credit_spread_change` | `credit_spread_change_score` | `positive`         | `neutral`         | `negative`         | `credit_spread_change_intensity` |
| 2               | `credit_spread_state`  | `credit_spread_state_score`  | `wide`             | `normal`          | `tight`            | `credit_spread_state_intensity`  |

The input definitions, stabilization settings, rule-score mapping, adjustment configuration, and output names are defined under `exposure_stances.credit` in the loaded Module 1 configuration. Classification thresholds are taken from the label thresholds of the referenced components.

#### 5.3.1 Conditions, Rule Case, and Intensity

Each component score is classified into a condition. Its intensity measures how far the score lies inside that condition beyond the relevant classification threshold.

For example, suppose the component scores produce:

```text
credit_spread_change_score
→ condition: negative
→ intensity: 0.6

credit_spread_state_score
→ condition: tight
→ intensity: 0.4
```

The conditions are combined in configured input order to form the rule case:

```text
negative|tight
```

This rule case selects the configured base credit score.

The intensities retain magnitude information that the rule case alone does not contain.

A neutral condition receives zero intensity. A non-neutral condition receives an intensity between `0.0` and `1.0`.

The intensity calculation is implemented by:

```text
_credit_spread_state_intensity()
```

#### 5.3.2 Credit Adjustment

Unlike duration, credit does not necessarily use the rule-case score directly as its final stance score. It refines the base score using a weighted sum of the two intensities.

The selected rule case determines:

* the base rule score;
* `change_intensity_weight`;
* `level_intensity_weight`;
* any configured score caps.

The intensity adjustment is:

```text
intensity adjustment =
    (credit_spread_change_intensity × change_intensity_weight)
  + (credit_spread_state_intensity × level_intensity_weight)
```

The intensity adjustment is added to the base rule score, and the result is restricted to the configured lower and upper caps.

The `rule_adjustment` output records the actual difference between the capped final score and the base rule score.

The adjustment calculation is implemented by:

```text
_adjust_credit_spread_rule_score()
```

### 5.4 Curve Positioning Stance

Curve positioning uses three bucket-classified component-score inputs. Their configured order determines the order of conditions in the curve-positioning rule case.

| Rule-case order | Rule input          | Source component score    | Classification     | Possible conditions                                                                                              |
| -------------- | ------------------ | ------------------------ | ----------------- | --------------------------------------------------------------------------------------------------------------- |
| 1               | `curve_change`      | `curve_change_score`      | `threshold_bucket` | `stable`, `steepening`, `flattening`                                                                             |
| 2               | `curve_state`       | `curve_state_score`       | `threshold_bucket` | `inverted`, `flat`, `normal`, `steep`                                                                            |
| 3               | `curve_move_driver` | `curve_move_driver_score` | `score_bucket`     | `bull_parallel`, `bear_parallel`, `front_end_down_long_end_up`, `front_end_up_long_end_down`, `mixed_or_unclear` |

For example, suppose the first two component scores fall within the configured `steepening` and `flat` ranges:

```text
curve_change_score
→ steepening

curve_state_score
→ flat
```

The third input uses an exact discrete-score mapping. Under the current configuration:

```text
curve_move_driver_score = 0.5
→ front_end_down_long_end_up
```

The three conditions are combined in configured input order to form the rule case:

```text
steepening|flat|front_end_down_long_end_up
```

The input definitions, classification methods, stabilization settings, rule-score mapping, and output names are defined under `exposure_stances.curve_positioning` in the loaded Module 1 configuration. The threshold ranges and discrete score-to-bucket mappings are defined by the referenced component configurations.

Curve positioning combines two range-classified conditions with one exact-score-classified yield-move condition, without a post-lookup adjustment.


### 5.5 USD Exposure Stance

USD exposure is the current weighted-sum stance.

```text
usd_exposure_stance_score = fx_score × 1.0
```

No additional stance-specific calculation is applied after the weighted sum.


---

## 6. Derived Direction and Strength Labels

After the numeric stance score is calculated, Module 1 derives direction and strength labels.

These labels are interpretations of the score, not additional stance-score calculations.

### 6.1 Direction Labels

Direction is derived from each stance’s final numeric score using the global direction thresholds:

```text
score >= 0.5
→ positive direction

score <= -0.5
→ negative direction

otherwise
→ neutral direction
```

Each stance maps the generic direction categories to its own labels:

| Stance              | Positive            | Neutral            | Negative            |
| ------------------- | ------------------- | ------------------ | ------------------- |
| `duration`          | `duration_positive` | `duration_neutral` | `duration_negative` |
| `credit`            | `credit_positive`   | `credit_neutral`   | `credit_negative`   |
| `usd_exposure`      | `usd_positive`      | `usd_neutral`      | `usd_negative`      |
| `curve_positioning` | `long_end`          | `neutral`          | `short_end`         |


### 6.2 Strength Labels

Strength is derived from the final numeric score, with a configured override for neutral direction.

A neutral direction receives the configured neutral strength:

```text
neutral direction
→ weak
```

Otherwise, strength is determined by the absolute score magnitude:

```text
abs(score) <= 0.5
→ weak

0.5 < abs(score) <= 1.0
→ moderate

abs(score) > 1.0
→ strong
```

A magnitude of exactly `1.0` is therefore labeled `moderate`.


### 6.3 Stored Outputs

Numeric stance scores are stored in:

```text
self.stance_scores
```

The corresponding score, direction label, and strength label are stored together in:

```text
self.exposure_stance
```


---

## 7. Breakdown and Diagnostic Interpretation

The calculation builders produce explanatory breakdown data alongside the final stance score.

These breakdowns support diagnostics, audit, plotting, and historical review. They describe the runtime calculation but do not define a separate scoring path.

### 7.1 Weighted-Sum Breakdown

A weighted-sum breakdown can expose:

* source component scores;
* configured weights;
* weighted contributions;
* final stance score.

These fields show how the arithmetic result was constructed.

### 7.2 Rule-Mapped Breakdown

A rule-mapped breakdown can expose:

* source component scores;
* raw states or buckets;
* stabilized states or buckets;
* a per-input flag showing whether stabilization changed the classified condition;
* a flag showing whether stabilization changed any condition in the rule case;
* the combined rule case;
* the base rule score, when configured as an output;
* adjustment metadata, when an adjustment is configured;
* the final stance score.

The raw and stabilized conditions distinguish the immediate classification result from the condition actually used to construct the rule case.

Adjustment fields may be present for credit, but they are omitted for duration and curve positioning because those stances do not configure post-lookup adjustments.


### 7.3 Diagnostic Responsibility

Diagnostics should explain the runtime calculation without redefining it.

They should:

* use the same configured inputs, classifications, and stabilization rules as runtime calculation;
* derive available fields from the resolved stance configuration;
* preserve the distinction between weighted-sum and rule-mapped stances;
* expose adjustment metadata only when adjustment is configured;
* avoid maintaining a parallel scoring interpretation.

---

## 8. Summary

### 8.1 Calculation Paths

```text
Weighted sum:

component scores
→ apply configured weights
→ sum contributions
→ final stance score
```

```text
Rule mapped without adjustment:

component scores
→ states or buckets
→ stabilized conditions
→ rule case
→ configured base score
→ final stance score
```

```text
Credit rule mapped with adjustment:

component scores
→ states
→ stabilized state pair
→ configured base score
→ intensity-based credit adjustment
→ capped final stance score
```

### 8.2 Current Stance Mapping

| Stance | Result |
| --- | --- |
| `duration` | Rule-mapped base score |
| `credit` | Rule-mapped base score plus credit-specific capped adjustment |
| `usd_exposure` | `fx_score × 1.0` |
| `curve_positioning` | Rule-mapped base score |

### 8.3 Main Runtime Functions

| Function | Responsibility |
| --- | --- |
| `calculate_exposure_stance()` | Calculates each stance score and derives direction and strength labels |
| `_calculate_exposure_stance_score()` | Routes each stance to the weighted-sum or rule-mapped path |
| `_build_weighted_stance_score_breakdown()` | Calculates weighted contributions and the final weighted score |
| `_build_rule_mapped_stance_score_breakdown()` | Coordinates classification, stabilization, rule-case construction, score lookup, and optional adjustment |
| `_rule_mapped_adjusted_row()` | Returns the base score when adjustment is absent or applies the configured credit adjustment |
