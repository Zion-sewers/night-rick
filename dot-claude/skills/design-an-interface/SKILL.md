---
name: design-an-interface
description: Generate multiple radically different interface designs for a module using parallel subagents, then compare and synthesize. Use when designing an API, exploring interface options, comparing module shapes, or when the user says "design it twice".
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

Designs are proposals, not implementations. Contract: nothing is built from a design
without the reflection scratch verification (instantiate, exercise the primary path,
type-check). The comparison, not the first idea, is the deliverable.


# Design an Interface

From "A Philosophy of Software Design": your first idea is unlikely to be the best. Generate multiple radically different designs, then compare. The value is in the contrast.

## Workflow

### 1. Gather requirements

Before designing, understand:

- [ ] What problem does this module solve?
- [ ] Who are the callers? (other modules, external users, tests)
- [ ] What are the key operations?
- [ ] Any constraints? (performance, compatibility, existing patterns)
- [ ] What should be hidden inside vs exposed?

Ask: "What does this module need to do? Who will use it?"

### 2. Generate designs (parallel subagents)

Spawn 3 or more subagents simultaneously. Each must produce a **radically different** approach. Give each a different forcing constraint:

- Agent 1: minimize method count, aim for 1 to 3 methods max
- Agent 2: maximize flexibility, support many use cases
- Agent 3: optimize for the most common case
- Agent 4: take inspiration from a specific paradigm or library

Each subagent outputs:
1. Interface signature (types, methods)
2. Usage example (how a caller uses it)
3. What this design hides internally
4. Trade-offs of this approach

### 3. Present designs

Show each design with its signature, usage examples, and what it hides. Present them sequentially so each approach can be absorbed before the comparison.

### 4. Compare designs

Compare on:
- **Interface simplicity**: fewer methods, simpler params
- **General-purpose vs specialized**: flexibility vs focus
- **Implementation efficiency**: does the shape allow efficient internals?
- **Depth**: small interface hiding significant complexity (good) vs large interface with thin implementation (bad)
- **Ease of correct use** vs **ease of misuse**

Discuss trade-offs in prose, not tables. Highlight where designs diverge most.

### 5. Synthesize

The best design often combines insights from multiple options. Ask which design best fits the primary use case and which elements from other designs are worth incorporating.

### 6. Reflection (mandatory)

After synthesis, verify the chosen interface before anyone implements it: instantiate it in a scratch file, exercise the primary path the way a caller would, and confirm it type-checks. A design that cannot survive one real call is not a design. Preserve the scratch verification as evidence, then discard the scratch.

## Evaluation criteria

From "A Philosophy of Software Design":

**Interface simplicity**: fewer methods and simpler params are easier to learn and use correctly.

**General-purpose**: handles future use cases without changes, but beware over-generalization.

**Implementation efficiency**: the interface shape should allow efficient implementation, not force awkward internals.

**Depth**: small interface hiding significant complexity is a deep module (good). Large interface with thin implementation is shallow (avoid).

## Anti-patterns

- Do not let subagents produce similar designs, enforce radical difference
- Do not skip the comparison, the value is in contrast
- Do not implement, this is purely about interface shape
- Do not evaluate based on implementation effort
