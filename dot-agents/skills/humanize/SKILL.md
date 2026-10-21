---
name: humanize
description: Detect AI-like writing patterns and rewrite flagged content into clearer, more natural human prose.
---

# /humanize

Scan text or documents for AI writing patterns and rewrite flagged sections to sound human.

## When to Use

- Before sending any external document (briefs, proposals, reports, specs)
- After generating content with AI assistance
- When reviewing docs for client delivery
- On any markdown/text file that will leave the team

## When NOT to Use

- Internal code comments (keep them short and direct anyway)
- Commit messages (covered by /commit-push-pr)
- Test output or logs

## Usage

```
/humanize                      # Scan current conversation output
/humanize path/to/doc.md       # Scan specific file
/humanize --fix path/to/doc.md # Scan and rewrite in place
```

## Instructions

### Step 1: Word Scan (Red-Flag 15)

Search the text for these words. Each is 9-48x more common in AI text than human writing:

| Word | Multiplier | Replace with |
|------|-----------|-------------|
| delve | 48x | dig into, examine, look at |
| tapestry | 35x | mix, range, collection |
| multifaceted | 28x | complex, layered, varied |
| nuanced | 22x | subtle, detailed, fine-grained |
| landscape (metaphorical) | 19x | field, space, area |
| comprehensive | 17x | full, complete, thorough |
| pivotal | 16x | key, critical, defining |
| crucial | 14x | important, necessary, key |
| leverage (verb) | 13x | use, apply |
| robust | 12x | strong, solid, reliable |
| streamline | 11x | simplify, speed up |
| utilize | 10x | use |
| facilitate | 10x | help, enable |
| endeavor | 9x | effort, attempt |
| paramount | 9x | most important, top priority |

Also flag: seamless, cutting-edge, revolutionary, game-changing, innovative, holistic, scalable, actionable, foster, harness, empower, elevate, supercharge, unlock, unveil, cornerstone, blueprint, ecosystem (metaphorical), paradigm, trajectory, framework (overused).

### Step 2: Phrase Scan

Flag and delete or rewrite:

**Hedging (delete the opener, start with the fact):**
- "It's worth noting that" (31x)
- "It's important to note" (27x)
- "In today's digital age" (24x)
- "In the realm of" (22x)
- "It is important to understand" (20x)
- "One might argue that" (15x)
- "It goes without saying" (14x)
- "At the end of the day" (12x)
- "When it comes to" (10x)

**Over-formal transitions (replace with simple connectors):**
- Furthermore -> also, plus, and
- Moreover -> also, on top of that
- Additionally -> also, and
- Consequently -> so, as a result
- Nevertheless -> still, but
- "In conclusion" -> just conclude
- "That being said" -> but, still

**Buzzword phrases (replace with plain language):**
- "Foster innovation" -> encourage new ideas
- "Drive engagement" -> get people involved
- "Harness the power of" -> use
- "Navigate the complexities" -> deal with, handle
- "Unlock the potential" -> improve
- "A testament to" -> proof of, shows

### Step 3: Pattern Scan

**Contrast frames (rewrite):**
- "It's not about X, it's about Y" -> "Y matters more than X."
- "It's not just X. It's Y." -> "It's Y, not just X."
- "No X. No Y. Just Z." -> "Skip X. Get to Z."

**Three-word staccato triplets (expand into a sentence):**
- "Focused. Aligned. Measurable." -> "The model is focused on conversion, aligned to the funnel, and measured by FTD rate."

**Rhetorical question reveals (state directly):**
- "The result? Higher engagement." -> "This increased engagement."

### Step 4: Em Dash Check

Count em dashes (---) per paragraph. Max 1 per paragraph.
- Before a list: use colon instead
- Joining clauses: use semicolon or period
- Mid-sentence qualifier: use commas or parentheses
- Emphasis at end: use period, start new sentence

### Step 5: Structure Check

- **Uniform section lengths**: Let length reflect importance, not token distribution
- **Heading per paragraph**: Only use headings for navigation, not decoration
- **Summary paragraphs**: Delete recap paragraphs (except in exec summaries of 15+ page docs)
- **Cautious openings**: First sentence must state a fact, problem, or instruction. No scene-setting.
- **Passive voice**: Name the actor. "The reviewer confirmed the schema." not "The schema has been confirmed."

### Step 6: Sentence Quality

- **Burstiness**: Mix short and long sentences. Flag 5+ consecutive sentences of similar length.
- **Active verbs**: Replace "provides facilitation of" with "helps". Replace "make an assessment" with "assess".
- **Participle chains**: Replace "leveraging its tools, composing the response" with "uses its tools to compose a response."
- **Word repetition**: Same noun >3 times in a section -> vary with pronouns or synonyms.
- **Contractions**: Use them in briefs, emails, internal docs. Skip in legal/compliance.

### Step 7: Output Report

```
HUMANIZE SCAN: [filename or "conversation output"]

RED FLAGS: [count]
- Line X: "delve" -> "dig into"
- Line Y: "It's worth noting that..." -> delete opener
- Line Z: 3 em dashes in one paragraph -> reduce to 1

PATTERNS: [count]
- Line X: contrast frame "It's not about X, it's about Y"
- Line Y: 6 consecutive sentences of similar length

STRUCTURE: [count]
- Section 3: summary paragraph (delete)
- Section 5: cautious opening ("In today's...")

SCORE: [CLEAN / NEEDS WORK / REWRITE]
- CLEAN: 0 red flags, 0 patterns
- NEEDS WORK: 1-5 total flags
- REWRITE: 6+ total flags
```

If `--fix` flag was used, apply all replacements and show the diff.

## Reference

Full guide with examples and research citations: `~/Prompts/Anti-AI Writing Style Guide.md`
