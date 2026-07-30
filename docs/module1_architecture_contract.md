# Module 1 Architecture Contract

## 1. Purpose

This document defines the architectural contract for Module 1 as conceptualized from the current `bondview` model.

The contract focuses on three primary layers:

1. `module1_config.yaml` as the model-definition layer;
2. Schema validation as the configuration-to-runtime contract boundary;
3. Calculator execution as a reusable, configuration-driven calculation engine.

The intended conceptual hierarchy is:

```text
raw input → feature → component → stance → Module1Result
```

The purpose of this contract is to ensure that:

- model structure is defined explicitly;
- reusable mechanics are implemented once;
- Curve, Credit, Duration, and later model areas use common execution capabilities wherever their behavior is structurally equivalent;
- configuration changes do not require hidden or duplicated Python changes;
- calculation stages remain understandable and testable;
- completed results form a stable boundary for downstream consumers.

This document is an architectural contract, not a complete implementation specification. Concrete class names and file boundaries may change as long as the responsibilities and invariants defined here are preserved.

---

## 2. Normative Terms

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** describe architectural requirements.

- **MUST / MUST NOT**: required for architectural compliance;
- **SHOULD / SHOULD NOT**: preferred unless a documented reason justifies an exception;
- **MAY**: optional and implementation-dependent.

---

## 3. Core Architectural Principles

### 3.1 Configuration defines model structure

`module1_config.yaml` MUST be the authoritative definition of configurable model structure.

Where configuration is intended to define the model, YAML SHOULD contain items such as:

- input references;
- feature definitions;
- component definitions;
- calculation operators;
- weights;
- transformations;
- normalization settings;
- smoothing settings;
- clipping settings;
- bucket definitions;
- classification methods;
- hysteresis and persistence settings;
- rule tables;
- labels;
- output names;
- relationships between components and stances.

Python MUST NOT duplicate configurable model structure merely for implementation convenience.

### 3.2 Python implements reusable mechanics

Python code MUST implement the reusable mechanics that interpret and execute the configuration.

Examples include:

- feature operators;
- input preparation;
- transformations;
- weighted aggregation;
- normalization;
- smoothing;
- clipping;
- bucket classification;
- state stabilization;
- rule lookup;
- label calculation;
- output construction.

Python MAY contain explicitly named special operators when the behavior cannot be represented clearly through existing generic capabilities. Such operators MUST be referenced explicitly from YAML and MUST NOT be selected through hidden stance-name checks.

### 3.3 Structure and execution are separate

The system MUST distinguish between:

- raw YAML structure;
- validated and resolved model specification;
- runtime data;
- calculated outputs.

The Calculator SHOULD NOT repeatedly interpret loosely structured YAML throughout the pipeline. Schema validation and specification resolution SHOULD convert accepted configuration into an explicit runtime form before calculation begins.

### 3.4 Equivalent behavior uses equivalent mechanics

When two model paths differ only by configuration values, they MUST use the same runtime capability.

For example:

- one-input and n-input weighted scoring SHOULD use the same weighted calculation mechanism;
- Curve, Credit, and Duration bucket classification SHOULD use the same classifier when their classification semantics are equivalent;
- hysteresis and persistence SHOULD be reusable stabilization blocks rather than stance-specific implementations.

### 3.5 Stance names do not determine execution

Runtime dispatch MUST be capability-driven rather than stance-name-driven.

The Calculator MUST NOT contain structures such as:

```python
if stance_name == "curve":
    ...
elif stance_name == "credit":
    ...
elif stance_name == "duration":
    ...
```

unless those stances genuinely require distinct named operators that are explicitly declared in configuration.

---

## 4. Responsibility Boundaries

### 4.1 YAML responsibility

YAML owns the model choices that a user should be able to change without editing Python.

Examples include:

- which inputs participate in a calculation;
- weights and signs;
- enabled or disabled optional blocks;
- smoothing method and horizon;
- normalization method and horizon;
- clipping bounds;
- bucket boundaries;
- default buckets;
- hysteresis buffer;
- minimum state persistence;
- rule-case scores;
- output and label vocabularies.

A change to one of these items SHOULD require only:

1. a YAML change;
2. schema validation;
3. normal calculation and regression validation.

