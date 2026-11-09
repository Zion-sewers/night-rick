---
name: youtube-distill
description: "Analyse a YouTube video via Gemini in the browser and distil it into a fixed, checkable artifact: thesis, mechanism, evidence with timestamps, disagreement, search terms, and what is quoted vs inferred. Triggers on 'analyse this video', 'distil this youtube', 'summarise this video', a bare YouTube URL, or /youtube-distill. Canonical YouTube skill (merged with youtube-gemini 2026-10-10; the repo is the canonical source)."
---

# YouTube distill

Turn a video into a small, checkable artifact instead of a summary nobody re-reads.

The mechanism is a browser round trip: open Gemini in the managed browser, hand it the
YouTube URL with a fixed question, and read the answer back. Gemini is used because it
reads the video itself from the URL rather than a scraped transcript, which is a
capability the local session does not have.

## What Gemini can and cannot do here, measured before relying on it

- It accepts a YouTube URL directly and reasons over the video.
- **It cannot produce a verbatim transcript.** It summarises and answers; it does not
  return the words in order. So nothing it returns may be presented as a quotation.
- Public videos only. Private and unlisted fail.
- One video URL per request, and a daily cap around eight hours of video.
- Timestamps use `MM:SS`, and it will honour them if you ask about a specific moment.

The consequence that shapes this whole skill: **the output is a model's reading of a
video, not the video.** A timestamp Gemini returns is a POINTER TO GO CHECK, never
evidence on its own. Anything load-bearing gets opened at that timestamp by a human or
by a second pass before it is repeated as fact.

## Step 1: name the research phase before writing the question

The question changes completely depending on why you are watching. Three phases, each
needing a different mind, from Neel Nanda's research process
(https://www.lesswrong.com/posts/hjMy4ZxS5ogA9cTYK/how-i-think-about-my-research-process-explore-understand):

- **Explore.** You do not yet know the right question. The goal is to learn the shape of
  the problem space without trying to confirm anything. Ask for the map, the vocabulary,
  and the disagreements. Noticing which anomaly is interesting rather than boring is the
  whole skill here.
- **Understand.** You have a hypothesis. The goal is a question that would distinguish it
  from its nearest rival. Ask what the speaker's claim predicts that a competing claim
  does not. Treat every result as false until shown otherwise, and treat an exciting
  result as more likely false, not less.
- **Distill.** You already understand it and need to hand it on. Ask what the shortest
  defensible version is and what to leave out. Distillation is a judgement about what to
  deprioritise, not a compression of everything.

The phases are not a pipeline. Finding a mess during Distill sends you back to Explore,
and that is the normal case rather than a failure.

**Research taste** is the acquired sense of which questions are worth asking at all. It
is trained on small, unambitious attempts, not on one large one. If you cannot say what a
video would change about a decision you are making, that is the signal to skip it.

## Step 2: choose the question by expected information gain, not by coverage

Do not ask for a summary. A summary maximises coverage, and coverage is the wrong
objective: it returns what you already know alongside what you do not, at equal length.

Pick the question whose ANSWER YOU CANNOT PREDICT. Formally this is expected information
gain, the drop in entropy from prior to posterior once the answer is known
(https://arxiv.org/abs/2406.17453). Practically, the test is one sentence:

> Write down what you expect the answer to be. If you can, the question is worth little.
> Ask the one where you cannot.

Two corollaries worth keeping. A highly informative question is useless if the source
cannot answer it, so weight by answerability as well as by information. And a question
that can only be answered "yes" carries no information at all, whatever it feels like.

## Step 3: run it (verified route, 2026-10-10)

Use `browser.spawn_task` (one message per round trip; wait for the handoff before
continuing). Task template:

"Open gemini.google.com. If the signed-in chat interface loads, you are ready. Locate
the prompt input box, type the following message exactly, send it, wait for the response
to finish generating, then report the full reply text back. Message: <THE CONTRACT
BELOW with the URL substituted>. Do not navigate away, open other chats, or change any
settings."

Read the answer from the handoff text rather than screenshots. Text is cheaper and exact.
If the answer is truncated or still streaming, steer the same task to re-read rather than
guessing. Never fill a gap from your own knowledge of the topic: a plausible sentence you
wrote is indistinguishable in the artifact from something the video said, and that is the
failure this skill exists to prevent.

Fallback (only if Gemini reports it cannot access the video): transcript extraction is
UNVERIFIED in this environment — verify tooling first or ask the user; do not present it
as working.

## The contract sent to Gemini

Keep it minimal and fixed. A stable contract makes two videos comparable; a bespoke
prompt per video makes every artifact a one-off.

```
Watch this video and answer ONLY the following. Do not summarise.

URL: <youtube url>

1. THESIS. The single claim the video is arguing for, in one sentence. If it argues
   for nothing, say so.
2. MECHANISM. How the thing actually works, in at most five sentences. Concrete over
   abstract. If a mechanism is asserted but never explained, say which.
3. EVIDENCE. What is offered as support, and of what kind: measurement, demo,
   anecdote, appeal to authority, or none. Give MM:SS for each.
4. LOAD-BEARING TIMESTAMPS. At most five MM:SS pointers where a claim I would repeat
   is actually made, so I can verify them myself.
5. DISAGREEMENT. Anything the speaker presents as settled that is actually contested,
   and anything they explicitly disagree with.
6. VOCABULARY. The exact terms, tool names, paper titles and people named, spelled as
   said. This is for search, so precision beats readability.
7. WHAT IS NOT HERE. What a viewer would wrongly assume was covered.
8. CONFIDENCE. For each of 1 to 3, say whether you are reading it from the video or
   inferring it.

If you cannot access the video, say exactly that. Do not answer from the title.
```

Item 8 is the one people delete first and it is the one that matters. Without it the artifact cannot distinguish what the video said from what the model filled in.

## Step 4: the artifact

Write one file. It is short on purpose.

```markdown
# <title> (<channel>, <duration>)
Source: <url>          Read by: Gemini via browser, <date>
Phase: explore | understand | distill
Question asked, and why its answer was unpredictable: <one line>

THESIS
MECHANISM
EVIDENCE          (kind + MM:SS)
CHECK THESE       (<= 5 timestamps, unverified until opened)
DISAGREEMENT
SEARCH TERMS      (exact spellings, for finding this again and for the next query)
NOT COVERED
DECISION          What this changes. If nothing, say "nothing" and keep the file anyway.
```

`SEARCH TERMS` is the row that earns the artifact's keep. Six months later nobody rereads
a summary, but the exact spelling of a tool or a paper is what makes the thing findable.

`DECISION` saying "nothing" is a real and useful outcome. A file that always finds a
decision is a file that invents them.

## Step 5: verify before it becomes a claim

Anything that will be repeated as fact gets one of these before it leaves the artifact:

- Open the timestamp and confirm it.
- Or search for the primary source. A video citing a paper is not the paper. If the
  video names a benchmark, the benchmark's own page settles the number.
- Or mark it `unverified` in the artifact and keep it marked.

For a claim that would change a decision, do a second pass with a DIFFERENT question
rather than re-asking the same one. Re-asking the same question of the same model
produces agreement, not confirmation.

## Boundaries

- Never present Gemini's words as the speaker's words. It cannot transcribe.
- Do not send private repository content, credentials or personal data into the browser
  prompt. The URL and the fixed contract are all that goes.
- One video per run. The daily cap is real and a batch will fail partway with no clear
  error.
- If the video is unavailable, record that and stop. Do not answer from the title, the
  channel, or prior knowledge of the topic.
- Reply in the user's language (Hebrew for Shoval) unless asked otherwise.
