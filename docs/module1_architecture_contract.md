# Module 1 Architecture Contract

## 1. Purpose

This document defines the architectural contract for Module 1 as conceptualized from the current `bondview` model.

The contract focuses on three primary layers:

1. `module1_config.yaml` as the model-definition layer;
2. Schema validation as the configuration-to-runtime contract boundary;
3. Calculator execution as a reusable, configuration-driven calculation engine.

The intended conceptual hierarchy is:

```text
raw input
    ↓
shared feature calculation
    ├── macro features
    └── bond-market features
    ↓
component calculation
    ↓
duration / curve / credit stance calculation
    ↓
Module1Result
```

The purpose of this contract is to ensure that:

- model structure is defined explicitly;
- reusable mechanics are implemented once;
- Curve, Credit, and Duration use common execution capabilities wherever their behavior is structurally equivalent;
- shared macro conditions are calculated once and interpreted separately by each stance;
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
- relationships between features, components, and stances;
- shared macro-feature definitions and stance-specific use of those features.

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

### 3.6 Raw-data reuse is permitted

A raw series is not exclusively owned by one feature group or calculation path.

The same aligned source observation MAY be used by:

- shared macro-feature calculations;
- bond-market feature calculations;
- more than one component where each use has a distinct declared meaning.

For example, the policy rate MAY contribute to both a policy-restrictiveness feature and a Treasury-policy spread feature. This is not duplication by itself.

The prohibited duplication is competing ownership of the same derived meaning. Two calculations MUST NOT independently claim to produce the authoritative policy-restrictiveness state, inflation trend, or another equivalent derived concept unless their distinction is explicit in the model contract.

Shared raw inputs SHOULD come from one scenario-consistent data snapshot so that observation dates, revisions, frequency alignment, and preparation choices remain coherent.

### 3.7 Macro interpretation is internal to Module 1 unless independently justified

Growth, inflation, policy, real-rate, and related macro conditions SHOULD initially be represented as shared Module 1 features or an internal model-ready context.

A separate public `MacroResult` contract SHOULD NOT be introduced solely because multiple Module 1 stances use macro information. It becomes justified only if it has a stable standalone meaning and genuine consumers outside Module 1.

Module 1 owns the translation from shared macro conditions into bond-exposure implications:

- Duration interprets them for interest-rate exposure;
- Curve interprets them for maturity-segment and curve-shape positioning;
- Credit interprets them for spread and default-risk exposure.

The same macro condition MAY have different or opposite effects across those stances. The architecture therefore SHOULD NOT require one universal macro score.

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

Calculator SHOULD calculate shared macro features once per scenario and reuse the resulting values across Duration, Curve, and Credit. A stance calculator SHOULD NOT independently reconstruct a shared macro feature when an authoritative feature already exists.

### 4.4 Shared macro-feature responsibility

The shared macro-feature layer owns model-ready descriptions of broad economic conditions, not final bond-exposure decisions.

Examples MAY include:

- growth momentum or state;
- inflation level, direction, or pressure;
- realized policy direction;
- policy restrictiveness;
- real-rate condition;
- liquidity or fiscal conditions when later included in the model.

These features SHOULD be produced through existing generic feature and scoring capabilities wherever possible.

Examples include:

- `change`, `pct_change`, `spread`, or `difference` feature operators;
- one-input or multi-input weighted scoring;
- normalization, smoothing, clipping, thresholds, and buckets.

A new operator MAY be introduced for a genuinely new relationship, such as a formally defined real-rate or policy-restrictiveness calculation. The operator MUST remain reusable and MUST NOT create a parallel macro-specific scoring framework.

### 4.5 Stance responsibility for macro features

Duration, Curve, and Credit own the stance-specific interpretation of shared macro features.

They MUST NOT assume that a shared feature has one universal directional meaning. For example, weakening growth may support longer Duration while reducing Credit attractiveness.

Each stance SHOULD consume only the macro features relevant to its declared model. Stance composition MAY use:

- weighted score composition;
- bucket or state classification;
- rule-table composition;
- a configured gate or override for exceptional states.

