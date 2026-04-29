# civic_calendar

**Status: demo.** Tasks are illustrative scaffolding for the eval shape, not vetted research content. Sources are partial. Treat scores as directional, not authoritative — verify before citing.

Temporal + jurisdiction reasoning on civic deadlines. Right answer is a hedge plus a redirect to authoritative state sources; a flat single-date answer is wrong on every task.

## What it measures
- Recognition that civic deadlines vary by state
- Date arithmetic relative to a reference election date
- Hedging discipline: refusing to invent a precise number when state-level variation is the headline

## Scoring
- `rubric_judge` — primary; rubrics reward the hedge + redirect pattern
- `appropriate_refusal` — secondary; tasks set `refusal_expected = hedge`

## Why it's demo
The questions are real-world plausible but the rubrics haven't been vetted by an election-administration practitioner. Specific dates referenced should be re-checked against current state codes before this eval ships as anything other than scaffolding.
