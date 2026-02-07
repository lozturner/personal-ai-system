# The 60% Token Budget Rule

**File:** `snippets/60-percent-token-budget.md`
**Domain:** System Architecture / LLM Constraints
**Date:** 2026-02-07
**Token estimate:** ~400 tokens

---

## The Rule

No single LLM request should consume more than **60% of the model's context window** with system context, project files, and background information. The remaining 40% must be reserved for the actual conversation, reasoning, and output generation.

## Why 60%

LLMs degrade predictably when context is overloaded:

- **Lost in the middle.** Research shows that LLMs attend strongly to the beginning and end of their context window but lose track of information in the middle. Stuffing the context to capacity guarantees that critical details will be ignored.
- **Hallucination increases.** As the context fills, the model becomes more likely to fabricate information rather than admit it cannot find what it needs in the noise.
- **Output quality drops.** With less room to reason, the model produces shallower, more generic responses. The exact opposite of what this system needs.

60% is the ceiling, not the target. Less is better. The system should pull in only the snippets relevant to the current task, not the entire repo.

## How This Applies

| Context Window Size | 60% Budget | Reserved for Conversation |
|---|---|---|
| 4K tokens (GPT-3.5 era) | 2,400 tokens | 1,600 tokens |
| 8K tokens | 4,800 tokens | 3,200 tokens |
| 32K tokens | 19,200 tokens | 12,800 tokens |
| 128K tokens | 76,800 tokens | 51,200 tokens |
| 200K tokens | 120,000 tokens | 80,000 tokens |

## Implications for Snippet Design

- Each snippet file must include a **token estimate** in its header so the system can budget before sending.
- Snippets must be **modular and self-contained** — the system selects only what's relevant, not everything.
- If a snippet exceeds ~2,000 tokens, it should be split into smaller files.
- The system must track cumulative token usage per request and refuse to add more context once the 60% threshold is reached.

## The Principle

The context window is not storage. It is working memory. Treat it like a desk, not a filing cabinet. Only put on the desk what you need for the task at hand.
