# Content — Spine, Template, Prompt, Q&A, Diagrams

## Content Spine

Sections marked **[REQUIRED]** must always be present.

```
┌─────────────────────────────────────────────────────┐
│  HEADER BAND                          [REQUIRED]    │
│  Title · Badge row · Last-updated · Owner           │
├─────────────────────────────────────────────────────┤
│  OVERVIEW                             [REQUIRED]    │
│  1-paragraph purpose + KPI metric cards             │
├─────────────────────────────────────────────────────┤
│  UI DESIGN FLOW                       [REQUIRED]    │
│  End-to-end interaction diagram                     │
├─────────────────────────────────────────────────────┤
│  SYSTEM PROMPT                        [REQUIRED]    │
│  Full prompt in styled dark code block              │
├─────────────────────────────────────────────────────┤
│  AGENT BEHAVIOR / PIPELINE            [RECOMMENDED] │
│  Step-by-step numbered flow                         │
├─────────────────────────────────────────────────────┤
│  Q&A REFERENCE                        [REQUIRED]    │
│  Categorized accordion Q&A pairs                    │
├─────────────────────────────────────────────────────┤
│  ARCHITECTURE                         [RECOMMENDED] │
│  Component table with SLA / owners                  │
├─────────────────────────────────────────────────────┤
│  KPI DASHBOARD                        [OPTIONAL]    │
│  Live metrics cards                                 │
├─────────────────────────────────────────────────────┤
│  CHANGELOG                            [RECOMMENDED] │
│  Version history table                              │
└─────────────────────────────────────────────────────┘
```

### Section Ordering Rules

- **Lead with Overview.** Context before detail. Never open with architecture or code.
- **UI Flow before System Prompt.** Readers need the "what" before the "how".
- **Q&A near the bottom.** Reference material, not narrative.
- **Changelog last.** Audit trail, not content.

### Heading Hierarchy

```markdown
# Page Title                          ← One per page, H1
## Section Name                       ← Major sections
### Subsection Name                   ← Within a section
#### Detail Heading                   ← Use sparingly
```

Never skip levels — `####` must live inside `###` inside `##`.

## Agent Content Template

Canonical structure. Fill in bracketed placeholders.

```markdown
# [Agent Name] — Customer Support Agent

<!-- PASTE HEADER BAND HTML (components.md § Header Band) -->

---

## Overview

[Agent Name] is an Azure OpenAI-powered conversational agent deployed on [Channel(s)].
It handles tier-1 support for [Product/Team] by resolving [X]% of inbound tickets
without human intervention, routing escalations to [CRM] with full context.

<!-- PASTE 4 KPI CARDS in a grid (components.md § KPI Metric Card) -->

---

## UI Design Flow

[2-3 sentence description of the user journey.]

<!-- PASTE FLOW DIAGRAM (see Mermaid section below) -->

---

## System Prompt

The following prompt governs identity, tone, capabilities, and safety.

<!-- PASTE SYSTEM PROMPT CODE BLOCK (components.md § System Prompt Code Block) -->

---

## Agent Behavior Pipeline

<!-- PASTE STEP PIPELINE (components.md § Step / Decision Pipeline) — 5 steps minimum -->

---

## Q&A Reference Bank

### Account & Authentication
<!-- PASTE ACCORDIONS -->

### Billing & Payments
<!-- PASTE ACCORDIONS -->

### Orders & Fulfillment
<!-- PASTE ACCORDIONS -->

### Technical Issues
<!-- PASTE ACCORDIONS -->

---

## Architecture

<!-- PASTE ARCHITECTURE TABLE (components.md § Architecture Component Table) -->

---

## KPIs & Monitoring

<!-- PASTE 6 KPI CARDS -->

---

## Changelog

<!-- PASTE CHANGELOG TABLE (components.md § Changelog Table) -->
```

## System Prompt Authoring Standard

### Mandatory Sections

