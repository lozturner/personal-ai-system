# GitHub as Session Memory

**File:** `snippets/github-as-session-memory.md`
**Domain:** System Architecture / Session Continuity
**Date:** 2026-02-07
**Token estimate:** ~350 tokens

---

## The Problem

Every AI chat session is amnesiac. When the window closes, the context is gone. The next session starts from zero. The user re-explains their life, their project, their preferences, their frustrations — and the AI confidently generates a fresh plan that ignores everything that came before.

## The Solution

The GitHub repository **is** the persistent memory. It is the single source of truth that survives between sessions. Any new chat — with any LLM, on any platform — starts by reading this repo and gets the full picture:

- What the project is and why it exists (`personal_ai_vision.md`)
- What design principles govern the system (`snippets/`)
- What has already been built (`whiteboard.html`, `adhd-anim-lib/`)
- What went wrong and what was learned (`snippets/friction-log-*.md`)

## How It Works

1. **New session opens.** User points the AI at `github.com/lozturner/personal-ai-system`.
2. **AI reads the repo.** It pulls in the vision doc, the snippets, the file structure.
3. **Context is restored.** The AI understands the project, the user's needs, and the design constraints without the user repeating anything.
4. **Work continues.** New outputs are committed back to the repo before the session ends.
5. **Nothing is lost.** The repo grows. The system remembers.

## Rules

- Every session must commit its outputs back to the repo before closing.
- The repo structure must remain readable by any LLM — plain text, Markdown, small files.
- No file in the repo should exceed the 60% token budget rule (see `snippets/60-percent-token-budget.md`).
- The repo is the memory. If it's not in the repo, it didn't happen.
