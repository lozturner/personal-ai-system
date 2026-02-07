# Friction Log: GitHub Push Permission Failure

**File:** `snippets/friction-log-github-push.md`
**Domain:** System Friction / ADHD Barriers
**Date:** 2026-02-07
**Token estimate:** ~400 tokens

---

## What Happened

During the first real attempt to ship work from the AI system to a permanent location (GitHub), the process broke down at the exact moment it mattered most. The CLI token had read access but not write access. The browser needed a login. The login needed device verification. The device verification needed the user's phone.

The repo was created via the browser. But pushing code to it failed — the token that can *read* repos, *list* repos, and even reports `"push": true` in the API permissions response, cannot actually push. Six files. One commit. Blocked.

## Why This Matters

This is the pattern. This is the entire problem described in `personal_ai_vision.md` playing out in real time:

1. **The AI did the work.** The whiteboard was built, the animation library was written, the snippets were created.
2. **The last mile failed.** Getting the output to a permanent, accessible location required permissions, authentication flows, and manual intervention that the AI could not complete alone.
3. **The burden fell on the user.** The person with ADHD — the person this system is supposed to *help* — had to stop, context-switch, log into GitHub on a browser, verify a device, and hand control back.
4. **Momentum was lost.** The gap between "the work is done" and "the work is saved" is where ADHD kills progress. Every interruption is a risk of abandonment.

## What The System Must Solve

Any personal AI system built for this user must treat **"save and persist the output"** as a first-class, zero-friction operation. Not an afterthought. Not "push to GitHub." The system must own its own persistence layer — local files, synced storage, whatever — so that the output of every interaction is automatically saved without requiring the user to authenticate, approve, or intervene.

The GitHub push failure is Exhibit A.

## Action Items

- The persistent context system must not depend on third-party auth flows for basic save operations.
- Local-first storage is not optional — it is the foundation.
- GitHub/cloud sync should be a background operation that handles its own credentials silently.
- If auth breaks, the work must still be saved locally. Always.
