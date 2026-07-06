# Module 1 Rule-Mapped Diagnostics Entry-Point Audit

Date: 2026-07-06

## Summary Conclusion

The two working assumptions are correct for tracked production code:

- The only production callers of `diagnose_rule_mapped_stance(...)` are `diagnose_rule_mapped_stance_transitions(...)` and `summarize_rule_mapped_stance_stability(...)`.
- Both callers use `diagnose_rule_mapped_stance(...)` to obtain the base rule-mapped diagnostic `DataFrame`, then perform deterministic post-processing.

The proposed `diagnose_rule_mapped_stance(view=...)` design can be implemented as a narrow diagnostic routing/interface change if the default preserves the current state-level behavior exactly. It should not change scoring, labels, stance calculation, config interpretation, YAML files, model outputs, plotting, historical review behavior, or decision logic.

Classification:

- Interface change: yes, if a new `view` keyword is added to the public method.
- Behavior change: no, if `view="state"` is the default and current output remains byte-for-byte compatible for existing calls.
- Model-output change: no expected model-output change.
- Diagnostic routing change: yes.

## Caller Search Results

Required search commands run:

```bash
rg -n "diagnose_rule_mapped_stance\("
rg -n "\.diagnose_rule_mapped_stance\("
rg -n "diagnose_rule_mapped_stance"
rg -n "diagnose_rule_mapped_stance" --glob '!reports/*.md'
rg -n "summarize_rule_mapped_stance_stability|diagnose_rule_mapped_stance_transitions"
rg -n "from module1 import|import module1|RegimeModule|diagnose_rule_mapped_stance" --glob '*.py' --glob '*.ipynb' --glob '*.md' --glob '*.yaml' --glob '*.yml' docs reports .
find . -maxdepth 3 \( -name '*.ipynb' -o -path './docs/*' -o -path './examples/*' -o -path './tests/*' \) -print
```

Definitions found:

| symbol | location |
|---|---:|
| `diagnose_rule_mapped_stance(...)` | `module1.py:7073` |
| `diagnose_rule_mapped_stance_transitions(...)` | `module1.py:7118` |
| `summarize_rule_mapped_stance_stability(...)` | `module1.py:7261` |

Production direct callers of `diagnose_rule_mapped_stance(...)`:

| caller | call location | classification |
|---|---:|---|
| `diagnose_rule_mapped_stance_transitions(...)` | `module1.py:7134` | active production method call |
| `summarize_rule_mapped_stance_stability(...)` | `module1.py:7270` | active production method call |

Method-call search results for `.diagnose_rule_mapped_stance(`:

| location | classification |
|---|---|
| `module1.py:7134` | active production call through `self` |
| `module1.py:7270` | active production call through `self` |
| `reports/260703_module1_rule_mapped_transition_contract_audit.md:53` | report-only example/reconstruction code |

Non-report tracked search with `rg -n "diagnose_rule_mapped_stance" --glob '!reports/*.md'` found only `module1.py` definitions and the two production calls. No docs, notebooks, examples, tests, YAML files, or comments outside reports were found as active usage sites.

Report-only references were found in prior audit/report files, including:

- `reports/260701_module1_group_k_compat_removal_audit.md:40`
- `reports/260701_module1_group_k3_remaining_alias_decision.md:20`, `:50`, `:51`
- `reports/260701_module1_stance_summary_api_audit.md:16`, `:17`, `:71`, `:72`, `:76`, `:78`
- `reports/260701_module1_summarize_stance_logic_deletion_audit.md:7`, `:68`, `:92`, `:121`, `:122`, `:142`, `:143`
- `reports/260703_module1_public_api_audit.md:69`, `:70`, `:71`, `:113`, `:157`, `:169`, `:170`, `:198`, `:199`, `:214`
- `reports/260703_module1_public_api_stage1b_usage_audit.md:14`, `:15`, `:56`, `:57`, `:81`, `:88`, `:167`, `:168`, `:189`, `:190`
- `reports/260703_module1_rule_mapped_stability_summary_api_overlap_audit.md:13`, `:55`, `:75`, `:76`, `:89`, `:95`, `:100`, `:136`, `:174`
- `reports/260703_module1_rule_mapped_transition_contract_audit.md:9`, `:15`, `:18`, `:53`, `:122`, `:123`, `:142`, `:186`
- `reports/260703_module1_stage2_diagnostic_duplication_audit.md:26`, `:100`, `:146`, `:152`, `:159`, `:191`, `:239`, `:244`, `:251`, `:726`, `:729`, `:755`, `:756`, `:775`, `:820`

Public/external usage risk:

- The method is public-looking because it is a non-underscore `RegimeModule` method and prior public API audits classify it as a public generic diagnostic API.
- No tracked external caller, notebook, example, test, or docs usage was found outside reports.
- Renaming the method or changing existing parameters would still be risky because public-looking diagnostic methods may be used outside the repository. Adding an optional keyword-only `view` parameter with the existing behavior as the default is the least risky interface change.

## Current Call Graph

Current production relationship:

```text
diagnose_rule_mapped_stance(...)
  -> _resolve_rule_mapped_diagnostic_config(...)
  -> _derive_rule_mapped_diagnostic_spec_from_context(...)
  -> _trace_rule_mapped_stance_score(...)
  -> _ensure_rule_mapped_stabilization_change_flags(...)
  -> _rule_mapped_selected_columns(...)
  -> returns selected diagnostic DataFrame copy

diagnose_rule_mapped_stance_transitions(...)
  -> _resolve_rule_mapped_diagnostic_config(...)
  -> _derive_rule_mapped_diagnostic_spec_from_context(...)
  -> diagnose_rule_mapped_stance(..., include_scores=False, include_raw_states=True, include_stabilized_states=True, include_rule_case=True, include_labels=True)
  -> builds transition-focused DataFrame

summarize_rule_mapped_stance_stability(...)
  -> _resolve_rule_mapped_diagnostic_config(...)
  -> _derive_rule_mapped_diagnostic_spec_from_context(...)
  -> diagnose_rule_mapped_stance(..., include_scores=False, include_raw_states=True, include_stabilized_states=True, include_rule_case=True, include_labels=True)
  -> builds summary dict of DataFrames
```

## Current Return-Value And Post-Processing Relationship

`diagnose_rule_mapped_stance(...)` currently returns a `pd.DataFrame` copy: `diagnostics[selected_cols].copy()`.

The returned `DataFrame` is selected from `_trace_rule_mapped_stance_score(...)` output after stabilization-change flags are ensured. The selected columns are controlled by:

- `include_scores`
- `include_raw_states`
- `include_stabilized_states`
- `include_rule_case`
- `include_labels`

Default state-level output includes score inputs, raw states, stabilized states, stabilization change flags, rule-case and score columns, rule metadata columns, stance label, and strength label when those columns exist.

`diagnose_rule_mapped_stance_transitions(...)` consumes the base `DataFrame` by:

- preserving the diagnostic index as the transition index;
- adding a `date` column from `diagnostics.index`;
- copying raw and stabilized state columns in spec order;
- copying the rule-case column and final score column;
- deriving previous rule case and previous final score with `.shift(1)`;
- deriving rule-case changed and score-change columns;
- copying stance and strength labels;
- copying the optional `stabilization_change_any_col` when present;
- forcing the first valid rule-case row's changed flag to `False`.

`summarize_rule_mapped_stance_stability(...)` consumes the base `DataFrame` by:

- dropping null rule cases, scores, stance labels, and strength labels;
- counting rule-case transitions with `_count_series_changes(...)`;
- calculating unique, most-frequent, ratio, and valid-count rule-case metrics;
- calculating score mean, median, min, max, standard deviation, and valid counts;
- calculating stance/strength share fields through `_series_value_shares(...)`;
- adding duration-specific positive/neutral/negative stance shares for `target == "duration"`;
- building `component_state_summary` with `_rule_mapped_component_state_summary(...)`;
- building `mapped_score_distribution` with `_rule_mapped_score_distribution(...)`;
- returning a dict with `component_state_summary`, `rule_case_summary`, `mapped_score_distribution`, and `score_summary`.

Neither post-processing function appears to depend on side effects or printing from `diagnose_rule_mapped_stance(...)`; there are no prints in the inspected path. Both depend on implicit behavior from the base method:

- date filtering through the base `start` and `end` arguments passed into `_trace_rule_mapped_stance_score(...)`;
- the index shape and ordering returned by the base diagnostic output;
- dynamic spec-derived column names;
- column presence governed by the `include_*` flags;
- the stabilized change flag columns inserted by `_ensure_rule_mapped_stabilization_change_flags(...)`;
- current selected-column ordering from `_rule_mapped_selected_columns(...)`;
- `.copy()` isolation of the selected diagnostic output.

## Recursion-Risk Analysis

If `diagnose_rule_mapped_stance(...)` becomes a dispatcher and `view="transitions"` delegates to `diagnose_rule_mapped_stance_transitions(...)`, the current implementation would recurse unless the transition function stops calling the public dispatcher or explicitly requests the state view.

Unsafe shape:

```python
def diagnose_rule_mapped_stance(..., view="state"):
    if view == "transitions":
        return self.diagnose_rule_mapped_stance_transitions(...)

def diagnose_rule_mapped_stance_transitions(...):
    diagnostics = self.diagnose_rule_mapped_stance(...)
```