It SHOULD NOT require reviewing Calculator source code unless the YAML change introduces a genuinely new capability.

### 4.2 Schema responsibility

Schema validation owns the contract between YAML and Calculator.

Schema MUST determine whether the declared model can be executed unambiguously by the Calculator.

Schema validation SHOULD cover three categories.

#### A. Generic configuration structure

Examples:

- required sections;
- mapping and list shapes;
- non-empty names;
- unique outputs;
- valid references;
- numeric and finite values;
- required fields;
- unknown fields in closed contracts.

#### B. Calculator capability contracts

Examples:

- supported operators;
- supported block combinations;
- required parameters for each operator;
- legal pipeline stages;
- supported classifier types;
- valid stabilization settings;
- output ownership;
- valid type and dimensional relationships.

#### C. Model-level invariants

Model-specific validation MAY exist where the model intentionally imposes a narrower contract than the generic engine.

Examples include:

- an expected set of rule states;
- a required cross-product of rule cases;
- semantic constraints on score ordering;
- component relationships required by a particular model definition.

Model-specific invariants MUST remain clearly distinguishable from generic Calculator capability validation.

### 4.3 Calculator responsibility

Calculator owns runtime execution of an already accepted model specification.

Calculator MUST:

- operate according to the resolved specification;
- preserve the declared pipeline order;
- use generic capabilities where behavior is structurally equivalent;
- produce internally coherent result tables;
- avoid silently repairing malformed configuration;
- avoid consulting unrelated consumer behavior;
- avoid hidden configuration defaults unless those defaults are part of the formal contract.

Calculator MAY provide named operators for specialized domain logic, but each operator MUST have an explicit input/output/configuration contract.

---

## 5. Configuration Resolution

The runtime SHOULD use a resolved model specification rather than repeatedly traversing raw YAML mappings.

Conceptually:

```text
raw YAML
    ↓
schema validation
    ↓
resolved specification
    ↓
Calculator execution
```

A resolved specification SHOULD:

- identify the selected operator explicitly;
- contain validated input references;
- preserve declared ordering;
- normalize optional settings into explicit values;
- separate input-level and score-level processing;
- resolve bucket and stabilization contracts;
- identify declared output columns;
- be immutable or treated as immutable during execution.

The resolved specification MAY use dataclasses, typed mappings, or another explicit structure. The important requirement is that runtime behavior not depend on repeated ad hoc interpretation of loosely structured dictionaries.

---

## 6. Canonical Calculation Pipeline

Generalization MUST NOT make execution order implicit.

The Calculator SHOULD use a fixed canonical pipeline whose stages are explicit. YAML selects and configures blocks within that pipeline; YAML does not initially define an unrestricted arbitrary sequence of operations.

A recommended canonical sequence is:

```text
1. Resolve source inputs
2. Prepare each input
3. Transform each input
4. Aggregate inputs
5. Post-process the aggregate score
6. Classify the score or input state
7. Stabilize the classified state
8. Apply rule or stance composition
9. Produce labels and outputs
10. Construct Module1Result
```

Not every calculation uses every stage. An unused stage MUST behave as an explicit no-op or be omitted through a clearly defined optional block.

### 6.1 Input resolution

Input resolution maps configured source names to runtime Series or equivalent values.

It MUST:

- preserve configured input order;
- fail clearly on missing required inputs;
- avoid implicit fallback to similarly named columns;
- avoid mutating caller-owned data.

### 6.2 Input preparation

Input preparation applies operations to individual source inputs before aggregation.

Examples:

- smoothing;
- filtering small absolute values;
- missing-value treatment where formally defined;
- alignment or frequency preparation.

Input preparation MUST be distinguished from score-level post-processing.

### 6.3 Input transformation

Input transformation changes the semantic representation of each prepared input.

Examples:

- normalization;
- fixed-anchor transformation;
- sign or direction transformation;
- bounded scaling.

The configuration and resolved specification MUST make clear whether a transformation applies:

- per input;
- after weighted aggregation;
- instead of another transformation;
- in a fixed relationship to another stage.

### 6.4 Aggregation

Aggregation combines one or more transformed inputs into a score.

The generalized weighted aggregation capability MUST support:

- one input with an explicit or resolved weight;
- multiple inputs with explicit weights;
- ordered input processing;
- deterministic missing-value semantics;
- input-level metadata sufficient for validation and traceability.

