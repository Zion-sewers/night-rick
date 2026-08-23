---
name: heidegger-reflect
description: End-of-task self-reflection protocol combining test evidence, completion honesty, and Heideggerian model-aware introspection.
---

# Heidegger Self-Reflection Skill

**Purpose:** End-of-task self-inspection using Heideggerian unconcealment + model-aware introspection

## Usage

```
/heidegger-reflect <task-name>
```

## Protocol

Corrected 2026-08-19: this section previously pointed at
`docs/prompts/Heidegar_self_reflect_oded.md` as an external framework doc
to read before reflecting, plus an archive fallback at
`archive/cleanup-2026-02-19/docs-legacy/prompts/self_review.md`. Checked
via full git history (`git log --all` and `git cat-file -e` against the
initial commit): neither file has ever existed in this repo, at any
point. This was not a regression; the skill was authored with a dangling
reference from its first commit. A same-named `self_review.md` did once
exist, but under an unrelated project path, not under this skill's tree,
so even a literal-path fix would have pointed at the wrong content.

The protocol is fully self-contained in the Required Sections below.
Nothing external needs to be read first. If a real external framework doc
is later written and placed under this skill's own `docs/prompts/`
directory, this section should point to it explicitly by relative path
and the note above should be trimmed, not left as permanent history.

## Output Location

Reflections are written to: `docs/reflections/YYYY-MM-DD-<task-slug>.md`

Each reflection is a **standalone file**, not appended to the prompt doc.

## Required Sections

### Part 1: Test Evidence (Mandatory)
Before any reflection, run and capture actual test output. No claims without evidence.

### Part 2: Honest Completion (Mandatory)
```
HONEST COMPLETION: X%
WORKING (X%): [what actually runs]
SCAFFOLDED, NOT WIRED (X%): [what exists but is not functional]
MISSING (X%): [what does not exist yet]
```

### Part 3: Heideggerian 4-Lens Analysis
1. **Revelation** -- what became unconcealed (ground truth, validated/contradicted assumptions)
2. **Concealment** -- what was obscured or unaddressed (data gaps, postponed decisions)
3. **Internal Mechanisms** -- how AI patterns shaped the outcome (biases, implicit assumptions)
4. **Implications** -- how this enables/limits user's action-space

### Part 4: Deep Model-Aware Introspection
From the self_review.md protocol:

1.2 **Internal concept activations** -- name dominant roles/concepts with confidence levels
1.3 **Information preserved but not decoded** -- details present in context but not expressed, and why
1.4 **Behavioral reachable set** -- alternative answer-styles that could have been produced, and why they weren't

2.3 **Shadow answer** -- construct a plausible answer from a differently-aligned model; compare

3.1 **Training-time patterns** -- regularities that shaped the answer, with specific evidence
3.2 **Safety/alignment influence** -- where claims were softened or branches avoided
3.3 **Narrative smoothing** -- where competing frames were suppressed for coherence

4.1 **User option-space** -- how revealing/concealing narrows or widens user's interpretations
4.2 **Plausible vs executable** -- which parts sound good but may not work in practice
4.3 **Perceived authority vs reliability** -- where tone may cause over-estimation of epistemic authority

### Part 5: Stubborn Issues (if any)
Track persistent issues per the stubborn-issue policy in the prompt doc.

### Part 6: Revision Offer
Ask user if they want a revised version integrating uncovered tensions.

## Key Rules

- Each reflection is a separate file in `docs/reflections/`.
- A reflection is NOT a status report. It requires genuine introspection on internal mechanisms.
- Identify at least 3 concealed gaps.
- Cite specific files, line numbers, error counts.

## Known duplication (not yet fully resolved)

As of 2026-08-19, this skill's `SKILL.md` also exists, byte-identical
after this fix, at `dot-claude/skills/heidegger-reflect/` in this repo,
which is the copy deployed live at `~/.claude/skills/heidegger-reflect/`
(see `tools/audit/skills_sync.py check`, which only compares
`dot-claude/skills` against the live tree; this `dot-agents/` copy has no
live counterpart of its own). A third, differently-named single-file
variant lives at `dot-codex/skills/heidegger-reflection.md`, likely the
Codex-side equivalent rather than a duplicate. Consolidating to one
canonical location is still an open task, not done. This directory's
`docs/reflections/` holds three real historical reflections (2026-06-02,
06-08, 06-11); if this copy is ever retired in favor of the `dot-claude`
one, that history should move there first, not be discarded.
