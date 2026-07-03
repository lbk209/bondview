# Module 1 Public API Stage 1B Usage Audit

Date: 2026-07-03

## Short conclusion

Stage 1B starts from the PR #51 candidate list in `reports/260703_module1_public_api_audit.md` and searches the broader tracked usage surfaces that PR #51 intentionally ignored.

Broader usage evidence did not reveal active docs, README, examples, tests, or notebook usage for any candidate method. The only broader references found are in prior committed reports. Those reports are useful compatibility and design evidence, but they are not active caller evidence.

The strongest Stage 2 candidates are target-specific diagnostic duplication or genericization candidates:

- `diagnose_historical_review_case()`
- `diagnose_rule_mapped_stance_transitions()`
- `summarize_rule_mapped_stance_stability()`
- `compare_credit_input_smoothing_effect()`
- `compare_curve_input_smoothing_effect()`
- `compare_curve_move_driver_threshold_effect()`
- `compare_curve_positioning_stabilization_cases()`
- `compare_credit_stance_persistence_cases()`

No deletion decision is made in Stage 1B. Stage 1B only records usage evidence and recommends follow-up audit routing.

## Scope confirmation

Searched broader tracked usage surfaces:

- `docs/`
- `reports/`
- `tests/`
- `examples/`
- tracked notebooks: `*.ipynb`
- README files
- other tracked Markdown files

Tracked files found in those surfaces:

- `AGENTS.md`
- `README.md`
- `docs/chatgpt_context_bondview.md`
- `docs/module1_stance_score_calculation_logic.md`
- committed files under `reports/`

No tracked files were found under `tests/`, `examples/`, or notebook patterns.

Runtime/source/config files were not modified. Runtime source files were not used as caller evidence in this Stage 1B report, except PR #51's report was used as the candidate source.

Untracked external callers remain unknowable from repository search.

## Candidate usage table

| method name | PR #51 classification | broader references found | strongest reference type | active usage evidence? | updated classification | notes |
|---|---|---|---|---|---|---|
| `run_module1_historical_review()` | `compatibility_candidate` | PR #51 report only | generated report mention only | No | `needs_compatibility_decision` | No docs/tests/examples usage. Compatibility concern still comes from wrapper/legacy evidence in source and PR #51. |
| `diagnose_historical_review_case()` | `diagnostic_duplication_candidate` | PR #51 report only | generated report mention only | No | `needs_stage2_duplication_audit` | Likely overlap to test against `review_historical_cases(output="diagnostic")`. |
| `diagnose_rule_mapped_stance_transitions()` | `diagnostic_duplication_candidate` | prior reports and PR #51 | historical/audit mention | No | `needs_stage2_duplication_audit` | Reports describe it as useful transition-focused replacement coverage, but not active external usage. |
| `summarize_rule_mapped_stance_stability()` | `diagnostic_duplication_candidate` | prior reports and PR #51 | historical/audit mention | No | `needs_stage2_duplication_audit` | Reports describe public output values and alias impact; stronger compatibility weight than a pure cleanup candidate. |
| `compare_credit_input_smoothing_effect()` | `diagnostic_duplication_candidate` | multiple prior Group F/G/H reports and PR #51 | historical/audit mention | No | `needs_stage2_duplication_audit` | Prior reports explicitly say preserve public API while genericizing internals. |
| `compare_curve_input_smoothing_effect()` | `diagnostic_duplication_candidate` | multiple prior Group F/G/H reports and PR #51 | historical/audit mention | No | `needs_stage2_duplication_audit` | Same pattern as credit smoothing diagnostic. |
| `compare_curve_move_driver_threshold_effect()` | `diagnostic_duplication_candidate` | multiple prior reports and PR #51 | historical/audit mention | No | `needs_stage2_duplication_audit` | Prior reports frame it as a specialized wrapper over future generic parameter-effect mechanics. |
| `compare_curve_positioning_stabilization_cases()` | `diagnostic_duplication_candidate` | Group G/H reports, cleanup reclassification report, PR #51 | historical/audit mention | No | `needs_stage2_duplication_audit` | Public contract is documented in reports; Stage 2 should preserve public result shape if genericized. |
| `compare_credit_stance_persistence_cases()` | `diagnostic_duplication_candidate` | Group H report, cleanup reclassification report, PR #51 | historical/audit mention | No | `needs_stage2_duplication_audit` | Report-only evidence, but public result keys are documented. |
| `update_horizons()` | `cleanup_candidate` | PR #51 report only | generated report mention only | No | `cleanup_candidate` | No broader active usage found; deletion still requires separate utility/API audit. |
| `save_data()` | `cleanup_candidate` | PR #51 report only | generated report mention only | No | `cleanup_candidate` | No broader active usage found; likely utility cleanup, not diagnostic duplication. |
| `inspect_module1_results()` | `cleanup_candidate` | PR #51 report only | generated report mention only | No | `cleanup_candidate` | No broader active usage found; likely inspection utility cleanup. |
| `compare_horizon_cases()` | `needs_follow_up` | Group H report and PR #51 | historical/audit mention | No | `keep_user_facing` | Group H documents a public batch diagnostic contract; not a diagnostic duplication Stage 2 target. |
| `validate_historical_expected_labels()` | `needs_follow_up` | PR #51 report only | generated report mention only | No | `defer` | Public validator with no broader active usage; not a target-specific diagnostic duplication candidate. |
| `plot_historical_review_case()` | `needs_follow_up` | PR #51 report only | generated report mention only | No | `keep_user_facing` | Plotting API; no active docs found, but user-facing by purpose and not a diagnostic duplication target. |
| `plot_target_comparison()` | `needs_follow_up` | PR #51 report only | generated report mention only | No | `keep_user_facing` | Plotting API; no active docs found, but user-facing by purpose and not a diagnostic duplication target. |

