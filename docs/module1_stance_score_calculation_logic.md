# Module 1 Stance Score Calculation Logic

## Purpose

This document explains how Module 1 calculates stance scores.

It describes the implementation structure, the two stance score calculation paths, and how each major stance uses those paths.

The main flow is:

```text
component scores
-> stance score calculation
-> stance direction
-> stance strength
```

---

## A. Overall Calculation Flow

Stance calculation starts after component scores have been prepared.

```text
calculate_component_scores()
-> calculate_exposure_stance()
-> _calculate_exposure_stance_score()
-> numeric stance score
-> stance direction
-> stance strength
```

`calculate_component_scores()` creates component-level score columns in `self.scores`.

`calculate_exposure_stance()` iterates the configured exposure stances. For each stance, it calls `_calculate_exposure_stance_score()` to calculate the numeric stance score.

`_calculate_exposure_stance_score()` dispatches according to the stance function configured in YAML.

The two main stance score calculation styles are:

```text
weighted_sum
rule_mapped_stance
```

After the numeric score is calculated, `calculate_exposure_stance()` assigns direction and strength labels from that final score.

---

## B. Weighted-Sum Stance Path

A weighted-sum stance directly combines component scores.

```text
stance_score =
    component_score_1 * weight_1
  + component_score_2 * weight_2
  + ...
```

This path is used when the stance can be represented as a direct weighted combination of inputs.

Example concept:

```text
usd_exposure_stance_score = fx_score * 1.0
```

Weighted-sum stances do not use:

```text
state inputs
state stabilization
rule cases
base rule scores
rule adjustment
```

The weighted result is the final stance score used for direction and strength labeling.

---

## C. Rule-Mapped Stance Path

A rule-mapped stance uses a conditional rule table instead of a direct weighted sum.

The rule-mapped path is:

```text
_calculate_exposure_stance_score()
-> _build_rule_mapped_stance_score_breakdown()
-> _rule_mapped_adjusted_row()
```

Duration, credit, and curve positioning use this shared rule-mapped path.

The rule-mapped flow is:

```text
component scores
-> raw states
-> stabilized states
-> rule case
-> base rule score
-> adjustment/no-adjustment handling
-> final stance score
```

### C.1 Schema Resolution

`_build_rule_mapped_stance_score_breakdown()` first calls:

```text
_resolve_rule_mapped_stance_schema()
```

This resolves the YAML `rule_mapped` block into internal specs:

```text
_RuleMappedStateInputSpec
_RuleMappedAdjustmentSpec
_RuleMappedStanceSpec
```

The resolved stance spec contains an optional adjustment field:

```text
_RuleMappedStanceSpec.adjustment: _RuleMappedAdjustmentSpec | None
```

If YAML has no `rule_mapped.adjustment` section:

```text
spec.adjustment is None
```

If YAML has a `rule_mapped.adjustment` section:

```text
spec.adjustment is a _RuleMappedAdjustmentSpec
```

### C.2 State Classification

Each rule-mapped stance defines state inputs. Each state input points to a component score column.

Examples:

```text
duration_preference -> duration_preference_score
credit_spread_change -> credit_spread_change_score
credit_spread_state -> credit_spread_state_score
curve_change -> curve_change_score
curve_state -> curve_state_score
```

For `threshold_state` inputs, the classification pattern is:

```text
if score >= positive_threshold:
    raw_state = positive bucket

elif score <= negative_threshold:
    raw_state = negative bucket

else:
    raw_state = neutral bucket
```

Bucket labels are stance-specific.

Examples:

```text
duration_preference:
    positive -> favorable
    neutral  -> neutral
    negative -> unfavorable

credit_spread_state:
    positive -> wide
    neutral  -> normal
    negative -> tight
```

`_build_rule_mapped_stance_score_breakdown()` writes raw state columns and stabilized state columns into the rule-mapped breakdown.

### C.3 State Stabilization

