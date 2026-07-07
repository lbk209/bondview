# Module 1 Public API Stage 1 Audit

Date: 2026-07-03

## Short conclusion

This restricted-scope Stage 1 audit found several public or public-looking Module 1 methods with no scoped callers beyond their own definitions. That is not enough to recommend deletion, because this audit intentionally ignored docs, reports, notebooks, tests, examples, README files, and untracked files.

The strongest next-stage candidates are:

- `run_module1_historical_review()` as a `compatibility_candidate`, because its docstring calls it a convenience wrapper and says it no longer returns the legacy `review_historical_context()` bundle.
- `diagnose_historical_review_case()`, `diagnose_rule_mapped_stance_transitions()`, `summarize_rule_mapped_stance_stability()`, and the specialized `compare_*` diagnostic methods as `diagnostic_duplication_candidate` or `needs_follow_up`, because they are public-looking diagnostics with little or no scoped caller evidence.
- `update_horizons()`, `save_data()`, and `inspect_module1_results()` as lightweight `cleanup_candidate` / `needs_follow_up` items because this restricted scan found no scoped runtime callers.

No deletion decision is made in Stage 1. Absence of references inside the scoped files only means no evidence was found within this intentionally restricted scope.

## Scope confirmation

Files searched:

- `module1.py`
- `module1_schema.py`
- `data/module1_config.yaml`
- tracked `*.yaml` / `*.yml` files: `data/module1_config.yaml`, `data/historical_context.yaml`

Common source types intentionally ignored:

- docs
- reports, except for writing this new report
- notebooks
- tests
- examples
- README files
- untracked files

The requested report path was `reports/report-20260703-module1-public-api-audit.md`, but AGENTS.md requires `reports/YYMMDD_<scope>_<topic>_<report_type>.md`. This report therefore uses `reports/260703_module1_public_api_audit.md`.

## Method inventory