A one-input score SHOULD be represented as the one-input case of the same mechanism unless it requires genuinely different behavior.

### 6.5 Score-level post-processing

Post-processing applies to the aggregate score rather than individual inputs.

Examples:

- score smoothing;
- clipping;
- final scaling.

The stage order MUST be fixed and documented. For example, if score smoothing occurs before clipping, that order MUST be enforced consistently rather than inferred from YAML key order.

### 6.6 Classification

Classification converts a continuous score or a set of input states into a discrete raw bucket or state.

Supported classifier families MAY include:

- threshold state;
- range bucket;
- exact-score bucket;
- multi-input condition bucket;
- rule-table case construction.

Classifier behavior MUST be selected explicitly by capability, not inferred from a component or stance name.

### 6.7 Stabilization

Stabilization converts raw classified states into stabilized states.

Stabilization MUST be a reusable block independent of Curve, Credit, or Duration names.

Supported stabilization blocks MAY include:

- hysteresis;
- minimum state persistence;
- combined hysteresis and persistence;
- no-op stabilization.

YAML MUST be able to enable, disable, or configure supported stabilization blocks without requiring Python changes.

For example, adding or removing hysteresis from a Curve configuration SHOULD be a YAML-only model change when the generic hysteresis capability already exists.

### 6.8 Rule or stance composition

Stance composition combines component scores or classified states.

Supported forms MAY include:

- weighted score composition;
- rule-table lookup;
- rule-table lookup with a formally defined adjustment block.

Rule lookup MUST preserve configured state-input order. Rule-case construction and rule-score lookup MUST use the same resolved state vocabulary validated by Schema.

### 6.9 Labels and output construction

Labels and strengths MUST be derived from declared output rules.

Output construction MUST:

- use configuration-declared output names;
- prevent output collisions;
- preserve deterministic column ordering;
- keep raw states and stabilized states distinguishable where both are produced;
- retain enough metadata to explain which model specification produced the result.

---

## 7. Block Architecture

The Calculator SHOULD be composed of blocks with explicit contracts rather than one function containing every possible behavior.

A block contract SHOULD identify:

1. accepted runtime input type;
2. returned output type;
3. configuration fields consumed;
4. whether the block is row-local or history-dependent;
5. missing-value semantics;
6. mutation guarantees;
7. validation requirements.

Conceptual interfaces may resemble:

```python
prepare_input(series, spec, context) -> Series
transform_input(series, spec, context) -> Series
aggregate_inputs(inputs, spec, context) -> Series
postprocess_score(score, spec, context) -> Series
classify_score(score, spec, context) -> Series
stabilize_state(raw_state, score, spec, context) -> Series
compose_stance(inputs, spec, context) -> DataFrame
```

These exact function names are not required.

### 7.1 Row-local and history-dependent blocks

The architecture MUST distinguish row-local operations from history-dependent operations.

Typically row-local:

- weighting;
- sign transformation;
- clipping;
- ordinary bucket lookup;
- rule-table lookup.

Typically history-dependent:

- rolling smoothing;
- rolling normalization;
- hysteresis;
- minimum persistence.

History-dependent blocks MUST receive sufficient ordered time-series context and MUST define behavior at missing observations and initial periods.

### 7.2 No-op blocks

Optional stages SHOULD have explicit no-op behavior.

Examples:

- no smoothing;
- no clipping;
- no stabilization.

A no-op block MAY be represented by absence, `null`, or an explicit `none` operator, but the interpretation MUST be unambiguous and validated.

---

## 8. Generalized Weighted Score Contract

The generalized weighted score capability is the standard mechanism for combining one or more numerical inputs.

It MUST support:

- one or more declared inputs;
- explicit input ordering;
- validated numeric weights;
- input-level preparation;
- input-level transformation;
- weighted aggregation;
- score-level post-processing;
- deterministic output naming.

The architecture MUST NOT create separate ordinary one-feature and weighted-feature execution paths when they differ only in input count.

Special transformations such as fixed-anchor scoring MAY be supported as input-transform blocks or a clearly defined scoring operator. Their stage relationship to normalization, sign, smoothing, and clipping MUST be explicit.

---