## Reference details

`run_module1_historical_review()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report. Classified as `compatibility_candidate` because the method is a wrapper with legacy-context wording. Report-only; not active usage.

`diagnose_historical_review_case()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report. Notes possible overlap with `review_historical_cases(output="diagnostic")`. Report-only; not active usage.

`diagnose_rule_mapped_stance_transitions()`:

- `reports/260701_module1_stance_summary_api_audit.md`: Describes the method as transition-focused coverage for schema-backed rule-mapped targets. Historical/audit mention; useful design evidence.
- `reports/260701_module1_summarize_stance_logic_deletion_audit.md`: Recommends it as replacement guidance for transition-focused review after deleting `summarize_stance_logic(...)`. Historical/audit mention.
- `reports/260701_module1_group_k3_remaining_alias_decision.md` and `reports/260701_module1_group_k_compat_removal_audit.md`: Mention that transition diagnostics are not affected by a curve move-driver alias. Historical/audit mention.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`summarize_rule_mapped_stance_stability()`:

- `reports/260701_module1_stance_summary_api_audit.md`: Describes output shape and duration coverage. Historical/audit mention.
- `reports/260701_module1_summarize_stance_logic_deletion_audit.md`: Recommends it as replacement summary-level diagnostic. Historical/audit mention.
- `reports/260701_module1_group_k3_remaining_alias_decision.md`: Identifies one public diagnostic summary value affected by alias behavior and says the method still appears useful. Historical/audit mention with compatibility weight.
- `reports/260701_module1_group_k_compat_removal_audit.md`: Mentions impact on the diagnostic spec consumer path. Historical/audit mention.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`compare_credit_input_smoothing_effect()`:

- `reports/260630_module1_group_f_diagnostic_contract_audit.md`: Documents public signature, result keys, output columns, and recommends migrating behind existing public API. Historical/audit mention with strong compatibility weight.
- `reports/260630_module1_group_h_summary_display_audit.md`: Documents result key matrix and runtime-observed table contracts. Historical/audit mention with strong compatibility weight.
- `reports/260629_module1_rule_score_helper_usage_audit.md`, `reports/260630_module1_credit_adjustment_j1_audit.md`, `reports/260630_module1_group_g_stabilization_case_audit.md`, `reports/260630_module1_remaining_cleanup_reclassification_audit.md`: Cleanup/audit context. Report-only design evidence.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`compare_curve_input_smoothing_effect()`:

- `reports/260630_module1_group_f_diagnostic_contract_audit.md`: Documents public signature, result keys, output columns, and recommends preserving public API during migration. Historical/audit mention with strong compatibility weight.
- `reports/260630_module1_group_h_summary_display_audit.md`: Documents result key matrix and runtime-observed table contracts. Historical/audit mention with strong compatibility weight.
- `reports/260626_module1_hardcoded_component_scores_audit.md`, `reports/260629_module1_rule_score_helper_usage_audit.md`, `reports/260629_module1_target_bucket_accessors_audit.md`, `reports/260630_module1_group_g_stabilization_case_audit.md`, `reports/260630_module1_remaining_cleanup_reclassification_audit.md`: Cleanup/audit context. Report-only design evidence.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`compare_curve_move_driver_threshold_effect()`:

- `reports/260630_module1_group_f_diagnostic_contract_audit.md`: Says it fits a generic parameter-effect pattern but should remain a specialized public wrapper; documents public contract. Historical/audit mention with strong compatibility weight.
- `reports/260630_module1_group_h_summary_display_audit.md`: Documents result key matrix and runtime-observed table contracts. Historical/audit mention with strong compatibility weight.
- `reports/260626_module1_hardcoded_component_scores_audit.md`, `reports/260629_module1_rule_score_helper_usage_audit.md`, `reports/260629_module1_target_bucket_accessors_audit.md`, `reports/260630_module1_group_g_stabilization_case_audit.md`, `reports/260630_module1_remaining_cleanup_reclassification_audit.md`: Cleanup/audit context. Report-only design evidence.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`compare_curve_positioning_stabilization_cases()`:

- `reports/260630_module1_group_g_stabilization_case_audit.md`: Defines it as the active public stabilization-case comparison and recommends preserving public method signature, result keys, case ids, column order, value semantics, and default windows. Historical/audit mention with strong compatibility weight.
- `reports/260630_module1_group_h_summary_display_audit.md`: Documents result key matrix and runtime-observed table contracts. Historical/audit mention with strong compatibility weight.
- `reports/260630_module1_remaining_cleanup_reclassification_audit.md`: Classifies it as a public diagnostic entry. Report-only design evidence.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`compare_credit_stance_persistence_cases()`:

- `reports/260630_module1_group_h_summary_display_audit.md`: Documents public signature, result key matrix, and table contracts. Historical/audit mention with strong compatibility weight.
- `reports/260630_module1_remaining_cleanup_reclassification_audit.md`: Classifies it as a public diagnostic entry and generic persistence-case candidate. Report-only design evidence.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`update_horizons()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report only. No broader active usage.

`save_data()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report only. No broader active usage.

`inspect_module1_results()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report only. No broader active usage.

`compare_horizon_cases()`:

- `reports/260630_module1_group_h_summary_display_audit.md`: Documents it as a public batch comparison diagnostic returning one flat DataFrame selected by `output`; notes runtime inspection was not run because it may be expensive. Historical/audit mention with user-facing contract weight.
- `reports/260703_module1_public_api_audit.md`: PR #51 report-only mention.

`validate_historical_expected_labels()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report only. No broader active usage.

