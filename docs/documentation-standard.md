# Documentation Standard

This document defines the writing and maintenance standard for P37 Neuro technical documentation.

The objective is documentation that is precise, durable, navigable and evidence-backed.

## 1. Document types

Use the correct document type instead of mixing several purposes in one file.

### Overview

Explains what the product/system is, why it exists, its scope and its current maturity.

### Architecture

Explains system boundaries, responsibilities, data/control flow and important design decisions.

### Reference

Defines contracts, schemas, APIs, configuration or exact behavior.

### How-to / procedure

Provides steps for a concrete task such as training, testing, deployment or integration.

### Validation report

Records a frozen protocol, results, evidence and supported conclusion for one experiment or release.

### Roadmap/status

Tracks planned and completed work. It must distinguish software implementation from capability validation.

---

## 2. Canonical-source rule

A fact should have one canonical home.

Other documents should link to that source instead of copying large sections.

Examples:

- current stage status → `roadmap.md`;
- system definition → `overview.md`;
- layer boundaries → `architecture.md`;
- qualification protocol → `testing.md`;
- measured experiment result → a file under `docs/validation/`.

Avoid maintaining the same status table independently in several places.

---

## 3. Evidence and claim levels

Every capability statement must match the evidence level.

Use these classifications:

1. **software validation** — code/contracts/runtime checks;
2. **synthetic smoke validation** — controlled generated tasks without representative physics;
3. **simulation capability evidence** — held-out physics-simulation result;
4. **hardware-in-the-loop evidence** — target runtime/controller path without unrestricted physical operation;
5. **physical capability evidence** — measured real-robot result;
6. **production/fleet evidence** — measured deployed-system behavior.

Do not write “validated” without specifying the level.

Do not promote a synthetic/simulation result to a physical claim.

---

## 4. Status language

Use precise status terms.

### Implemented

The software exists and is covered by its normal engineering checks.

### Platform complete

The required software path for that stage exists end to end.

### Experimentally demonstrated

A specific controlled experiment produced the documented result.

### Qualification in progress

The software path exists and the defined capability gates are still being evaluated. Use this for active maturity work instead of describing unfinished qualification as a failure.

### Non-qualifying / inconclusive result

Use these terms in validation reports when a completed experiment does not meet a predefined threshold or does not support a clear conclusion. Reserve **failure**, **failure mode** and **fail-closed** for operational errors, safety behavior and diagnostic taxonomy where those terms are technically precise.

### Simulation validated

The capability passed a predefined held-out physics-simulation protocol.

### Physically validated

The capability passed the predefined physical-robot protocol.

### Production validated

The capability/release path passed the predefined live deployment protocol.

Avoid vague labels such as “done,” “production ready,” “general,” or “works on any robot” unless the scope and evidence make the statement objectively true.

---

## 5. Required structure for major technical documents

Use the following order when applicable:

1. title;
2. status/scope;
3. purpose;
4. system or capability definition;
5. architecture/process;
6. interfaces or responsibilities;
7. current implementation state;
8. limitations/non-goals;
9. validation/evidence;
10. related documentation.

Long documents should include a navigation table or clear headings.

---

## 6. Writing style

P37 documentation should be technically precise, direct, neutral, specific about scope and readable by an engineer who did not build the subsystem.

Prefer:

> The runtime rejects observations older than the configured maximum age.

Avoid:

> The runtime is extremely robust and enterprise-grade.

Prefer:

> The current synthetic E4 smoke test showed lower recovery error when recurrent memory was preserved.

Avoid:

> P37 has solved long-horizon robot memory.

---

## 7. Architecture diagrams

A diagram must show direction of data/control flow, name boundaries consistently, distinguish learned components from deterministic components, avoid implying unimplemented dependencies and remain synchronized with the architecture document.

Complex visual diagrams should have an editable source checked into the repository when practical.

---

## 8. Procedures and commands

Commands must be copyable.

State the required working directory, prerequisites, optional dependencies, environment variables, expected success condition and whether a command spends money, uses cloud resources or controls hardware.

Never include private keys, credentials, real secret values or account-specific tokens.

Use clearly named placeholders.

---

## 9. Versioning and reproducibility

Validation and release documents should record:

- date;
- commit SHA;
- checkpoint/artifact ID;
- dataset version;
- environment/simulator version;
- hardware where relevant;
- seed/configuration;
- result classification.

When behavior changes materially, update the canonical document in the same engineering change.

Historical validation reports should not be rewritten to match newer results. Add a new report.

---

## 10. Safety documentation

For actuator-facing behavior:

- distinguish learned policy behavior from deterministic safety;
- state the independent safety mechanism;
- identify failure behavior;
- document limits/watchdogs/stops;
- do not imply software-only checks replace manufacturer or certified safety systems.

Physical test instructions must require an independent emergency-stop path.

---

## 11. Documentation review checklist

Before merging a substantial documentation change, verify:

- [ ] the document has one clear purpose;
- [ ] terminology matches the rest of the repository;
- [ ] claims match the evidence level;
- [ ] implementation and capability status are separated;
- [ ] links point to canonical sources;
- [ ] commands are reproducible;
- [ ] no secrets or private infrastructure values are present;
- [ ] historical results are not silently rewritten;
- [ ] safety scope is explicit where physical systems are involved;
- [ ] the README/docs index points users to the right entry point.

---

## 12. Naming conventions

Use:

- **P37 Neuro** — product/program name;
- **P37** — acceptable shorthand after first use;
- **robot brain** — shared intelligence system connecting perception, embodiment, context, policy, action and learning;
- **embodiment** — a specific robot body's morphology/control representation;
- **checkpoint** — serialized learned model state;
- **artifact** — immutable deployable model/package identified by digest;
- **release** — signed/promoted artifact plus lineage and evidence;
- **capability** — measured behavior under a defined evaluation protocol.

Avoid inventing synonyms for established subsystem names inside technical documentation.
