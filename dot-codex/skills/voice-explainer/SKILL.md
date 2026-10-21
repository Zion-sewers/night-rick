---
name: voice-explainer
description: Generate short audio narration via ElevenLabs eleven_multilingual_v2 and auto-play it. Triggers on out-of-focus / tired / "read it to me" signals (en/he/ar) detected by the UserPromptSubmit hook.
model: haiku
allowed-tools: ["Bash($HOME/.claude/bin/generate-voice.py *)", "Bash($HOME/.claude/bin/pop-voice.sh *)"]
---

# Voice Explainer

Generate short audio narration via ElevenLabs `eleven_multilingual_v2` and auto-play it. For when the user is out of focus, tired, walking, or explicitly asks for audio.

## When to invoke

**User signal:**
- "i'm tired", "i'm out of focus", "out of focus", "i'm zoning out"
- "tell me what you're doing", "narrate this", "say it out loud", "read it to me"
- "audio it", "audio mode", "tldr audio"
- Hebrew: "אני עייף", "אני לא מתרכז", "תקריא לי", "תגיד בקול", "תספר לי", "באודיו"
- Arabic: "أنا متعب", "اقرأ لي"
- A `UserPromptSubmit` hook (`~/.claude/hooks/voice-explainer-trigger.sh`) injects the hint when these phrases appear.

**Proactive (no user signal needed):**
- Long-running analysis (>2 minutes of tool calls): emit a 30-60 word audio status update once mid-flight.
- End-of-task recap when a multi-step plan finishes: a 60-90 word podcast-style summary.
- Critical alerts: credit-guard freeze trip, autonomous-night handoff, watchdog abort.
- Mode-change announcements: "switching to autonomic mode until 06:00" / "back to regular mode."

Do NOT use:
- For every Claude response (would be exhausting).
- For code blocks (visual is better).
- When the user is in a meeting (no detection for this; user can `touch /tmp/.claude-voice-disabled`).

## How to use

```bash
~/.claude/bin/generate-voice.py "<text to speak>" \
  --voice calm_female \
  --out-name <slug>
```

The helper:
1. Fetches `<your-secret-name>-ElevenLabsApiKey` from `<your-key-vault-name>` via az.
2. POSTs to `https://api.elevenlabs.io/v1/text-to-speech/<voice_id>` with `eleven_multilingual_v2`.
3. Saves MP3 to `~/.claude/assets/voice/<slug>-<unix>.mp3`.
4. Auto-plays via `ffplay -nodisp -autoexit` (no window, exits when done).
5. Prints a markdown reference + duration + cost estimate.

Pass `--no-pop` to skip auto-play (just save the file).

## Length guidance

| Use case | Target words | Why |
|---|---|---|
| Out-of-focus check-in | 30–50 | quick orientation |
| Mid-flight status | 60–80 | enough context, not boring |
| End-of-task recap | 80–120 | summary + next step |
| Mode/alert announcement | 10–25 | one beat |
| Daily Brief read-aloud | 200–400 | morning podcast |
| Spec read-aloud | 1–4 minutes | walking commute |

ElevenLabs charges ~$0.30 per 1000 characters. The user has rich credits (per them) — be generous on quality, careful on volume. One audio per response unless explicitly requested otherwise.

## Voice profiles

| Profile | Use for | Voice |
|---|---|---|
| `calm_female` (default) | narrator / status / brief | Freya |
| `calm_male` | narrator alt | Arnold |
| `authoritative_female` | alerts / release gate | Bella |
| `authoritative_male` | release gate alt | Adam |
| `energetic_female` | morning brief / good news | Bella (lower stability) |
| `energetic_male` | shipping / PR merged announcement | Adam (lower stability) |
| `premium_female` | weekly engineering update | Freya (mid stability) |
| `premium_male` | weekly engineering update alt | Arnold (mid stability) |

Edit voice IDs in `~/.claude/bin/generate-voice.py` if you want different voices.

## Multilingual

`eleven_multilingual_v2` auto-detects Hebrew, English, Arabic. Match the user's language:
- They wrote Hebrew → narrate in Hebrew
- English → English
- Arabic → Arabic (limited utility today; depends on which markets your work touches)

