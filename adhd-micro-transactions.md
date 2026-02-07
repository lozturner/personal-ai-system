# Design Principle: ADHD Micro-Transactions

**File:** `snippets/adhd-micro-transactions.md`
**Domain:** ADHD Management / UX Design
**Token estimate:** ~350 tokens

---

## The Principle

ADHD brains are wired for **micro-transactions** — small, immediate, rewarding feedback loops. This is why YouTube Shorts, TikTok, and notification badges work: each one is a tiny dopamine hit that costs almost nothing to engage with.

The same principle must be applied to every interface built for this system.

## What This Means in Practice

**Nothing just appears.** Every element on screen must *arrive* — it pops, slides, fades, draws, bounces, or glows into existence. The arrival itself is the micro-reward. It says: "something happened, and it was for you."

**Interactions must be instant and visible.** When the user does something, the system responds with immediate visual feedback. No loading spinners. No "processing..." text. Movement. Change. Confirmation.

**Chunk everything.** Large blocks of text or data are hostile to ADHD. Break everything into small, digestible pieces. Each piece gets its own moment. Stagger them. Let the eye follow a trail.

**Reduce initiation cost to zero.** The hardest part of ADHD is starting. Every action in the system should require the absolute minimum number of steps. One click. One word. One glance. If it takes two steps, it's one step too many.

## How This Connects to the Animation Library

The `adhd-anim-lib/` folder contains a reusable CSS + JS animation system built on this principle. It provides:

- `pop` — scale from zero with overshoot (reward)
- `fade` — gentle appearance (low-stress)
- `slide-left/right/up` — directional arrival (narrative flow)
- `bounce` — playful drop-in (engagement)
- `draw` — border draws itself (attention)
- `glow` — brief brightness pulse (highlight)
- `typewriter` — text reveals left-to-right (anticipation)
- SVG line drawing — connections animate into place

Every future project should include this library and apply these animations to all UI elements.