This can produce a loop or accidental dispatcher re-entry if defaults or future edits drift.

Safest recursion-avoidance strategy:

- Move the current state-level implementation into a private helper such as `_diagnose_rule_mapped_stance_state(...)`.
- Make `diagnose_rule_mapped_stance(...)` a thin public dispatcher.
- Have `view="state"` call `_diagnose_rule_mapped_stance_state(...)`.
- Have `diagnose_rule_mapped_stance_transitions(...)` and `summarize_rule_mapped_stance_stability(...)` call `_diagnose_rule_mapped_stance_state(...)` directly for their base rows, or accept a precomputed base diagnostic that was produced by that helper.

## Recommended Implementation Shape

Recommended minimal implementation:

1. Extract the current body of `diagnose_rule_mapped_stance(...)` into a private helper, likely `_diagnose_rule_mapped_stance_state(...)`, preserving the existing signature and return value.
2. Add keyword-only `view: str = "state"` to `diagnose_rule_mapped_stance(...)`.
3. Dispatch:
   - `view == "state"`: call `_diagnose_rule_mapped_stance_state(...)` and preserve the current default output.
   - `view == "transitions"`: call `diagnose_rule_mapped_stance_transitions(...)`.
   - `view == "stability"`: call `summarize_rule_mapped_stance_stability(...)`.
4. Update `diagnose_rule_mapped_stance_transitions(...)` and `summarize_rule_mapped_stance_stability(...)` to obtain their base rows from `_diagnose_rule_mapped_stance_state(...)`, not from the public dispatcher.
5. Keep existing `diagnose_rule_mapped_stance_transitions(...)` and `summarize_rule_mapped_stance_stability(...)` public methods for compatibility unless a separate public API deprecation decision is made.

The alternative design, adding an optional precomputed base diagnostic to the two post-processing methods, is also viable but less minimal for the public entry-point task. It creates more signatures to reason about. If used, the parameter should be private/keyword-only and should not change existing public behavior. It would be useful only if duplicate base calculation becomes a measurable issue or if tests need direct injection.

Do not rename public functions as part of the entry-point change. Do not move outputs between functions. Keep transition and stability output builders in their current functions or private helpers behind those functions.

## Risks And Limitations

Risks:

- Adding `view` changes the public method signature even if backward-compatible.
- `diagnose_rule_mapped_stance(...)` would return different object types by view: `DataFrame` for `state`, `DataFrame` for `transitions`, and `dict` for `stability`. This should be documented in the method docstring.
- Invalid `view` handling should raise a clear `ValueError`; it should not silently fall back to state output.
- Existing callers that pass unexpected keyword arguments should continue to fail in the same general way; avoid accepting broad `**kwargs`.
- The post-processing methods rely on base index ordering, dynamic columns, and exact include flags. Any helper extraction must preserve those details exactly.

Limitations:

- This was a static audit plus prior-report review. No runtime equality check was run in this task because production code was not changed.
- External usage outside the tracked repository cannot be ruled out.
- Prior report files are historical references, not active production callers.

## Validation Commands Run

Search and inspection commands:

```bash
git status --short --branch
git branch --show-current
git log --oneline -5
git fetch --prune origin
git branch -r --list 'origin/codex/session/*'
rg -n "diagnose_rule_mapped_stance\("
rg -n "\.diagnose_rule_mapped_stance\("
rg -n "diagnose_rule_mapped_stance"
rg -n "diagnose_rule_mapped_stance" --glob '!reports/*.md'
rg -n "summarize_rule_mapped_stance_stability|diagnose_rule_mapped_stance_transitions"
rg -n "from module1 import|import module1|RegimeModule|diagnose_rule_mapped_stance" --glob '*.py' --glob '*.ipynb' --glob '*.md' --glob '*.yaml' --glob '*.yml' docs reports .
find . -maxdepth 3 \( -name '*.ipynb' -o -path './docs/*' -o -path './examples/*' -o -path './tests/*' \) -print
nl -ba module1.py | sed -n '7040,7365p'
nl -ba reports/260703_module1_rule_mapped_transition_contract_audit.md | sed -n '1,210p'
nl -ba reports/260703_module1_rule_mapped_stability_private_helper_overlap_audit.md | sed -n '1,235p'
```

No production Python files were changed, so no `python -m py_compile` production syntax validation was required for this audit.

## Model Output Impact

No model outputs changed in this task because this was audit-only and modified only this report.

For the proposed future implementation, model outputs would not be expected to change if the work is limited to diagnostic routing and preserves the current state, transition, and stability calculations exactly.