## 9. Generalized Bucket Score Contract

A generalized bucket-score capability is a composition of reusable stages, not one monolithic function.

Conceptually:

```text
ScorePipeline
    ↓
BucketClassifier
    ↓
optional StateStabilizer
    ↓
Bucket/State Outputs
```

The high-level capability MAY offer a convenient unified configuration surface, but the internal contracts MUST remain separable.

### 9.1 Continuous score and discrete state remain distinct

The architecture MUST distinguish:

- a continuous numerical score;
- a raw classified bucket/state;
- a stabilized bucket/state.

These values MUST NOT be conflated merely because some current configurations assign a representative numeric score to each bucket.

### 9.2 YAML-controlled optional behavior

YAML SHOULD be able to control supported behavior such as:

- whether inputs are smoothed;
- whether a score is normalized;
- bucket boundaries;
- default bucket;
- whether hysteresis is enabled;
- whether persistence is enabled;
- stabilization parameters.

Once a capability exists, enabling or disabling it for Curve, Credit, Duration, or another model area SHOULD not require stance-specific Python modifications.

### 9.3 Multi-input conditions

Some bucket classifications depend on multiple inputs rather than one score.

The architecture MAY support a bounded declarative condition form such as:

```yaml
classification:
  method: condition_bucket
  inputs:
    front_end: dgs2_change
    long_end: dgs10_change
  buckets:
    bull_parallel:
      conditions:
        front_end: negative
        long_end: negative
    bear_parallel:
      conditions:
        front_end: positive
        long_end: positive
    mixed_or_unclear:
      default: true
```

The supported condition vocabulary MUST be bounded and schema-validated. YAML SHOULD NOT become a general-purpose expression language.

---

## 10. YAML Design Rules

YAML SHOULD be declarative, bounded, and readable.

It SHOULD describe:

- what the model is;
- which reusable operators are selected;
- how those operators are configured;
- what outputs are produced.

It SHOULD NOT contain:

- unrestricted executable expressions;
- arbitrary Python references;
- hidden ordering based on mapping implementation details;
- duplicated declarations of the same authoritative relationship;
- presentation-only configuration unrelated to model execution.

Ordering that affects calculation MUST be represented through ordered lists or another explicit contract.

YAML aliases MAY reduce duplication, but semantic correctness MUST NOT rely on object identity after parsing.

---

## 11. Schema and Calculator Synchronization

Schema and Calculator MUST share one capability contract.

The following failure mode is prohibited:

```text
YAML accepts a form
→ Schema validates it
→ Calculator ignores or interprets it differently
```

The reverse is also prohibited:

```text
Calculator supports a form
→ Schema rejects it because of an unrelated name whitelist
```

Capability names, required fields, classifier families, and stabilization options SHOULD be defined in one authoritative location or exposed through a narrow shared contract.

Schema MAY apply stricter model-specific invariants after generic capability validation.

---

## 12. Calculator Execution Contract

Calculator execution MUST be deterministic for identical:

- input data;
- resolved configuration;
- horizon values;
- execution options.

Calculator MUST NOT:

- mutate caller-owned configuration;
- mutate caller-owned input tables;
- depend on downstream consumer state;
- consult current external configuration while evaluating an already resolved specification;
- silently skip unsupported configuration fields;
- produce partially coherent result tables.

Calculator SHOULD separate:

- environment and file acquisition;
- configuration loading and resolution;
- pure in-memory model execution.

This separation permits repeated scenario calculation without forcing unrelated I/O or environment initialization.

---

## 13. Module1Result Contract

`Module1Result` is the completed calculation boundary.

It SHOULD contain a coherent snapshot of the outputs and model information needed to interpret the calculation.

A complete result MAY include:

- source data used by the calculation;
- calculated features;
- component scores;
- component labels;
- stance scores;
- final stance labels and strengths;
- the exact resolved or accepted configuration snapshot;
- horizons and other calculation metadata;
- validation or specification metadata where useful.

All included tables MUST describe the same calculation scenario.

A result MUST NOT combine:

- modified component scores;
- baseline labels;
- baseline stance outputs;
- unrelated configuration metadata.

Downstream consumers SHOULD operate from `Module1Result` or a deliberately derived narrower result contract. They SHOULD NOT reconstruct hidden Calculator state or reload current YAML to reinterpret an existing result.