| method name | category | public/public-looking reason | references within scoped files | YAML/config references | compatibility/legacy keyword evidence | classification | notes |
|---|---|---|---|---|---|---|---|
| `TargetResolution.to_target_info()` | data retrieval / context | Does not start with `_`; conversion API on public-looking dataclass | Called by `_resolve_target()` at `module1.py:6026` | None | None | `keep_active` | Active internal context path. |
| `RegimeModule.load_core_files()` | data retrieval / context | Public loader | Classmethod body calls local loaders through `instance.load_*`; no other scoped caller | None | None | `keep_active` | Public orchestration entry point for core files. |
| `RegimeModule.validate_horizons()` | validation / schema-related | Public validator | Called by `update_horizons()`, `compare_horizon_cases()`, `load_module1_config()` | Horizon keys in `data/module1_config.yaml` | None | `keep_active` | Active validation helper. |
| `RegimeModule.update_horizons()` | validation / schema-related | Public mutator | Definition only in scoped call scan | None | None | `cleanup_candidate` | No scoped caller, but likely user-facing; needs broader audit before any action. |
| `RegimeModule.compare_horizon_cases()` | diagnostics / tracing | Public comparison method | Definition only in AST call scan; internally runs pipeline and `review_historical_cases()` | Horizon keys in config | `temporary` describes temporary instances at `module1.py:457` | `needs_follow_up` | Public batch diagnostic; no deletion inference from Stage 1. |
| `RegimeModule.load_series_config()` | data retrieval / context | Public loader | Called by `load_core_files()` and `load_data()` | None | None | `keep_active` | Active data loading path. |
| `RegimeModule.download_series()` | data retrieval / context | Public data acquisition method | Called by `load_data()` | None | None | `keep_active` | Active data loading path. |
| `RegimeModule.check_frequency_sanity()` | validation / schema-related | Public validation-like method | Called by `load_data()` | None | None | `keep_active` | Active data quality check. |
| `RegimeModule.load_local_data()` | data retrieval / context | Public loader | Called by `load_series_config()` and `load_data()` | None | None | `keep_active` | Active data loading path. |
| `RegimeModule.load_data()` | data retrieval / context | Public loader | Called by `load_core_files()` and `calculate_features()` | None | None | `keep_active` | Active pipeline prerequisite path. |
| `RegimeModule.save_data()` | data retrieval / context | Public persistence method | Definition only in scoped call scan | None | None | `cleanup_candidate` | No scoped caller; likely external utility surface. |
| `RegimeModule.load_module1_config()` | validation / schema-related | Public config loader | Called by `load_core_files()`, `calculate_features()`, and many runtime/diagnostic guards | `data/module1_config.yaml` is the loaded config | None | `keep_active` | Central active config path. |
| `RegimeModule.calculate_features()` | scoring / calculation | Public calculation method | Called by `compare_horizon_cases()`, `run_module1_pipeline()`, diagnostics guards | Feature definitions in config | None | `keep_active` | Active Module 1 layer. |
| `RegimeModule.align_component_scores()` | scoring / calculation | Public-looking calculation method | Called by `calculate_component_scores()` | Component score outputs in config | None | `keep_active` | Public-looking but actively used internally. |
| `RegimeModule.calculate_component_scores()` | scoring / calculation | Public calculation method | Called by `compare_horizon_cases()`, `run_module1_pipeline()`, diagnostics guards | Component score functions in config | None | `keep_active` | Active Module 1 layer. |
| `RegimeModule.calculate_component_labels()` | scoring / calculation | Public calculation method | Called by `compare_horizon_cases()`, `run_module1_pipeline()`, diagnostics guards | Component label config | None | `keep_active` | Active Module 1 layer. |
| `RegimeModule.calculate_exposure_stance()` | scoring / calculation | Public calculation method | Called by `compare_horizon_cases()`, `run_module1_pipeline()`, diagnostics, and `compare_credit_stance_persistence_cases()` | Exposure stance functions in config | None | `keep_active` | Active Module 1 layer. |
| `RegimeModule.run_module1_pipeline()` | scoring / calculation | Public orchestration method | Called by `run_module1_historical_review()` | None | None | `keep_active` | Active convenience orchestration path. |
| `RegimeModule.load_historical_context()` | data retrieval / context | Public historical context loader | Called by `compare_horizon_cases()` and `run_module1_historical_review()` | `data/historical_context.yaml` is the loaded config | None | `keep_active` | Active review prerequisite. |
| `RegimeModule.validate_historical_expected_labels()` | validation / schema-related | Public validator | Definition and error-message mention only in scoped scan | Historical context labels in YAML | None | `needs_follow_up` | Public validation command; no scoped caller beyond user-facing error guidance. |
| `RegimeModule.review_historical_cases()` | diagnostics / tracing | Public review method | Called by `compare_horizon_cases()`, `diagnose_historical_review_case()`, `run_module1_historical_review()`, plotting guidance | Historical expectations in YAML | None | `keep_active` | Main active historical review API. |
| `RegimeModule.diagnose_historical_review_case()` | diagnostics / tracing | Public diagnostic method | Definition only in AST call scan; internally delegates to `review_historical_cases()` | Historical context YAML indirectly | None | `diagnostic_duplication_candidate` | May overlap `review_historical_cases(output="diagnostic")`; needs Stage 2. |
| `RegimeModule.run_module1_historical_review()` | compatibility / wrappers / aliases | Public wrapper | Definition only in scoped call scan; internally calls `run_module1_pipeline()`, `load_historical_context()`, `review_historical_cases()` | Historical context YAML indirectly | `wrapper` and `legacy` in docstring at `module1.py:4883`, `module1.py:4899` | `compatibility_candidate` | Strongest compatibility clue in restricted scope. |
| `RegimeModule.inspect_module1_results()` | reporting | Public inspection method | Definition only in scoped call scan | None | None | `cleanup_candidate` | No scoped caller; likely notebook/user utility, which this audit intentionally ignored. |
| `RegimeModule.get_target_context()` | data retrieval / context | Public context API | Called by historical review, comparison dataset, raw input lookup, tracing diagnostics | Target groups in config metadata | None | `keep_active` | Active context boundary for diagnostics/plotting. |
| `RegimeModule.build_target_comparison_dataset()` | data retrieval / context | Public comparison dataset API | Called by `plot_target_comparison()` | Target groups in config metadata | `legacy` in docstring at `module1.py:6158` says compare path is independent of legacy plot modes | `keep_active` | Active consumer-neutral path; legacy mention does not itself suggest cleanup. |
| `RegimeModule.raw_inputs_for_target()` | data retrieval / context | Public context helper | Called by plotting helper at `module1.py:9141` | Target config indirectly | None | `keep_active` | Active plotting/context helper. |
| `RegimeModule.diagnose_rule_mapped_stance()` | diagnostics / tracing | Public generic diagnostic method | Called by `diagnose_rule_mapped_stance_transitions()` and `summarize_rule_mapped_stance_stability()` | Rule-mapped config for duration, credit, curve | None | `keep_active` | Generic diagnostic API. |
| `RegimeModule.diagnose_rule_mapped_stance_transitions()` | diagnostics / tracing | Public diagnostic method | Definition only as external API; calls `diagnose_rule_mapped_stance()` | Rule-mapped config indirectly | None | `diagnostic_duplication_candidate` | Could overlap generic rule-mapped diagnostics; needs Stage 2. |
| `RegimeModule.summarize_rule_mapped_stance_stability()` | diagnostics / tracing | Public summary method | Definition only as external API; calls `diagnose_rule_mapped_stance()` | Rule-mapped config indirectly | None | `diagnostic_duplication_candidate` | Public summary around generic diagnostics; needs Stage 2. |
| `RegimeModule.trace_stance_score()` | diagnostics / tracing | Public trace method | Called by `compare_credit_stance_persistence_cases()` | Stance function names in config | None | `keep_active` | Active trace API and diagnostic dependency. |
| `RegimeModule.compare_credit_input_smoothing_effect()` | diagnostics / tracing | Public diagnostic comparison | Definition only in scoped call scan | Credit diagnostics config indirectly | None | `diagnostic_duplication_candidate` | Specialized diagnostic with no scoped caller; may overlap generic comparison paths. |
| `RegimeModule.compare_curve_input_smoothing_effect()` | diagnostics / tracing | Public diagnostic comparison | Definition only in scoped call scan | Curve diagnostics config indirectly | None | `diagnostic_duplication_candidate` | Specialized diagnostic with no scoped caller; may overlap generic comparison paths. |
| `RegimeModule.compare_curve_move_driver_threshold_effect()` | diagnostics / tracing | Public diagnostic comparison | Definition only in scoped call scan | Curve move driver config and diagnostics indirectly | None | `diagnostic_duplication_candidate` | Specialized parameter-effect diagnostic. |
| `RegimeModule.compare_curve_positioning_stabilization_cases()` | diagnostics / tracing | Public diagnostic comparison | Definition only in scoped call scan | Curve state stabilization config | None | `diagnostic_duplication_candidate` | Specialized stabilization diagnostic. |
| `RegimeModule.compare_credit_stance_persistence_cases()` | diagnostics / tracing | Public diagnostic comparison | Definition only as external API; internally recalculates stance and calls `trace_stance_score()` | Credit state stabilization config | `temporary` in docstring at `module1.py:8714` | `diagnostic_duplication_candidate` | Specialized persistence diagnostic. |
| `RegimeModule.plot_historical_review_case()` | plotting / reporting | Public plotting method | Definition only in AST call scan; references `review_historical_cases()` in guidance | Historical context YAML indirectly | None | `needs_follow_up` | User-facing plotting API; no cleanup conclusion from restricted scan. |
| `RegimeModule.plot_target_comparison()` | plotting / reporting | Public plotting method | Definition only in scoped call scan; uses `build_target_comparison_dataset()` | Target config indirectly | None | `needs_follow_up` | User-facing plotting API; broad usage likely outside restricted scope. |