```
## Identity
  - Agent name, role description
  - Tone and persona
  - Language handling

## Capabilities
  - What the agent CAN do
  - Available tools / function calls (with param hints)
  - Knowledge domains

## Constraints
  - What the agent MUST NOT do
  - PII rules, policy boundaries

## Escalation Triggers
  - Handoff conditions
  - Confidence threshold (numeric)
  - Max retry count

## Response Format
  - Length guidance per query type
  - Markdown vs plain text
  - Citation format for KB articles
```

### Quality Rules

- **Specific, not verbose.** "Respond in 2-3 sentences for simple factual queries" > "Keep responses concise."
- **Absolute constraints.** "Never disclose" not "try to avoid disclosing."
- **Numeric thresholds.** "Confidence < 0.72" not "when unsure."
- **Version the prompt.** First line: `# Prompt Version: 2.4 | Last modified: Apr 2026`.
- **Markdown inside the prompt.** GPT-4o renders `##` + `-` as structure.

## Q&A Authoring Rules

| Rule | Correct | Wrong |
|---|---|---|
| Question format | User-voice, natural | "FAQ Item 7" |
| Answer length | 2-4 sentences | 10+ lines or 1 word |
| Answer tone | Direct, no jargon | "Per policy section 4.2..." |
| Category badge | Always present | Missing |
| Order within category | Most-asked first | Alphabetical |

### Category System

| Category | Badge Color | Typical Volume |
|---|---|---|
| Account & Auth | Blue | 30% |
| Billing & Payments | Green | 25% |
| Orders & Fulfillment | Orange | 20% |
| Technical Issues | Red | 15% |
| Product Information | Purple | 10% |

### Well-Formed Example

```
Q: Why was I charged twice for my last order?
Category: Billing
A: Duplicate charges are usually caused by a payment retry after a
   network timeout. The extra charge is typically reversed within
   3-5 business days. If it persists beyond 5 days, reply with
   your order number and we'll escalate to the payments team.
```

### Poorly-Formed (Do Not Use)

```
Q: Billing issue?              ← Too vague, not user-voice
A: Please contact billing.    ← Not helpful
```

## UI Design Flow — Mermaid Standard

Use Mermaid `flowchart` for all UI flow. Azure Wiki renders `::: mermaid` natively.

```
::: mermaid
flowchart TD
    A([User]) --> B[Chat Widget Opens]
    B --> C{Authentication\nCheck}
    C -- Not logged in --> D[Show Login Prompt]
    C -- Logged in --> E[Load Conversation Context\nfrom Redis]
    D --> E
    E --> F[User Sends Message]
    F --> G[Azure Functions\nPreprocessor]
    G --> H{Content Safety\nFilter}
    H -- Flagged --> I[Return Safety\nDecline Message]
    H -- Clean --> J[Azure OpenAI\nGPT-4o Inference]
    J --> K{Confidence\nScore Check}
    K -- Score less than 0.72 --> L[Escalate to\nHuman Agent Queue]
    K -- Score >= 0.72 --> M[Tool Call Required?]
    M -- Yes --> N[Execute Tool\nget_order / create_ticket]
    N --> O[Inject Tool Result\ninto Context]
    O --> P[Final Response\nGeneration]
    M -- No --> P
    P --> Q[Send Response\nto User]
    Q --> R{Resolved?}
    R -- Yes --> S([Close Ticket])
    R -- No --> F
:::
```

### Mermaid Rules

- `TD` (top-down) for linear flows, `LR` (left-right) for state machines.
- Decisions: `{}` diamond nodes. Always label both branches.
- Start/End: `([...])` stadium shapes.
- Max 8-10 nodes per row. Split complex flows.
- No Mermaid theme styling — renders inconsistently across tenants.
- All decision arrows labeled (`-- Label -->`).

### HTML vs Mermaid Decision

| Use case | Recommendation |
|---|---|
| End-to-end flow (7+ nodes) | Mermaid flowchart |
| Architecture block diagram | HTML flex/grid boxes |
| State machine | Mermaid stateDiagram-v2 |
| Sequence | Mermaid sequenceDiagram |
| Simple 3-4 step pipeline | HTML step component (components.md) |
