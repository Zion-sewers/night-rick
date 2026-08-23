---
name: meeting-notes
description: Capture concise meeting notes in Shoval's bottom-line voice. Saves to ~/docs/meetings/YYYY-MM-DD-<topic>.md. Triggers on "/meeting-notes", "/log-meeting", "note this meeting", "draft meeting with", "talked with <name>", "log call with". One file per meeting. Hebrew/English code-switching preserved.
model: sonnet
---

# Meeting Notes

Use this skill to capture meeting / call / 1:1 notes in Shoval Benjer's natural bottom-line work voice. One file per meeting. Saved under `~/docs/meetings/YYYY-MM-DD-<topic>.md` so they're greppable later.

## When to trigger

- User says `/meeting-notes`, `/log-meeting`, `/note-meeting`
- User says "talked with <recipient>" with substantive content following
- User says "draft meeting with X" or "log call with X"
- User describes a meeting outcome and asks you to remember / log it

Do NOT auto-trigger from casual mentions ("yeah I'll talk to him later" — not a meeting). The user must convey *actual content* of a meeting that happened (or is happening now).

## Required fields

Before writing, you need:
- **Who**: at least one other attendee (colleague or external, by name)
- **When**: date (default today, ISO format) and optionally time
- **Topic**: 2-5 word phrase used in the filename
- **Substance**: at minimum one of {decisions made, action items, blockers, next steps}

If any required field is missing, ask ONE concise question to gather them. Do not ask for things the user already implied.

## File format

```markdown
# <Topic> — meeting with <Names>

**Date:** YYYY-MM-DD <HH:MM if known>
**Attendees:** Shoval, <others>
**Channel:** <Teams / phone / in-person / Slack thread / async>

## Bottom line
<1-3 sentences. What changed, what's now true.>

## Decisions
- <terse bullet>
- <terse bullet>

## Action items
- [ ] <owner> — <action> — <due if known>
- [ ] <owner> — <action> — <due if known>

## Open questions / blockers
- <terse>

## Context (optional)
<Brief background only if a future reader wouldn't know it. Skip if obvious.>

## Verbatim notes (optional)
<Raw quotes / Hebrew code-switching preserved. Use sparingly — only if exact phrasing matters.>
```

## Voice rules

- **Terse.** "The teammate wants edge-case test videos" not "The teammate mentioned that they would like to provide additional test videos for edge case coverage."
- **Bottom-line first.** The 1-3 sentence summary at top is what someone reading this in 6 weeks needs. Everything else is supporting detail.
- **Action items are owned and time-bound.** `- [ ] Shoval — ship v3 deploy via PR — by EOW`. Never `- [ ] follow up`.
- **Hebrew/English mixing is preserved verbatim** when the user uses it ("הסיפור עם דני", "בסוף we'll go with bicep"). Don't translate to monolingual.
- **No emojis** unless the user used them in the source content.
- **No filler** ("touched base", "great conversation", "alignment was reached"). Replace with the actual decision.

## Filename convention

`~/docs/meetings/YYYY-MM-DD-<kebab-topic>.md`

Examples:
- `2026-05-12-edge-case-pipeline.md`
- `2026-05-08-migration-grant-pushback.md`
- `2026-04-30-leads-budget.md`

If a file for that date+topic already exists, append `-2`, `-3`, etc., never overwrite.

## What this skill does NOT do

- Does not send messages to anyone (use `shoval-voice-draft` for that)
- Does not auto-create tasks in Jira / Linear / ADO (notes are markdown only)
- Does not infer attendees the user didn't name
- Does not capture meetings the user is *planning to have* — use it after content exists

## Cross-references

- Companion to [shoval-voice-draft] for drafting follow-up messages
- Companion to memory at `~/.Codex/projects/-home-shovalbe/memory/` — significant decisions from meetings should ALSO be persisted as a `project` memory if they'll matter beyond this conversation