After raw classification, `_build_rule_mapped_stance_score_breakdown()` stabilizes each state series.

Stabilization settings include:

```text
hysteresis_buffer
min_state_persistence
```

The rule case is built from stabilized states.

```text
raw state
-> stabilized state
-> rule case
```

This reduces noisy state flipping when scores move near thresholds.

### C.4 Rule Case and Base Rule Score

For each row, `_build_rule_mapped_stance_score_breakdown()` builds:

```text
state_tuple
score_tuple
rule_case
base_score
```

The rule case is created by:

```text
_rule_case_from_states()
```

The base rule score is looked up by:

```text
_lookup_rule_score()
```

Conceptually:

```text
base_score = rule_scores[rule_case]
```

Examples:

```text
negative|tight -> base credit score
favorable|no_shock|inflation_falling|policy_easing -> base duration score
steepening|flat|front_end_down_long_end_up -> base curve score
```

After the base score is found, the row is passed to:

```text
_rule_mapped_adjusted_row()
```

---

## D. Adjustment Handling

`_rule_mapped_adjusted_row()` decides whether a rule-mapped stance uses adjustment.

The no-adjustment branch is:

```text
adjustment = spec.adjustment

if adjustment is None:
    row[spec.score_output_col] = base_score
    return row
```

So for rule-mapped stances without adjustment config:

```text
final stance score = base rule score
```

There is no separate identity-adjustment object. The no-adjustment behavior is implemented directly by this branch.

When `spec.adjustment` exists, `_rule_mapped_adjusted_row()` follows the adjustment path. In the implementation, credit is the stance that uses real adjustment.

---

## E. Credit Adjustment

Credit is the rule-mapped stance with real adjustment.

The credit rule inputs are:

```text
credit_spread_change
credit_spread_state
```

The credit flow is:

```text
credit_spread_change_score
credit_spread_state_score
-> raw states
-> stabilized states
-> credit state pair
-> base_rule_score
-> _rule_mapped_adjusted_row()
-> credit-specific adjustment
-> credit_stance_score
```

### E.1 Credit State Pair

Credit combines the stabilized states into a two-part state pair.

Examples:

```text
positive|wide
neutral|normal
negative|tight
```

The state pair is used to look up the base credit rule score.

### E.2 Credit Intensity

Credit adjustment uses two intensity values:

```text
credit_spread_change_intensity
credit_spread_state_intensity
```

The function used for intensity is:

```text
_credit_spread_state_intensity()
```

Intensity measures severity inside the active non-neutral state.

For a threshold-state input:

```text
neutral state:
    intensity = 0.0

positive state:
    intensity = distance above positive threshold

negative state:
    intensity = distance below negative threshold

then clamp intensity to [0.0, 1.0]
```

So:

```text
state = category
intensity = severity inside that category
```

### E.3 Credit Adjustment Formula

Credit adjustment uses configured weights for the active credit state pair.

```text
rule_adjustment =
    change_intensity_weight * credit_spread_change_intensity
  + level_intensity_weight * credit_spread_state_intensity

credit_stance_score =
    clamp(base_rule_score + rule_adjustment, lower_cap, upper_cap)
```

Example:

```text
state_pair = negative|tight
base_rule_score = -1.20

change_intensity = 0.60
level_intensity = 0.30

change_intensity_weight = -0.20
level_intensity_weight = -0.10

rule_adjustment =
    (-0.20 * 0.60) + (-0.10 * 0.30)
  = -0.15

credit_stance_score =
    clamp(-1.20 - 0.15, lower_cap, upper_cap)
```

### E.4 Credit-Specific Implementation Details

Although credit adjustment is called from the shared rule-mapped row path, the adjustment math is credit-specific.

The adjustment path uses:

```text
_credit_spread_state_intensity()
_adjust_credit_spread_rule_score()
```

It also assumes:

```text
adjustment inputs use threshold_state classification
there are two intensity values
intensities[0] is credit_spread_change intensity
intensities[1] is credit_spread_state intensity
```

