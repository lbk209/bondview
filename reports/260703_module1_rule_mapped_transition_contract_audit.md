# Module 1 Rule-Mapped Transition Contract Audit

Date: 2026-07-03

## Short conclusion

Classification: `keep_as_public_convenience`.

`diagnose_rule_mapped_stance_transitions()` is exactly reproducible from `diagnose_rule_mapped_stance()` plus deterministic post-processing. A runtime contract check confirmed exact equivalence for `duration`, `credit`, and `curve_positioning` over a small local-data date slice.

Despite that, the method is more than a pure single-call wrapper. It centralizes transition-specific derivation that callers would otherwise need to repeat carefully: previous rule case, rule-case changed flag, previous score, score-change calculation, first-valid-row changed-flag correction, date column handling, labels, and optional stabilization-change flag handling. Prior reports also cite it as transition-focused replacement guidance. I do not recommend deletion in this task.

## Implementation delta

`diagnose_rule_mapped_stance_transitions()` starts by resolving the rule-mapped diagnostic context and spec, then calls:

```python
diagnose_rule_mapped_stance(
    spec.target,
    context_id=context_id,
    start=start,
    end=end,
    include_scores=False,
    include_raw_states=True,
    include_stabilized_states=True,
    include_rule_case=True,
    include_labels=True,
)
```

It adds the following transition-specific output on top of that base diagnostic:

- `date` column copied from the DataFrame index.
- Raw state columns and stabilized state columns copied in paired order from the rule-mapped spec.
- Current rule-case column.
- `previous_<rule_case_col>` using `.shift(1)`.
- `<rule_case_col>_changed`, comparing current and previous rule case while requiring current rule case to be non-null.
- Current final score column.
- `previous_<final_score_col>` using `.shift(1)`.
- `<final_score_col>_change`, calculated as current final score minus previous final score.
- Stance label column.
- Strength label column.
- Optional `stabilization_changed_any_output` column when the spec defines one.
- First-valid-row correction: the first valid rule-case row has `<rule_case_col>_changed` forced to `False`.

The method is fully generic across schema-backed rule-mapped stances. I found no target-specific branches for duration, credit, or curve positioning inside the method.

## Replacement recipe

Exact base call:

```python
diagnostics = rgm.diagnose_rule_mapped_stance(
    target,
    context_id=context_id,
    start=start,
    end=end,
    include_scores=False,
    include_raw_states=True,
    include_stabilized_states=True,
    include_rule_case=True,
    include_labels=True,
)
```

Required setup:

```python
context = rgm._resolve_rule_mapped_diagnostic_config(target)
spec = rgm._derive_rule_mapped_diagnostic_spec_from_context(context)
```

Required post-processing:

1. Create an empty DataFrame on the same index.
2. Add `date = diagnostics.index`.
3. Copy each `(raw_state_col, stabilized_state_col)` pair from the spec.
4. Copy the current rule-case column.
5. Add previous rule case with `.shift(1)`.
6. Add rule-case changed flag with current non-null gating.
7. Copy the final score column.
8. Add previous final score with `.shift(1)`.
9. Add score-change column.
10. Copy stance and strength label columns.
11. Copy the optional any-stabilization-change column if present.
12. Locate `diagnostics[spec.rule_case_col].first_valid_index()` and force the changed flag to `False` at that row.

The recipe is straightforward for a maintainer who knows the rule-mapped spec internals, but it is repetitive and easy for callers to get subtly wrong. The highest-risk details are first-valid-row behavior, optional stabilization-change output, dynamic column names, and preserving column order across targets.

## Runtime contract check

Runtime status: completed successfully.

Data availability:

- Used local CSV data via `load_local_data("data/raw_data_19980101_20260508.csv")`.
- The first attempt with `load_data()` tried FRED downloads and failed because `FRED_API_KEY=dummy` is not a valid FRED key. The successful check avoided network/data download by loading the local CSV directly.

Runtime setup:

- `FRED_API_KEY=dummy poetry run python`
- `RegimeModule(...)`
- `load_local_data("data/raw_data_19980101_20260508.csv")`
- `load_module1_config()`
- `calculate_features()`
- `calculate_component_scores()`
- `calculate_component_labels()`
- `calculate_exposure_stance()`

Targets checked:

- `duration`
- `credit`
- `curve_positioning`

Date range used:

- `2020-01-01` through `2020-03-31`

Comparison performed:

- actual `diagnose_rule_mapped_stance_transitions(target, start=..., end=...)`
- manual reconstruction from `diagnose_rule_mapped_stance(target, include_scores=False, include_raw_states=True, include_stabilized_states=True, include_rule_case=True, include_labels=True, start=..., end=...)`

Results:

| target | shape | columns/order | index/date handling | values | dtypes | first-valid changed flag |
|---|---:|---|---|---|---|---|
| `duration` | `(67, 18)` | matched | matched | matched | matched | `False` |
| `credit` | `(67, 14)` | matched | matched | matched | matched | `False` |
| `curve_positioning` | `(67, 16)` | matched | matched | matched | matched | `False` |

`pandas.testing.assert_frame_equal(..., check_dtype=True)` passed for all three targets.

No score-change differences were observed. The manually reconstructed score-change columns matched the method outputs exactly.

## Tracked references

Search command:

```bash
git grep -n "diagnose_rule_mapped_stance_transitions" -- .
```

Search result summary:

- Active method definition:
  - `module1.py`
- Active callers:
  - none found in tracked files
- Documentation/reference and prior audit mentions:
  - `reports/260701_module1_stance_summary_api_audit.md`
  - `reports/260701_module1_summarize_stance_logic_deletion_audit.md`
  - `reports/260701_module1_group_k3_remaining_alias_decision.md`
  - `reports/260701_module1_group_k_compat_removal_audit.md`
  - `reports/260703_module1_public_api_audit.md`
  - `reports/260703_module1_public_api_stage1b_usage_audit.md`
  - `reports/260703_module1_stage2_diagnostic_duplication_audit.md`

Reference classification:

- Method definition: `module1.py`.
- Active caller: none found.
- Prior audit/report mention: all report hits.
- Active docs/tests/notebooks/examples usage: none found by the prior Stage 1B audit and none found in this tracked-name search.

## Compatibility assessment

Public output shape risk: medium.

The method is public-looking and returns a stable transition table whose column names are dynamically derived from each target's rule-mapped spec. Prior reports cite it as transition-focused review guidance and as a replacement diagnostic after deleting older summary logic.

Convenience value: meaningful.

The output is reproducible, but reproducing it correctly requires spec resolution and multiple ordered post-processing steps. The method prevents repeated caller-side code for:

- dynamic state/rule-case/final-score column names,
- previous/current comparisons,
- null gating,
- first-valid-row correction,
- optional any-stabilization-change handling,
- consistent target-neutral column order.

Deprecate-first assessment:

Deprecation is not warranted from this audit alone. There are no active tracked callers, but the method has low maintenance burden, is fully generic across rule-mapped targets, and exposes a useful transition-focused view not directly returned by `diagnose_rule_mapped_stance()`.

## Recommendation

Recommended next action: keep as public convenience wrapper.

Rationale:

- Runtime comparison proves the method is not uniquely computational, but it is not a pure one-line wrapper.
- The replacement recipe is repetitive and relies on private spec helpers.
- The method is generic across duration, credit, and curve positioning.
- Prior reports present it as transition-focused diagnostic guidance.
- No deletion should be made without an explicit public API cleanup decision.

If the project later wants to reduce public API surface aggressively, the safer path is a deprecate-first PR, not immediate deletion.

## Validation

This task is report-only.

Validation run:

- `git diff --check` - passed with no output.

No Python syntax check was required because no Python files were changed.

No production equality check was required because runtime behavior, schema behavior, YAML config, diagnostics behavior, public API behavior, and model outputs were not changed.

Runtime comparison code was executed from the shell and was not added to the repository.
