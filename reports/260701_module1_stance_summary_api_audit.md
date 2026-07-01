# Module 1 Stance Summary API Audit

## Conclusion

Duration is not missing from stance diagnostic coverage. The active duration stance is schema-backed `rule_mapped`, and the newer generic diagnostics already cover duration rule cases, state inputs, score distribution, stance/strength shares, and stabilization/transition behavior.

Duration is still missing from the older `summarize_stance_logic(...)` public wrapper. That is an API consistency gap, not a model or diagnostic capability gap.

Recommended direction: preserve `summarize_stance_logic(...)` as a compatibility wrapper, but add duration through a small generic rule-mapped summary path rather than writing a third target-specific duration summary. Credit and curve can also be migrated toward a common helper later, while preserving their existing public return keys.

## Current API Map

| public method | supported targets | high-level output |
| --- | --- | --- |
| `trace_stance_score(...)` | weighted stances plus rule-mapped `duration`, `credit`, `curve_positioning` | Row-level diagnostic DataFrame with score inputs, state/bucket columns, rule case, final score, labels, and optional context/raw inputs. |
| `diagnose_rule_mapped_stance(...)` | schema-backed rule-mapped targets, including `duration`, `credit`, `curve_positioning` | Selected rule-mapped calculation DataFrame. |
| `diagnose_rule_mapped_stance_transitions(...)` | schema-backed rule-mapped targets, including `duration`, `credit`, `curve_positioning` | Transition-focused DataFrame with raw/stabilized states, previous rule case, score changes, labels, and any-state stabilization flag. |
| `summarize_rule_mapped_stance_stability(...)` | schema-backed rule-mapped targets, including `duration`, `credit`, `curve_positioning` | Dict of DataFrames: `component_state_summary`, `rule_case_summary`, `mapped_score_distribution`, `score_summary`. |
| `summarize_stance_logic(...)` | `credit`, `curve_positioning`; duration falls through to `print("not implemented")` | Older target-specific summary wrapper. |

## Credit Vs Curve Summary Comparison

`_summarize_credit_stance_logic(...)` returns:

- `state_pair_distribution`: count by `credit_state_pair`.
- `mean_score_by_state_pair`: mean `base_rule_score`, `rule_adjustment`, final score, and credit intensity metadata by state pair.
- `stance_label_distribution`: count by `credit_stance`.
- `stance_strength_distribution`: count by `credit_stance_strength`.

`_summarize_curve_positioning_stance_logic(...)` returns:

- `rule_case_distribution`: count and ratio by `curve_positioning_rule_case`.
- `mean_score_by_rule_case`: mean final score and curve component scores by rule case.
- `curve_change_bucket_distribution`: count and ratio.
- `curve_state_bucket_distribution`: count and ratio.
- `yield_move_driver_bucket_distribution`: count and ratio.
- `stance_label_distribution`: count and ratio.
- `stance_strength_distribution`: count and ratio.

Common pieces:

- rule-case/state-case distribution;
- mean score by rule case;
- stance label distribution;
- strength distribution.

Credit-only pieces:

- adjustment-aware columns: `base_rule_score`, `rule_adjustment`, final score, `credit_spread_change_intensity`, `credit_spread_state_intensity`.

Curve-only pieces:

- separate state/bucket distributions for the three curve inputs;
- ratios are included for all distributions.

`_curve_value_counts_with_ratio(...)` is only used by `_summarize_curve_positioning_stance_logic(...)`. Its behavior is generic, but its name is curve-specific.

## Duration Coverage Analysis

Duration active YAML has `function: duration_rule_stance` plus a `rule_mapped` block with four state inputs:

- `duration_preference`;
- `duration_rate_shock`;
- `inflation`;
- `policy`.

Existing duration diagnostics cover:

| coverage area | existing support |
| --- | --- |
| rule-case distribution | `summarize_rule_mapped_stance_stability("duration")["rule_case_summary"]` gives transition count, unique count, most frequent case, most frequent ratio, and valid count. `diagnose_rule_mapped_stance("duration")` exposes `duration_rule_case` for full distribution. |
| state/input distribution | `diagnose_rule_mapped_stance("duration")` exposes raw and stabilized state columns; `component_state_summary` gives most frequent raw/stabilized states and valid counts. |
| mean score or score distribution | `mapped_score_distribution` gives final score counts/shares; `score_summary` gives mean, median, min, max, std, and valid count. |
| stance label distribution | `score_summary` includes stance share fields, including duration-specific positive/neutral/negative shares. |
| strength distribution | `score_summary` includes strength share fields. |
| transition/stabilization behavior | `component_state_summary` reports transition counts and stabilization-changed counts/ratios; `diagnose_rule_mapped_stance_transitions("duration")` provides row-level rule-case and score transitions. |

`diagnose_rule_mapped_stance("duration")` and `diagnose_rule_mapped_stance_transitions("duration")` provide more detailed row-level diagnostics than a simple `summarize_stance_logic("duration")` branch would likely provide.

## Generalization Recommendation

Do not treat duration as missing model functionality. Treat it as missing legacy API wrapper coverage.

Safest direction:

- keep `summarize_stance_logic(...)` as the public compatibility entry point;
- add duration through a generic rule-mapped summary helper in a follow-up task;
- preserve existing credit and curve return keys initially;
- only then consider migrating credit/curve internals to the same helper where output equality can be preserved.

Avoid deprecating `summarize_stance_logic(...)` immediately because credit and curve already expose target-specific public return keys that may be used by callers.

## Implementation Proposal

Recommended next implementation task:

1. Add a private generic rule-mapped summary helper that can produce:
   - rule-case distribution with count/share;
   - mean final/input scores by rule case;
   - per-state-input distribution from stabilized state/bucket columns;
   - stance label distribution;
   - strength distribution.
2. Add a `duration` branch in `summarize_stance_logic(...)` using that helper.
3. Keep credit and curve summaries unchanged in that first implementation unless exact output equality coverage is added.

`_curve_value_counts_with_ratio(...)` should be retained temporarily. In a later cleanup, rename or replace it with a generic value-count-with-ratio helper after curve output equality is protected. It should not be deleted as part of the duration API addition.

## Validation

Report-only audit. No runtime, YAML, schema, diagnostic behavior, public method output, or model output was changed.

Checks performed:

- inspected `module1.py`, `module1_schema.py`, and `data/module1_config.yaml`;
- read-only smoke captured current summary keys and duration diagnostic shapes;
- `git diff --check` was run for the report patch.