Scenario workflows SHOULD request separate complete results for separate scenarios and compare those results rather than manually replacing isolated intermediate columns.

---

## 14. Extension Contract

Adding a new component or stance SHOULD follow this decision order:

1. Can the requirement be expressed by existing YAML fields and existing blocks?
2. Does it require a new reusable block or operator?
3. Does it require a genuine model-specific invariant?
4. Only as a last resort, does it require a named special-case execution path?

A new reusable capability MUST define:

- configuration grammar;
- schema validation;
- resolved specification representation;
- runtime interface;
- output contract;
- missing-value behavior;
- tests.

Adding a new Curve, Credit, or Duration configuration SHOULD NOT automatically imply adding a new Calculator branch.

---

## 15. Development and Validation Strategy

The architecture SHOULD be built through narrow end-to-end slices rather than implementing every block before any calculation runs.

A recommended first slice is:

```text
one feature
→ generalized weighted score
→ simple range classification
→ one stance output
→ Module1Result
```

Later blocks can be added individually:

1. input smoothing;
2. normalization;
3. fixed-anchor transformation;
4. score smoothing;
5. clipping;
6. generalized range buckets;
7. multi-input condition buckets;
8. hysteresis;
9. persistence;
10. rule-table composition;
11. labels and strengths.

Each block SHOULD be independently testable.

### 15.1 Required validation categories

Validation SHOULD cover:

- canonical valid configuration;
- malformed configuration;
- unsupported block combinations;
- one-input and multi-input weighted calculations;
- block ordering;
- no-op behavior;
- missing-value behavior;
- history-dependent initial periods;
- hysteresis transitions;
- persistence transitions;
- deterministic output order;
- caller-input and configuration immutability;
- complete result coherence.

### 15.2 Generality test

Generality is proven by configuration reuse, not by generic names.

After implementing multiple model areas, the repository SHOULD verify that Curve, Credit, and Duration can use shared capabilities without hidden stance-name dispatch.

---

## 16. Prohibited Design Patterns

The following patterns violate this contract unless explicitly justified and documented:

- duplicating YAML model structure in Calculator constants;
- changing Calculator code for a supported parameter-only YAML change;
- stance-name whitelists used as capability dispatch;
- one-feature and n-feature scoring paths with duplicated mechanics;
- stance-specific smoothing, hysteresis, or persistence implementations when generic blocks apply;
- schema rules that validate names rather than executable capabilities without a model-invariant reason;
- Calculator fallback behavior that hides invalid configuration;
- partial scenario reconstruction that creates internally inconsistent result objects;
- downstream consumers constructing incomplete Calculator shells;
- configuration fields accepted by Schema but ignored by Calculator;
- unrestricted YAML expression languages;
- excessive thin wrappers that do not establish a real ownership boundary.

---

## 17. Architectural Acceptance Criteria

The architecture is compliant when all of the following are true:

1. YAML is the authoritative model-definition layer for configurable structure.
2. Schema rejects declarations the Calculator cannot execute unambiguously.
3. Calculator executes a resolved specification through explicit ordered stages.
4. One-input and multi-input weighted calculations share one generalized mechanism.
5. Bucket classification and stabilization are reusable blocks.
6. Supported hysteresis and persistence can be enabled or disabled through YAML.
7. Curve, Credit, and Duration do not require separate execution branches when they use equivalent mechanics.
8. New capabilities are added through explicit operator contracts rather than hidden special cases.
9. Calculator produces coherent complete `Module1Result` objects.
10. Scenario calculations produce separate complete results rather than manually combining inconsistent intermediate outputs.
11. Configuration-only model changes do not require Calculator source changes when the required capability already exists.
12. Generic capability validation and model-specific invariants remain distinguishable.

---

## 18. Summary

The central architecture is:

```text
YAML defines the model
        ↓
Schema validates and resolves the model
        ↓
Calculator executes reusable ordered blocks
        ↓
Module1Result records one coherent completed calculation
```

The design goal is not abstraction for its own sake. The goal is to make model variation primarily configuration-driven, keep execution mechanics reusable, preserve explicit stage semantics, and prevent Curve, Credit, Duration, or later model areas from developing separate accidental architectures.