## Scoped caller/reference search notes

Search was intentionally limited to:

- `module1.py`
- `module1_schema.py`
- `data/module1_config.yaml`
- `data/historical_context.yaml`

Commands/methods used:

- `git ls-files '*.yaml' '*.yml'` to identify tracked YAML files in scope.
- Python AST parsing of `module1.py` to list class methods that do not start with `_`.
- Python AST call-site scan of `module1.py` to distinguish actual calls from docstrings and error messages.
- Scoped `rg` scans over the four scoped files for public method names, config function names, diagnostic/config keys, and compatibility keywords.

This audit did not search docs, reports, notebooks, tests, examples, README files, or untracked files.

## YAML/config reference scan

| file | key / section / reference | related method or function name | relevance | notes |
|---|---|---|---|---|
| `data/module1_config.yaml` | `model_metadata.target_groups` | `get_target_context()`, `build_target_comparison_dataset()`, `plot_target_comparison()` | actual runtime config reference | Target metadata supports context and plotting/comparison APIs. |
| `data/module1_config.yaml` | `model_metadata.diagnostics: {}` | diagnostic APIs generally | schema-related config reference | Empty diagnostics metadata; no public method names. |
| `data/module1_config.yaml` | component `score.function: weighted_feature_score` | `calculate_component_scores()` | actual runtime config reference | Runtime dispatch uses function names, not public method names. |
| `data/module1_config.yaml` | component `score.function: single_feature_score` | `calculate_component_scores()` | actual runtime config reference | Runtime dispatch uses internal scoring mechanics. |
| `data/module1_config.yaml` | component `score.function: curve_move_driver_score` | `calculate_component_scores()`, `compare_curve_move_driver_threshold_effect()` | actual runtime config reference | Runtime component function and related specialized diagnostic. |
| `data/module1_config.yaml` | component `diagnostics.prepared_inputs` | input smoothing diagnostics | actual runtime config reference | Supports prepared/filtered input diagnostic paths. |
| `data/module1_config.yaml` | `exposure_stances.duration.function: duration_rule_stance` | `calculate_exposure_stance()`, `trace_stance_score()` | actual runtime config reference | Active stance runtime dispatch. |
| `data/module1_config.yaml` | `exposure_stances.credit.function: credit_spread_stance` | `calculate_exposure_stance()`, `trace_stance_score()` | actual runtime config reference | Active stance runtime dispatch. |
| `data/module1_config.yaml` | `exposure_stances.usd.function: weighted_sum` | `calculate_exposure_stance()` | actual runtime config reference | Active weighted stance dispatch. |
| `data/module1_config.yaml` | `exposure_stances.curve_positioning.function: curve_positioning_stance` | `calculate_exposure_stance()`, `trace_stance_score()` | actual runtime config reference | Active stance runtime dispatch. |
| `data/module1_config.yaml` | `rule_mapped.function: rule_mapped_stance` | `diagnose_rule_mapped_stance()`, `trace_stance_score()`, rule-mapped runtime | actual runtime config reference | Present for duration, credit, and curve. |
| `data/module1_config.yaml` | `diagnostic_component: yield_move_driver` | rule-mapped diagnostics | actual runtime config reference | Diagnostic naming metadata, not a method reference. |
| `data/historical_context.yaml` | `events` and `expectations` | `load_historical_context()`, `review_historical_cases()` | actual runtime config reference | Historical review data source; no public method names. |

