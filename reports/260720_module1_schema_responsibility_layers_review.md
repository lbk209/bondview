# Module 1 schema responsibility layers review

## Scope

This task reorganized the active validation inside `validate_module1_config()` without changing the public validation contract, accepted canonical configuration, calculator behavior, or model outputs.

Production changes were limited to `module1_schema.py`. No YAML, calculator, diagnostics, sensitivity, plotting, or reporting production code changed.

## Responsibility mapping

### Layer A — generic YAML structure

The following substantial validators now localize generic declaration and relationship checks:

- `validate_top_level_structure()` owns required sections, metadata group structure and references, and horizon declarations.
- `validate_features_section()` owns feature mapping traversal and generic feature declaration shape while dispatching supported calculator feature methods.
- `validate_components_section()` owns the single ordered component traversal, generic component mapping checks, output registration, cross-references, and label relationships.
- `validate_stance_label_rules_section()` owns stance-label rule mapping and threshold structure.
- `validate_rule_mapped_rule_scores()` owns rule-key parsing and declared state cross-product coverage.
- `validate_exposure_stances_section()` owns the single ordered stance traversal, generic inputs, outputs, labels, and cross-references.
- `validate_rule_mapped_stance_schema()` retains generic ordered state-input and stabilization validation as the rule-mapped orchestration boundary.

### Layer B — calculator capability contract

Calculator-executable forms are visibly identified within the section validators and capability helpers:

- Supported feature methods and frequencies remain in `validate_features_section()`.
- `validate_anchor_block()` owns fixed-anchor shape validation.
- `validate_threshold_label_mode()` and `validate_bucket_label_mode()` own the two calculator-supported component label forms.
- `validate_component_diagnostics()` owns supported prepared-input diagnostic declarations.
- `validate_components_section()` keeps supported score functions, input preparation, normalization, smoothing, score-function input forms, and label-mode dispatch in the existing issue order.
- `validate_rule_mapped_adjustment_contract()` owns supported adjustment metadata and output structure before dispatching Credit-specific config validation.
- `validate_rule_mapped_stance_schema()` owns custom-stance `rule_mapped` requirements, supported classifications, calculator output bindings, and stabilization resolution.
- `validate_exposure_stances_section()` owns supported stance dispatch and weighted-input requirements.

### Layer C — Module 1 model invariants

Existing named-model rules are isolated without adding new invariants:

- `validate_credit_rule_adjustment_config()` and `validate_credit_cap_block()` retain the active Credit adjustment state, weight, and cap requirements.
- `validate_curve_change_model_invariants()` owns the active curve-change buckets.
- `validate_curve_state_model_invariants()` owns the active curve-state buckets.
- `validate_curve_move_driver_model_invariants()` owns move-driver categories and exact scores used by calculator logic.
- The named current-state component restrictions remain visibly marked inside the ordered component validator.
- Rule-mapped bucket declarations continue to be checked against active component bucket models.

No Duration-specific invariant was introduced.

## Characterization baseline and validation

A baseline was captured before editing from the current session branch. It stored the exact `report`, `issues`, and `full` DataFrames for 26 fixed configurations and the deterministic offline pipeline outputs.

Characterization cases covered:

- canonical configuration;
- missing and invalid top-level sections;
- unknown horizon and feature references;
- unsupported score functions;
- missing score output and malformed threshold/bucket label structures;
- missing weighted-stance weights and unknown weighted inputs;
- missing rule-mapped state outputs and unsupported classifications;
- invalid rule-mapped stabilization;
- malformed rule keys and missing cross-product cases;
- invalid Credit adjustment cap ordering and missing adjustment weights;
- Credit, Duration, and Curve custom stances without `rule_mapped`;
- accepted deferred gaps for omitted Credit adjustment config, unknown top-level fields, and unchecked `score.sign` values.

After the refactor, every returned DataFrame matched its baseline exactly, including type, columns and order, index, values, dtypes, names, issue identities, issue ordering, checked-record identities, and checked-record ordering.

Commands and checks included:

- `python -m py_compile module1_schema.py module1_calculator.py`
- repository search identifying `module1_calculator.py` as the only direct schema-helper importer;
- canonical YAML validation;
- strict `Module1Calculator` configuration loading with local repository data;
- exact 26-case validation DataFrame comparison using `pandas.testing.assert_frame_equal`;
- AST comparison of all module-level schema helper signatures before and after;
- exact offline pipeline DataFrame comparison for component scores, component labels, stance scores, and exposure stance outputs;
- `git diff --check`;
- SHA-256 comparison for `data/module1_config.yaml`.

Results:

- canonical YAML issues: `0`;
- strict calculator loading: passed with `0` issues;
- exact validation characterization cases: `26/26` passed;
- module-level helper signatures: unchanged;
- component scores: identical, shape `(7495, 10)`;
- component labels: identical, shape `(7495, 10)`;
- stance scores: identical, shape `(7495, 4)`;
- exposure stance outputs: identical, shape `(7495, 12)`;
- YAML SHA-256: `543164e2418b87907b8db0f7d289f11e50ca40c7ee473c05309c54c6af6e7309`, unchanged.

The offline constructor requires a `FRED_API_KEY` value even when reading the repository CSV fixture. Checks used a non-secret dummy value and made no network calls.

## Behavior impact and deferred gaps

Validation output did not change. Calculator behavior and model outputs did not change. Declaration and output ordering did not change. YAML did not change.

The following known gaps were intentionally left unchanged for later validation hardening:

- omitted Credit `rule_mapped.adjustment.config` remains accepted by schema validation;
- `score.sign` and `score.clip` were not hardened;
- non-finite numeric values were not newly rejected;
- currently accepted output-name collisions were not changed;
- unknown fields currently accepted remain accepted.
