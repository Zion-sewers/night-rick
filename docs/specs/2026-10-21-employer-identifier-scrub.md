---
PRD: Boundary enforcement
Ticket: night-rick #114
Status: active
Date: 2026-10-21
---

# Spec — Former-employer identifier scrub (dot-agents, dot-codex)

## Goal
Complete the identifier scrub that #110 performed on `dot-claude/skills`, extended to
`dot-agents/skills` and `dot-codex/skills`. Remove every former-employer identifier
(company and product names, internal hostnames, resource-group and project names,
internal email addresses, coworker attributions) while preserving the underlying
technique, command, or worked example in each skill.

## Why this shape
The repo is personal infrastructure. Employer-identifying literals in skill content
are a boundary violation in the wrong direction (work → personal is forbidden).
The scrub is mechanical and must not change behavior:

- Identifying literals become bracketed placeholders (`<resource-group>`,
  `<foundry-account>`, `<devops-org>`, …), reusing #110's established mapping
  wherever the identical literal appeared in both trees.
- Named-coworker attributions in worked examples become role descriptions
  (technical peer / manager / casual teammate / …), reusing #110's mapping.
- Hardcoded employer defaults in shell scripts become `${VAR:?...}` required-env-var
  checks, placed after CLI flag parsing so a `--flag` can still satisfy them.
- Third-party names that are the actual subject of a skill (competitor brands in an
  ORM doc, font-designer credits, real third-party tool names) are kept, not scrubbed.

## Acceptance
- [ ] Zero hits for the full identifier list across both trees (verified by grep sweep).
- [ ] All touched shell scripts pass `bash -n`; all touched JSON parses.
- [ ] `codemap.py check` and `docmap.py check` clean for the branch's files.
- [ ] No new work material added — diff is strictly removal/replacement.
