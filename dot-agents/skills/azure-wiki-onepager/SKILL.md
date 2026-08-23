---
name: azure-wiki-onepager
description: Authoring standard for Azure DevOps Wiki one-page articles (design tokens, component library, content spine, Mermaid flow, Q&A accordion, system-prompt blocks). Activate when writing or reviewing a single-page ADO Wiki doc — especially for AI agent / customer-support projects. Overrides anti-slop-ui.md palette within this scope only (Azure-native blue + white surface is required for ADO Wiki visual identity).
effort: medium
---

## Scope & Activation

**Activate when:**
- Authoring or reviewing an Azure DevOps Wiki page (single long-form `.md` with embedded HTML/CSS).
- Project is an AI agent, LLM pipeline, customer-support system, or similar technical product.
- Goal is a polished, navigable, information-dense one-pager — not a raw spec dump.

**Do NOT activate for:**
- Multi-page wikis with separate nav.
- Pure Markdown wikis with no embedded HTML/CSS.
- Repo READMEs.
- Frontend application code (that still uses `anti-slop-ui.md` — see override note below).

## Scope Override — vs `anti-slop-ui.md`

`~/.Codex/rules/anti-slop-ui.md` is the global default for frontend UI and requires Catppuccin/Nord palettes, forbids white backgrounds, forbids Inter-only font stacks, and forbids gradient fills on primary CTAs.

**This skill overrides those rules *only* inside ADO Wiki one-pagers**, because:
- ADO Wiki renders inside the Azure DevOps chrome; a Catppuccin/Nord palette clashes with Microsoft's native surface.
- Azure-native identity is `#0078d4` blue on `#f6f8fa`/`#ffffff` with Segoe UI type.
- The header-band gradient (`--wiki-primary` → `#005a9e`) is an explicit Microsoft Fluent pattern, not AI-slop.

Outside ADO Wiki (`.tsx`, `.jsx`, `.vue`, `.svelte`, app CSS), `anti-slop-ui.md` still governs. Do not leak Azure Blue into application UI.

## Canonical Target Pages

When producing an ADO Wiki one-pager, mirror the structure of your own team's exemplar
reference pages in your DevOps wiki (name them here once you've picked them):

- `https://dev.azure.com/<devops-org>/<devops-project>/_wiki/wikis/<devops-project>.wiki/<page-id>/<page-name>`

These pages cannot be fetched from inside Codex (no network allowlist for `dev.azure.com`). To diff live vs template, open them in a browser or run `az devops wiki page show --wiki <devops-project>.wiki --path <path>` locally. The template defined here is authoritative; the live pages are the visual target.

## Reference Modules

Load the relevant module when authoring — they're intentionally split to stay under the 500-LOC skill-file limit:

- `reference/tokens.md` — Design tokens, typography, color, spacing, layout grids, CSS standards. **Always load first.**
- `reference/components.md` — Copy-pasteable HTML for header band, KPI cards, callouts, Q&A accordion, system-prompt code block, architecture table, step pipeline, changelog.
- `reference/content.md` — Content spine (required sections), agent content template, system-prompt authoring standard, Q&A authoring rules, Mermaid flow standard.
- `reference/checklist.md` — Interaction patterns, accessibility + performance checklist, anti-pattern catalogue, pre-publish quality gate.

## Related Memory / Rules

- Memory: `project_wiki_rewrite.md` — "Agent Wiki Rewrite Status" (thorough depth per endpoint, matching the bar a demanding technical reviewer would hold you to; `doc-design.md` is the standard).
- Rule (overridden in-scope): `~/.Codex/rules/anti-slop-ui.md`.
- Skill: `azure-devops` — ADO CLI / PR workflow (creating the wiki PR itself).

## Mental Model — 3 Jobs in Priority Order

1. **Orientate** — Reader knows within 5 seconds what the page covers and why.
2. **Inform** — Every section answers a real question a stakeholder, dev, or operator would ask.
3. **Delight** — Visual design respects the reader's time. Not a Confluence dump or Word paste.

### Google-Grade Standard

- Information density without clutter.
- Hierarchy that guides the eye.
- Restraint — one accent color, two font weights, no gradients on interactive elements (header band is the single exception).
- Consistency — every card/table/callout follows the same grammar.
- Motion only where it adds meaning (accordion expand, nothing more).

## Azure Wiki Rendering Constraints

| Feature | Supported | Notes |
|---|---|---|
| Headings H1–H6 | yes | Strict hierarchy |
| Tables (GFM) | yes | Pipe syntax |
| Fenced code blocks | yes | Prism-like highlighter |
| Raw `<style>` | yes | Page-scoped |
| Raw `<script>` | limited | No `localStorage`, no external `fetch` |
| `<details>`/`<summary>` | yes | Native accordion, no JS |
| Mermaid | yes | `::: mermaid` fenced block |
| MathJax | yes | `$...$` / `$$...$$` |
| iframes | no | Azure security policy blocks |
| External `@import` fonts | tenant-dependent | Test first |
| CSS custom properties | yes | Full modern browser support |
| `prefers-color-scheme` | yes | Use for auto dark mode |

## Fast-Path Quality Gate (pre-publish)

Before merging any wiki PR, verify (full checklist in `reference/checklist.md`):

- [ ] Opens with header band — no raw H1 first.
- [ ] `<style>` token block at top of file.
- [ ] Overview ≤ 4 sentences + KPI cards.
- [ ] UI flow diagram present (Mermaid preferred for 7+ nodes).
- [ ] System prompt in dark code block with copy button.
- [ ] Q&A uses `<details>` accordion with category badges.
- [ ] Architecture table with status pills.
- [ ] Changelog in reverse chronological order.
- [ ] Single `<h1>`, sequential heading hierarchy.
- [ ] No hardcoded hex — only `var(--wiki-*)`.
- [ ] Dark mode tested via `prefers-color-scheme: dark`.
- [ ] No external `<script src>`, no `localStorage`, no `eval()`.

---

*Skill maintained by Platform Engineering. v1.0 — April 2026.*
*Source: merged from loose `azure-wiki-onepager-skill.md` transferred from Windows side.*