For technical nouns (deployment names, repo names, file paths), keep them in English even within Hebrew narration — that matches the user's natural code-switch pattern (per `shoval-voice-draft` SKILL).

## Niche use cases worth wiring

These are the ways audio earns its keep beyond the obvious narration.

### Tier 1 — implement now if requested
1. **Out-of-focus check-in** (the user's request) — they say "im out of focus" → 40-word audio status: what i'm doing, what's done, what's next.
2. **Long-task progress narration** — when running analysis or large refactor, emit a 60-word audio status every 2-3 minutes so user can lean back.
3. **End-of-task podcast recap** — finishing a multi-step plan: 90-word audio summary like a podcast intro: "alright, here's what just happened: ..."
4. **Mode-change announcement** — entering autonomic mode: "switching to autonomic mode now, will stop at 06:00 sharp." Two seconds of audio.

### Tier 2 — high leverage, easy
5. **Credit-guard freeze trip** — 15-word alert: "credit guard tripped: spend day-over-day delta exceeded 2x. all routines frozen until you unfreeze." Authoritative voice.
6. **Build-failed announcement** — "build 11711 on master failed: docker push unauthorized. logs in PR comments." Authoritative voice.
7. **Morning brief read-aloud** — daily 09:00 IDT, the routine #4 brief gets auto-narrated to a podcast-mode MP3 saved to `~/.claude/assets/voice/morning-brief-YYYY-MM-DD.mp3`. User listens during coffee.
8. **Walking commute mode** — `~/.claude/bin/walking-mode "topic"` reads the relevant SPEC sections + recent rollouts as continuous audio (5-10 min). For when the user is walking.

### Tier 3 — niche but valuable
9. **TL;DR mode** — paste a long doc, get a 30-second audio summary. Useful for vendor whitepapers, vibe-coder slop submissions.
10. **Voice handoff between sessions** — when one session ends in autonomic mode, write a `handoff.mp3` alongside `handoff.md`. Next session start plays it as preamble.
11. **Khaleeji Arabic narration** — for regional-market marketing content, generate narration in Khaleeji dialect. Use `eleven_multilingual_v2` with Arabic input; voice profile may need re-cast for that dialect specifically.
12. **Pair-programming "thinking out loud" mode** — every time a substantive plan or decision is reached, narrate it in 1 sentence. Good for the user feeling like they're pairing with a real person.
13. **Eyes-tired accessibility mode** — explicit toggle (`touch /tmp/.claude-voice-everything`) makes every assistant response also generate audio. For neck/eye fatigue moments. Off by default.

### Tier 4 — defer or skip
14. **Voice agents (interactive)** — full conversational voice via ElevenLabs Conversational AI. Out of scope for this skill; that's a separate product.
15. **Custom voice cloning** — train a "Shoval voice" clone for outbound messages on Teams. Privacy-heavy; not in scope.

## Files involved

- Helper: `~/.claude/bin/generate-voice.py`
- Pop script: `~/.claude/bin/pop-voice.sh`
- Output dir: `~/.claude/assets/voice/`
- Trigger hook: `~/.claude/hooks/voice-explainer-trigger.sh` (UserPromptSubmit)
- Disable flag (session-level): `touch /tmp/.claude-voice-disabled`

## Output to user

Always:
- Show the markdown reference + duration + cost: `🔊 [slug](path) (3.2s gen, 240 chars, ≈$0.07)`
- Audio plays automatically (unless `--no-pop`); user does not need to click anything.
- Keep narration concise — long audio is exhausting. Match the length-guidance table above.

## Hard rules

- Never auto-narrate sensitive content (passwords, API keys, customer PII, medical/legal text).
- Never claim to *be* the user (this is a TTS narration of *what i did*, not impersonation).
- Default voice is calm_female (Freya). Don't switch voices mid-task.
- Cool down 90 seconds between hook-triggered nudges (the hook handles this).
- Audio out of focus or tired ≠ skip the regular text response. Always include both.