The selected mechanism MUST be explicit in configuration and MUST use the same reusable Calculator capabilities available to non-macro features.


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
2. Calculate derived features
3. Prepare each feature or direct input
4. Transform each feature or input
5. Aggregate inputs into component scores
6. Post-process the aggregate score
7. Classify the score or input state
8. Stabilize the classified state
9. Apply rule or stance composition
10. Produce labels and outputs
11. Construct Module1Result
```

Not every calculation uses every stage. An unused stage MUST behave as an explicit no-op or be omitted through a clearly defined optional block.

### 6.1 Input resolution

Input resolution maps configured source names to runtime Series or equivalent values.

It MUST:

- preserve configured input order;
- fail clearly on missing required inputs;
- avoid implicit fallback to similarly named columns;
- avoid mutating caller-owned data;
- preserve one scenario-consistent view of observation dates and aligned values.

The same resolved raw input MAY feed multiple declared feature calculations. Input resolution MUST NOT impose exclusive ownership of a raw series by a particular component or feature group.

### 6.2 Derived-feature calculation

Derived-feature calculation converts resolved raw observations into model-ready features.

Derived features MAY include both:

- macro features, such as growth momentum, inflation pressure, policy direction, policy restrictiveness, and real-rate condition;
- bond-market features, such as yield changes, curve spreads, credit-spread changes, and Treasury-policy gaps.

Feature operators SHOULD be reusable and bounded. Supported operators MAY include:

- level;
- change;
- percentage change;
- spread or difference;
- rolling trend;
- bounded domain-specific operators with explicit contracts.

A feature MUST have one authoritative declared definition. Historical review, stance calculation, and other consumers MUST reuse that definition rather than reimplementing equivalent feature logic.

### 6.3 Input or feature preparation

Preparation applies operations to individual source inputs or calculated features before aggregation.

Examples:

- smoothing;
- filtering small absolute values;
- missing-value treatment where formally defined;
- alignment or frequency preparation.

Preparation MUST be distinguished from score-level post-processing.

### 6.4 Input transformation

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

### 6.5 Aggregation

Aggregation combines one or more transformed inputs into a component score.

The generalized weighted aggregation capability MUST support:

- one input with an explicit or resolved weight;
- multiple inputs with explicit weights;
- ordered input processing;
- deterministic missing-value semantics;
- input-level metadata sufficient for validation and traceability.

A one-input score SHOULD be represented as the one-input case of the same mechanism unless it requires genuinely different behavior.

A composite macro feature such as growth momentum or inflation pressure MAY use this mechanism when its inputs measure the same underlying concept. The architecture SHOULD NOT introduce a separate macro aggregation engine for that case.

### 6.6 Score-level post-processing

Post-processing applies to the aggregate score rather than individual inputs.

Examples:

- score smoothing;
- clipping;
- final scaling.

The stage order MUST be fixed and documented. For example, if score smoothing occurs before clipping, that order MUST be enforced consistently rather than inferred from YAML key order.

### 6.7 Classification

Classification converts a continuous score or a set of input states into a discrete raw bucket or state.

Supported classifier families MAY include:

- threshold state;
- range bucket;
- exact-score bucket;
- multi-input condition bucket;
- rule-table case construction.

Classifier behavior MUST be selected explicitly by capability, not inferred from a component or stance name.

Shared macro features MAY expose both continuous scores and classified states where both are useful. Those values MUST remain distinct.

### 6.8 Stabilization

Stabilization converts raw classified states into stabilized states.

Stabilization MUST be a reusable block independent of Curve, Credit, Duration, or macro-feature names.

Supported stabilization blocks MAY include:

- hysteresis;
- minimum state persistence;
- combined hysteresis and persistence;
- no-op stabilization.

YAML MUST be able to enable, disable, or configure supported stabilization blocks without requiring Python changes.

For example, adding or removing hysteresis from a Curve or inflation-state configuration SHOULD be a YAML-only model change when the generic hysteresis capability already exists.

### 6.9 Rule or stance composition

Stance composition combines component scores or classified states.

Supported forms MAY include:

- weighted score composition;
- rule-table lookup;
- rule-table lookup with a formally defined adjustment block;
- weighted composition with an explicitly configured gate or override.

Rule lookup MUST preserve configured state-input order. Rule-case construction and rule-score lookup MUST use the same resolved state vocabulary validated by Schema.

The model MAY select different composition forms for Duration, Curve, and Credit. That difference MUST arise from the declared model structure, not from hidden stance-name branching.

### 6.10 Labels and output construction

Labels and strengths MUST be derived from declared output rules.

Output construction MUST:

- use configuration-declared output names;
- prevent output collisions;
- preserve deterministic column ordering;
- keep raw states and stabilized states distinguishable where both are produced;
- keep shared macro features distinguishable from stance-specific interpretations;
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

## 10. Shared Macro Feature Contract

Shared macro-feature calculation is an internal production capability of Module 1. It is upstream of stance composition and is not conceptually equivalent to historical context or another downstream consumer.

Conceptually:

```text
raw economic observations
        ↓
shared macro features
        ├── growth
        ├── inflation
        ├── policy
        └── real-rate or related conditions
        ↓
