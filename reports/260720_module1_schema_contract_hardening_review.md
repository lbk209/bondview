# Module 1 schema contract hardening review

## Scope

This task hardens `module1_schema.py` where the calculator has a narrow, established runtime contract. No other production file changed. In particular, `data/module1_config.yaml`, `module1_calculator.py`, and the diagnostic, sensitivity, plotting, and reporting modules remain unchanged.

The implementation extends the existing validation layers instead of adding a parallel schema path:

- Layer B now validates calculator support for component `score.sign` and `score.clip`, Credit-only rule-mapped adjustments, and per-stance rule-mapped output ownership.
- Layer C continues to own Credit adjustment model invariants through `validate_credit_rule_adjustment_config()`.
- Existing rule-mapped traversal and parsing results are reused for adjustment and collision checks.

## Newly enforced contracts

### Finite numeric values

One module-level predicate now defines an ordinary numeric configuration value as a finite `numbers.Real` that is not `bool`. This matches calculator operations that require real, finite values while retaining ordinary YAML integer and float support. Existing integer-only checks, including horizons and `min_state_persistence`, remain integer-only.

The finite requirement now covers anchors, component and stance thresholds, component and stance weights, bucket scores and bounds, input-preparation numeric values, Credit adjustment weights and caps, rule scores, and rule-mapped hysteresis buffers.

### Component score transforms

- `score.sign`, when supported, accepts only `direct` or `inverse`.
- `score.sign` is supported only by `single_feature_score` and fixed-anchor `weighted_feature_score`, matching the branches that consume it in the calculator.
- `score.sign` is rejected for ordinary weighted scores and curve-move driver scores because those calculator paths ignore it.
- A present `score.clip` must be a mapping containing only optional `min` and `max` keys. Supplied bounds must be finite, non-boolean numbers and must satisfy `min <= max`. An empty mapping remains a no-op.

### Rule-mapped adjustment capability

- An adjustment block is supported only for `credit_spread_stance`.
- A present Credit adjustment requires a mapping-valued `config`, which remains validated by `validate_credit_rule_adjustment_config()`.
- Credit adjustment requires exactly two state inputs, both classified as `threshold_state`.
- Declared adjustment `metadata_outputs` must have one entry per adjustment state input.
- The entire Credit adjustment block remains optional, consistent with the calculator's optional adjustment execution.

### Rule-mapped output ownership

Within each rule-mapped stance, source score columns must be unique, generated columns cannot overwrite source scores, and generated output roles cannot reuse a column name. The registry includes state raw/stabilized/change outputs, rule and aggregate outputs, optional base and adjustment outputs, and the stance's score/label/strength outputs.

Nested `score_output`, `stance_output`, and `strength_output` must still equal their active top-level stance fields. A present `adjusted_score_output` must equal `score_output`; that equality is treated as an intentional alias because the calculator does not write a separate adjusted-score column.

### Targeted unknown fields

Unknown-field rejection was added only for the task's narrow runtime contracts: `score.clip`, top-level `rule_mapped`, classification-aware state-input entries, `rule_mapped.adjustment`, Credit adjustment config, Credit cap blocks, and Credit state blocks.

## Exact malformed mutation coverage

Focused checks asserted the relevant `(section, name, field, issue)` identity for every mutation. The newly rejected cases were:

- `score.sign`: an unsupported value; a non-string value; a sign on an ordinary weighted score; a sign on a curve-move driver score.
- `score.clip`: a non-mapping value; an unknown key; a nonnumeric bound; `NaN`; infinity; reversed bounds.
- Non-finite numeric values: a fixed anchor; a component threshold; a component weight; a stance weight; a bucket bound; a bucket score; an input-preparation numeric value; a stance-label threshold; a rule score; a stabilization buffer; a Credit default cap; a Credit state cap; a Credit adjustment weight.
- Adjustment capability: omitted Credit `adjustment.config`; non-mapping Credit config; an adjustment on a non-Credit stance; fewer than two Credit state inputs; more than two Credit state inputs; a non-`threshold_state` Credit adjustment input; a metadata-output count that differs from the state-input count.
- Output ownership: duplicate source scores; a generated state output overwriting a source score; duplicate state outputs; a rule output colliding with an earlier output; an adjustment metadata output collision; an adjustment/score output collision; a generated stance-output collision; `adjusted_score_output` differing from `score_output`.
- Targeted unknown fields: top-level `rule_mapped`; a generic state-input field; a threshold-state-specific field; a bucket-classification-specific field; `rule_mapped.adjustment`; Credit adjustment config; a Credit default-cap block; a Credit state-cap block; a Credit adjustment state block.

In total, 47 focused malformed mutations passed identity assertions. Six focused valid forms also passed: supported fixed-anchor inverse sign, omitted single-feature sign, equal clip bounds, an empty clip mapping, an omitted Credit adjustment block, and omitted optional Credit metadata outputs.

## Validation results

- `python -m py_compile module1_schema.py module1_calculator.py`: passed.
- Canonical YAML schema validation: zero issues before and after.
- Strict calculator configuration loading: passed with zero issues.
- Existing characterization corpus: 24 cases remained byte-for-byte equivalent at the DataFrame level. Two cases changed intentionally: missing Credit adjustment config is now reported at `rule_mapped.adjustment.config` with `missing`, and an unsupported score sign is now reported at `score.sign` with `unsupported`.
- Deterministic offline output comparison: component scores `(7495, 10)`, component labels `(7495, 10)`, stance scores `(7495, 4)`, and exposure stance outputs `(7495, 12)` were exactly equal, including index, column order, values, dtypes, names, and missing values.
- Existing module-level shared helper signatures: all four remained unchanged. The authoritative finite-number predicate is new and does not alter an existing signature.
- `git diff --check`: passed.
- Canonical YAML SHA-256 before and after: `543164e2418b87907b8db0f7d289f11e50ca40c7ee473c05309c54c6af6e7309`.
- External/network data: not needed. The deterministic comparison used the existing offline fixtures/path with a dummy FRED key and made no network request.

Canonical validation output, valid calculator behavior, and model outputs did not change. Only acceptance and issue identity for the targeted malformed configurations changed.

## Intentionally unresolved candidates

- No blanket unknown-field policy was added for the document, feature, component, stance, label, or descriptive metadata layers.
- Internal/diagnostic output names are not required to be globally unique across different stance breakdowns.
- A Credit stance may still omit the entire adjustment block.
- No new calculator support was added for sign transforms that existing calculator branches ignore.
- No unrelated schema wording, ordering, compatibility field, or model invariant was changed.

All requested checks were completed; there are no unrun checks or external-data limitations to report.