No scoped YAML file references public method names such as `compare_credit_input_smoothing_effect`, `plot_target_comparison`, or `run_module1_historical_review` directly.

## Compatibility / legacy keyword scan

| keyword | file / location | related method or area | relevance | notes |
|---|---|---|---|---|
| `temporary` | `module1.py:457` | `compare_horizon_cases()` | unrelated comment | Describes temporary `RegimeModule` instances during horizon-case diagnostics, not API compatibility. |
| `alias` | `module1.py:3788-3790`, `module1.py:3803-3805` | historical review target resolution | not a public cleanup clue | Internal target alias mapping supports canonical target lookup. |
| `wrapper` | `module1.py:4883` | `run_module1_historical_review()` | cleanup clue | Method is explicitly described as a convenience wrapper. |
| `legacy` | `module1.py:4899` | `run_module1_historical_review()` | cleanup clue | Docstring states it no longer returns the legacy `review_historical_context()` bundle. |
| `legacy` | `module1.py:6158` | `build_target_comparison_dataset()` | weak cleanup clue / mostly explanatory | Says compare-based path is independent of legacy plot modes; method is actively called by `plot_target_comparison()`. |
| `temporary` | `module1.py:8714` | `compare_credit_stance_persistence_cases()` | unrelated comment | Describes temporary persistence settings, not compatibility. |
| `backward` | `module1.py:9392`, `module1.py:9599` | plotting window handling | unrelated comment | Describes numeric window semantics extending backward from context start. |