stance-specific interpretation
        ├── Duration
        ├── Curve
        └── Credit
        ↓
Module1Result
```

### 10.1 One calculation, multiple stance uses

Shared macro features SHOULD be calculated once for a complete Module 1 scenario and reused by each stance.

A stance MAY use only a subset of the available features. The Calculator MUST NOT require every stance to consume every macro feature.

The shared layer describes the economic condition. It does not assign one universal bond implication.

For example:

```text
growth weakening
    → may support longer Duration
    → may imply a Curve transition associated with future easing
    → may reduce Credit attractiveness
```

### 10.2 Generic mechanics remain authoritative

Macro features SHOULD use the same feature, score, classification, and stabilization capabilities as other Module 1 features.

Typical forms include:

- single-feature scoring for realized policy direction;
- weighted feature scoring for composite growth or inflation measures;
- a derived difference or spread for real-rate or policy-restrictiveness measures;
- threshold or bucket classification for feature states.

A separate macro-specific weighted-sum engine, bucket engine, smoothing path, normalization path, or stabilization path MUST NOT be created when the existing generic capability can express the required behavior.

### 10.3 Stance composition choices

The contract does not require one composition operator for all stances.

A likely model structure MAY use:

- rule-mapped composition for Duration where growth, inflation, policy, rate shocks, and market confirmation interact;
- rule-mapped composition for Curve where macro state, current curve shape, curve change, and yield-move driver interact;
- rule-mapped composition for Credit where spread-change and spread-state combinations have distinct meanings, optionally followed by a formally configured post-lookup adjustment. Relevant macro conditions MAY be represented as additional rule states or through a separate declared adjustment or gate when the model explicitly requires them.

These are model-design choices rather than hard-coded Calculator behavior. YAML and Schema MUST declare and validate whichever supported operator and optional adjustment blocks are selected.

### 10.4 Public-result boundary

The initial architecture SHOULD NOT require an independently consumable `MacroResult`.

An internal typed structure such as `MacroContext` MAY be used to pass shared feature values during calculation. It MAY also be retained inside `Module1Result` for explanation, reproducibility, and comparison.

Downstream consumers SHOULD continue to use `Module1Result` as the formal boundary. They SHOULD NOT be required to separately reconstruct or consume the internal macro context unless a future interface explicitly establishes that need.

### 10.5 Consumer reuse

Shared macro-feature and stance definitions remain production-owned even when another consumer evaluates prior dates, alternative scenarios, or explanatory views.

Such consumers MUST use completed `Module1Result` objects or the same authoritative Calculator capabilities. They MUST NOT maintain parallel implementations of growth, inflation, policy, real-rate, or stance logic.

---

## 11. YAML Design Rules

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

## 12. Schema and Calculator Synchronization

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

## 13. Calculator Execution Contract

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

## 14. Module1Result Contract

`Module1Result` is the completed calculation boundary.

It SHOULD contain a coherent snapshot of the outputs and model information needed to interpret the calculation.

A complete result MAY include:

- source data used by the calculation;
- calculated macro and bond-market features;
- an internal macro context or equivalent explanatory structure;
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

Downstream consumers SHOULD operate from `Module1Result` or a deliberately derived narrower result contract. They SHOULD NOT reconstruct hidden Calculator state, recalculate shared macro features, or reload current YAML to reinterpret an existing result.

Macro features retained in the result are explanatory and reproducibility data unless a downstream interface explicitly declares otherwise. The formal investment-facing outputs remain the Duration, Curve, and Credit results and any other declared Module 1 stances.

Scenario workflows SHOULD request separate complete results for separate scenarios and compare those results rather than manually replacing isolated intermediate columns.

---

## 15. Downstream Consumer Reference

The macro-feature extension primarily changes Module 1. Other modules SHOULD retain their existing role as consumers of a completed `Module1Result`.

ETF review or selection SHOULD preserve the joint meaning of the separate Duration, Curve, and Credit outputs. It SHOULD NOT collapse them into one overall bond score unless a future model explicitly defines and validates that aggregation.

For example:

```text
Duration: favorable
Curve: prefer intermediate maturities
Credit: unfavorable
```

A downstream selector may interpret this combination as support for an intermediate-maturity government-bond ETF while rejecting:

- an ultra-long government-bond ETF because its Duration exposure is excessive;
- an intermediate corporate-bond ETF because its Credit exposure conflicts with the result;
- a short-duration high-yield ETF because both its Duration and Credit characteristics conflict.

This is a downstream interpretation requirement, not a reason for the downstream module to recalculate growth, inflation, policy, real-rate, Curve, Credit, or Duration logic.

---

## 16. Extension Contract

Adding a new feature, component, or stance SHOULD follow this decision order:

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

Adding a new macro feature, Curve, Credit, or Duration configuration SHOULD NOT automatically imply adding a new Calculator branch.

---

## 17. Development and Validation Strategy

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

1. reusable derived-feature operators;
2. shared macro-feature calculation;
3. input smoothing;
4. normalization;
5. fixed-anchor transformation;
6. score smoothing;
7. clipping;
8. generalized range buckets;
9. multi-input condition buckets;
10. hysteresis;
11. persistence;
12. rule-table composition;
13. labels and strengths.

Each block SHOULD be independently testable.

### 17.1 Required validation categories

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
- one authoritative calculation of each shared macro feature;
- stance-specific use of macro features without duplicated feature logic;
- consumer reuse of production feature definitions;
- complete result coherence.

### 17.2 Generality test

Generality is proven by configuration reuse, not by generic names.

After implementing multiple model areas, the repository SHOULD verify that Curve, Credit, and Duration can use shared capabilities without hidden stance-name dispatch.

---

## 18. Prohibited Design Patterns

The following patterns violate this contract unless explicitly justified and documented:

- duplicating YAML model structure in Calculator constants;
- changing Calculator code for a supported parameter-only YAML change;
- stance-name whitelists used as capability dispatch;
- one-feature and n-feature scoring paths with duplicated mechanics;
- stance-specific smoothing, hysteresis, or persistence implementations when generic blocks apply;
- a parallel macro-specific score, bucket, normalization, smoothing, or stabilization engine when generic blocks apply;
- Duration, Curve, and Credit independently recalculating the same authoritative macro feature;
- consumer-specific code reimplementing production macro-feature or stance logic;
- treating a raw data series as exclusively owned by one feature group when another declared calculation legitimately requires it;
- schema rules that validate names rather than executable capabilities without a model-invariant reason;
- Calculator fallback behavior that hides invalid configuration;
- partial scenario reconstruction that creates internally inconsistent result objects;
- downstream consumers constructing incomplete Calculator shells;
- configuration fields accepted by Schema but ignored by Calculator;
- unrestricted YAML expression languages;
- downstream reduction of Duration, Curve, and Credit into one overall score without an explicit validated model contract;
- excessive thin wrappers that do not establish a real ownership boundary.

---

## 19. Architectural Acceptance Criteria

The architecture is compliant when all of the following are true:

1. YAML is the authoritative model-definition layer for configurable structure.
2. Schema rejects declarations the Calculator cannot execute unambiguously.
3. Calculator executes a resolved specification through explicit ordered stages.
4. Raw inputs may be reused by multiple declared feature calculations without creating competing derived meanings.
5. Shared macro features are calculated once per scenario and reused by Duration, Curve, and Credit.
6. Macro features and bond-market features use the same generic mechanics when their execution semantics are equivalent.
7. One-input and multi-input weighted calculations share one generalized mechanism.
8. Bucket classification and stabilization are reusable blocks.
9. Supported hysteresis and persistence can be enabled or disabled through YAML.
10. Duration, Curve, and Credit do not require separate execution branches when they use equivalent mechanics.
11. Their different macro interpretations are expressed through declared stance configuration rather than duplicated feature calculations.
12. Other consumers reuse the authoritative production feature and stance definitions.
13. New capabilities are added through explicit operator contracts rather than hidden special cases.
14. Calculator produces coherent complete `Module1Result` objects.
15. Scenario calculations produce separate complete results rather than manually combining inconsistent intermediate outputs.
16. Downstream consumers use `Module1Result` and preserve the separate Duration, Curve, and Credit meanings unless a validated aggregation contract exists.
17. Configuration-only model changes do not require Calculator source changes when the required capability already exists.
18. Generic capability validation and model-specific invariants remain distinguishable.

---

## 20. Summary

The central architecture is:

```text
YAML defines macro features, bond-market features, components, and stances
        ↓
Schema validates and resolves the model
        ↓
Calculator executes reusable ordered blocks
        ↓
shared macro and bond-market features are calculated once
        ↓
Duration, Curve, and Credit interpret those features through declared stance logic
        ↓
Module1Result records one coherent completed calculation
```

The design goal is not abstraction for its own sake. The goal is to make model variation primarily configuration-driven, keep execution mechanics reusable, preserve explicit stage semantics, calculate shared macro conditions once, and prevent Duration, Curve, Credit, or downstream consumers from developing separate accidental architectures. Other modules remain consumers of the completed `Module1Result`; they should preserve its distinct exposure dimensions rather than reconstructing or collapsing Module 1 logic without an explicit model contract.