`plot_historical_review_case()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report only. No broader active usage.

`plot_target_comparison()`:

- `reports/260703_module1_public_api_audit.md`: PR #51 generated report only. No broader active usage.

## Candidates with no broader active usage

No candidate had active docs, README, examples, tests, or notebook usage in tracked files.

Candidates with only report references:

- `run_module1_historical_review()`
- `diagnose_historical_review_case()`
- `diagnose_rule_mapped_stance_transitions()`
- `summarize_rule_mapped_stance_stability()`
- `compare_credit_input_smoothing_effect()`
- `compare_curve_input_smoothing_effect()`
- `compare_curve_move_driver_threshold_effect()`
- `compare_curve_positioning_stabilization_cases()`
- `compare_credit_stance_persistence_cases()`
- `update_horizons()`
- `save_data()`
- `inspect_module1_results()`
- `compare_horizon_cases()`
- `validate_historical_expected_labels()`
- `plot_historical_review_case()`
- `plot_target_comparison()`

The diagnostic comparison methods have report-only compatibility evidence because prior reports documented public table contracts. That is stronger than a stale mention, but still not active usage.

## Recommended Stage 2 target list

Stage 2 should be a target-specific diagnostic duplication audit for:

- `diagnose_historical_review_case()` - compare against `review_historical_cases(output="diagnostic")` and decide whether it adds unique behavior or only wraps a single output mode.
- `diagnose_rule_mapped_stance_transitions()` - compare against `diagnose_rule_mapped_stance()` plus simple transition derivations; determine whether transition columns are unique enough to preserve as a public method.
- `summarize_rule_mapped_stance_stability()` - compare against `diagnose_rule_mapped_stance()` and `trace_stance_score()` plus grouping/summary derivations; account for public summary vocabulary such as curve move-driver component names.
- `compare_credit_input_smoothing_effect()` - compare target-specific reconstruction/reporting against any generic input-preparation diagnostic core candidates; preserve current public output keys and table columns if migrated.
- `compare_curve_input_smoothing_effect()` - same as credit input smoothing, with curve-specific component and stance reconstruction.
- `compare_curve_move_driver_threshold_effect()` - compare against a generic parameter-effect diagnostic concept; decide whether it remains a specialized wrapper.
- `compare_curve_positioning_stabilization_cases()` - compare against a generic rule-mapped stabilization-case comparison core; preserve result keys, cases, DataFrame columns, and value semantics.
- `compare_credit_stance_persistence_cases()` - compare against a generic persistence/stabilization-case diagnostic concept while accounting for credit-specific windows and credit adjustment outputs.

## Candidates to exclude from Stage 2

Exclude from target-specific diagnostic duplication audit:

- `run_module1_historical_review()` - compatibility/wrapper decision, not target-specific diagnostic duplication.
- `update_horizons()` - utility/API cleanup audit, not diagnostic duplication.
- `save_data()` - utility/API cleanup audit, not diagnostic duplication.
- `inspect_module1_results()` - inspection utility cleanup audit, not diagnostic duplication.
- `compare_horizon_cases()` - public batch historical review diagnostic; if revisited, handle as separate historical-review API audit, not target-specific duplication.
- `validate_historical_expected_labels()` - validation utility; defer unless validation API cleanup is requested.
- `plot_historical_review_case()` - plotting API; keep/defer unless plotting API cleanup is requested.
- `plot_target_comparison()` - plotting API; keep/defer unless plotting API cleanup is requested.

## Compatibility notes

Candidates requiring explicit compatibility decision before deletion or deprecation:

- `run_module1_historical_review()` - wrapper/legacy context makes this a compatibility-sensitive public convenience API even without active tracked usage.
- `compare_credit_input_smoothing_effect()` - prior reports document public output contracts and recommend preserving public API during genericization.
- `compare_curve_input_smoothing_effect()` - same compatibility concern as credit input smoothing.
- `compare_curve_move_driver_threshold_effect()` - prior reports call for a specialized wrapper if genericized.
- `compare_curve_positioning_stabilization_cases()` - prior reports explicitly require preserving signature, result keys, cases, columns, ordering, semantics, and default windows.
- `compare_credit_stance_persistence_cases()` - prior reports document public result keys and tables.
- `compare_horizon_cases()` - public batch diagnostic contract is documented in Group H report.
- `summarize_rule_mapped_stance_stability()` - prior reports identify useful public summary output and public vocabulary impact.

Candidates with no active usage and lower compatibility evidence:

- `diagnose_historical_review_case()`
- `update_horizons()`
- `save_data()`
- `inspect_module1_results()`
- `validate_historical_expected_labels()`
- `plot_historical_review_case()`
- `plot_target_comparison()`

These still should not be deleted based solely on Stage 1B.

## Validation

This task is report-only.

Validation run:

- `git diff --check` - passed with no output.

No Python syntax check was required because no Python files were changed.

No production equality check was required because runtime behavior, schema behavior, YAML config, diagnostics behavior, public API behavior, and model outputs were not changed.