So the implementation should be understood as:

```text
shared rule-mapped path
+ credit-specific adjustment branch
```

---

## F. Duration Stance

Duration uses the shared rule-mapped path.

Main duration rule inputs:

```text
duration_preference
duration_rate_shock
inflation
policy
```

The duration flow is:

```text
duration component scores
-> raw states
-> stabilized states
-> duration rule case
-> base duration rule score
-> _rule_mapped_adjusted_row()
-> duration stance score
```

Duration YAML has no `rule_mapped.adjustment` block.

Therefore:

```text
spec.adjustment is None
```

and `_rule_mapped_adjusted_row()` returns:

```text
duration stance score = base duration rule score
```

Duration does not calculate duration adjustment, duration intensity metadata, or duration rule adjustment.

---

## G. Curve Positioning Stance

Curve positioning uses the shared rule-mapped path.

Main curve rule inputs are conceptually:

```text
curve_change
curve_state
curve_move_driver
```

The curve flow is:

```text
curve component scores
-> raw states/buckets
-> stabilized states
-> curve rule case
-> base curve score
-> _rule_mapped_adjusted_row()
-> curve positioning score
```

Curve YAML has no `rule_mapped.adjustment` block.

Therefore:

```text
spec.adjustment is None
```

and `_rule_mapped_adjusted_row()` returns:

```text
curve positioning score = base curve rule score
```

Curve positioning does not calculate curve adjustment, curve intensity metadata, or curve rule adjustment.

---

## H. Diagnostics

Rule-mapped diagnostics derive their available columns from the resolved rule-mapped spec.

The relevant diagnostic functions include:

```text
_derive_rule_mapped_diagnostic_spec_from_context()
_rule_mapped_selected_columns()
```

For stances with adjustment config, diagnostics can include adjustment-related fields.

For credit, available adjustment-related fields can include:

```text
base_rule_score
credit_spread_change_intensity
credit_spread_state_intensity
rule_adjustment
credit_stance_score
```

For duration and curve, adjustment fields are omitted because no adjustment config exists.

Diagnostic behavior by stance type:

```text
credit: includes adjustment fields where configured
duration: no adjustment fields
curve: no adjustment fields
```

No no-op adjustment columns are produced for duration or curve.

---

## I. Direction and Strength Labels

After the final numeric stance score is calculated, `calculate_exposure_stance()` assigns:

```text
stance direction
stance strength
```

The direction label is based on the final numeric score.

Conceptually:

```text
positive score -> positive label
near-zero score -> neutral label
negative score -> negative label
```

The strength label is based on score magnitude.

For no-adjustment rule-mapped stances:

```text
labels are based on the base rule score
```

For credit:

```text
labels are based on the adjusted credit_stance_score
```

For weighted-sum stances:

```text
labels are based on the weighted-sum score
```

---

## J. Summary

Stance score calculation can be summarized as:

```text
weighted_sum stances:
    component scores -> weighted sum -> final score

duration:
    rule case -> base rule score -> final score

credit:
    rule case -> base rule score -> credit-specific adjustment -> final score

curve:
    rule case -> base rule score -> final score
```

Function-level summary:

```text
calculate_exposure_stance()
    top-level exposure stance calculation

_calculate_exposure_stance_score()
    routes each stance to weighted-sum or rule-mapped scoring

_build_rule_mapped_stance_score_breakdown()
    builds states, rule cases, and base rule scores for rule-mapped stances

_rule_mapped_adjusted_row()
    returns base score when adjustment is absent;
    applies the credit-specific adjustment when adjustment exists
```

Stance-specific adjustment status:

```text
duration:
    no adjustment config
    final score = base rule score

credit:
    has adjustment config
    final score = base rule score + credit-specific rule adjustment, capped/clamped

curve:
    no adjustment config
    final score = base rule score

weighted_sum stances:
    no rule-mapped adjustment concept
```
