# Module 1 historical target-filter consolidation review

## Scope and implementation

Historical case filtering now resolves every individual configured target and target group through one call to:

```python
self.analysis.resolve_target(target, level, allow_group=True)
```

`_filter_historical_cases_by_target()` uses the returned `TargetResolution.related_targets` only as membership keys while iterating the existing case-table rows. It therefore preserves case membership and row order without reconstructing rows in group-member or set order.

The following duplicate historical configuration interpreters were removed:

- `_historical_review_target_aliases()`
- `_historical_review_target_groups()`

Removing the group interpreter made the `self.module1_config` constructor mirror unused. Repository-wide searches found no internal use, live consumer, notebook/example use, or current documented `Module1HistoricalAnalysis` contract, so the assignment was removed without a replacement property or forwarder. `component_config` and `exposure_stance_config` remain because historical validation and plotting use them.

No other production file, YAML file, data file, public method signature, historical loading path, calculation path, or plotting path changed.

## Intentional error-contract standardization

Historical target filtering now lets `Module1Analysis.resolve_target()` exceptions propagate unchanged. It no longer reconstructs the historical-specific messages `Unable to resolve historical review target filter: ...` or `Unsupported historical review level: ...`.

The intentionally standardized categories are:

- unknown targets with no level;
- unknown targets at component or stance level;
- component aliases requested as stance targets;
- stance aliases requested as component targets;
- unsupported levels;
- empty and `None` targets where the authoritative resolver supplies a different message;
- non-string invalid targets where the authoritative resolver raises during normalization.

Exception types and failure conditions remain unchanged. Target groups with no member at the requested level already used the authoritative resolver and retain the same messages. No ambiguous group error applies to the filter because it intentionally calls the resolver with `allow_group=True`; configured multi-member groups resolve to ordered `related_targets` instead.

## Consumer audit

The `self.module1_config` audit covered executable Python, tracked notebooks/examples, README/current documentation, and historical reports. The only live uses were the constructor assignment and the removed group interpreter. Historical reports that mention older state ownership describe the pre-split implementation and do not establish a current supported attribute contract.

No replacement alias map, group map, compatibility method, wrapper, adapter, or one-use configuration reconstruction was introduced.

## Validation results

A temporary pre-edit baseline was captured and was not committed.

- Configured resolver/filter matrix: 144 requests across every component and stance canonical name, score-output alias, label-output alias, configured target group, and `None`/component/stance level form.
- Successful requests: 101/101 retained exact canonical resolution, normalized input, `related_targets`, configured member order, selected case values, and selected row order.
- Configured invalid requests: 40 messages intentionally changed to the authoritative resolver forms; 3 group-without-level-member errors were already authoritative and remained exact.
- Additional invalid requests: unknown targets at every level, wrong-level aliases, unsupported levels, normalized inputs, empty/`None`/list-valued targets, canonical/group namespace overlap, and groups without requested-level members preserved exception types and failure conditions.
- Downstream empty-result handling remained exact.
- Historical reviews: all eight supported outputs matched exactly for 11 representative canonical, alias, group, component-level, stance-level, context-ID, validation-only, and relevance scenarios (88 comparisons total). Values, indexes, columns/order, row order, practical dtypes, and return types were checked.
- Historical loading: successful loading, strict invalid-label raising, warning-mode loading, retained validation evidence, and context/case state before and after failure remained exact.
- Module 1 outputs: features, component scores, component labels, stance scores, and exposure stance matched exact pre-edit values and hashes.
- Python compilation and import smoke checks passed for `module1_historical_analysis.py`, `module1_analysis.py`, `module1_calculator.py`, `module1_diagnostics.py`, `module1_sensitivity_diagnostics.py`, and `module1_schema.py`.
- AST checks confirmed all public method signatures are unchanged and the filter contains exactly one `resolve_target()` call.
- Repository searches confirmed both duplicate historical interpreters and historical-specific resolver-error reconstruction are absent, the unused mirror has no live references, and `Module1HistoricalAnalysis.resolve_historical_event_window()` remains the sole historical context-ID resolver.
- `git diff --check` passed.
- No YAML or data diff exists.

## Behavior impact

Only invalid historical filter message wording intentionally changed. Accepted inputs, target normalization, canonical results, configured group interpretation/order, selected historical cases/order, review values/schemas, plotting, historical load-state behavior, configuration interpretation, and Module 1 model outputs did not change.

There were no validation limitations or unresolved implementation issues.
