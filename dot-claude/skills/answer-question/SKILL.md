---
name: answer-question
description: Research-only mode. Read files, search code, search the web. No code changes, no implementation loop. Gives the Research office a cheap analyst mode that cannot accidentally trigger implementation.
effort: low
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

Research never crosses into implementation: no writes, no builds, no deploys. Contract:
every cited path is checked to exist, every external link resolves, every claim carries
its evidence tag. An answer whose citations do not resolve is a draft.


## Purpose

Answer a question about the codebase, architecture, technology, or design decisions. This skill runs a research-only loop: read, search, synthesize. No code changes, no test runs, no deploys.

## Allowed

- Read, Grep, Glob (file search and content search)
- Bash, read-only: `git log`, `git diff`, `git show`, `ls`, `wc`
- Web search and web fetch (external research)
- Subagent spawn with an explore-only brief (codebase exploration)

## Forbidden

- Write, Edit (no code changes)
- Bash with write commands, builds, or deploys
- Implementation loops (no TDD, no build-fix cycles)

## Reflection (mandatory)

Research-only does not mean verification-free. Every agent loop ends with a verification pass, and in this mode the pass runs over the ANSWER itself, the pstack pattern applied to research:
- Every cited file path and line number exists (check them, do not trust recall)
- Every external link resolves
- Every claim is tagged: established, adaptation, original synthesis, unverified, or secondary-only
- Numbers from secondary sources are never presented as fact

An answer whose citations do not resolve is a draft, not a result.

## Output format

Answer with citations:
- File references: `path/to/file.py:42`
- Code snippets: inline with line numbers
- External sources: markdown links

## When to exit

If the answer reveals that code changes are needed, state what needs changing and hand back to the normal loop. Do not start implementing inside this skill.