No bounded keyword hits for `compatibility`, `deprecated`, `fallback`, `old`, `preserve`, `retained`, `TODO`, or `not implemented` were found in the scoped files.

## Candidate list

Likely keep:

- `to_target_info()`
- `load_core_files()`
- `validate_horizons()`
- `load_series_config()`
- `download_series()`
- `check_frequency_sanity()`
- `load_local_data()`
- `load_data()`
- `load_module1_config()`
- `calculate_features()`
- `align_component_scores()`
- `calculate_component_scores()`
- `calculate_component_labels()`
- `calculate_exposure_stance()`
- `run_module1_pipeline()`
- `load_historical_context()`
- `review_historical_cases()`
- `get_target_context()`
- `build_target_comparison_dataset()`
- `raw_inputs_for_target()`
- `diagnose_rule_mapped_stance()`
- `trace_stance_score()`

Cleanup candidates:

- `update_horizons()`
- `save_data()`
- `inspect_module1_results()`

Diagnostic duplication candidates:

- `diagnose_historical_review_case()`
- `diagnose_rule_mapped_stance_transitions()`
- `summarize_rule_mapped_stance_stability()`
- `compare_credit_input_smoothing_effect()`
- `compare_curve_input_smoothing_effect()`
- `compare_curve_move_driver_threshold_effect()`
- `compare_curve_positioning_stabilization_cases()`
- `compare_credit_stance_persistence_cases()`

Compatibility candidates:

- `run_module1_historical_review()`

Unclear / needs follow-up:

- `compare_horizon_cases()`
- `validate_historical_expected_labels()`
- `plot_historical_review_case()`
- `plot_target_comparison()`

Ignored:

- None. All inventoried non-underscore methods were public or public-looking enough to include in Stage 1.

## Recommended next action

Move the following methods to a Stage 2 broader audit that includes docs, reports, notebooks, tests, examples, README files, and any known external usage:

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
- `plot_historical_review_case()`
- `plot_target_comparison()`

Do not touch the following methods based on this restricted audit:

- core data/config/pipeline methods: `load_core_files()`, `load_data()`, `load_module1_config()`, `calculate_features()`, `calculate_component_scores()`, `calculate_component_labels()`, `calculate_exposure_stance()`, `run_module1_pipeline()`
- active context and generic diagnostic methods: `get_target_context()`, `build_target_comparison_dataset()`, `raw_inputs_for_target()`, `diagnose_rule_mapped_stance()`, `trace_stance_score()`
- active config/data helpers: `validate_horizons()`, `load_series_config()`, `download_series()`, `check_frequency_sanity()`, `load_local_data()`, `align_component_scores()`, `load_historical_context()`, `review_historical_cases()`, `to_target_info()`

Do not recommend deletion solely from this restricted-scope audit.

## Validation

This task is report-only.

Validation run:

- `git diff --check` - passed with no output.

No Python syntax check was required because no Python files were changed.

No production equality check was required because runtime behavior, schema behavior, YAML config, diagnostics behavior, public API behavior, and model outputs were not changed.
