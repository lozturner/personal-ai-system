# A System That Serves, Not Just Generates

This document is an attempt to capture a specific, articulated frustration and a proposed architectural solution for a more effective personal AI. It is not a final plan, but a starting point for correction, debate, and iterative design. It is intentionally written to reflect the user's stated experience, not to reframe it with optimistic marketing language.

## 1. The Core Failure: The Illusion of Progress

The central problem identified is that while AI systems (as of 2023-2024) are proficient at *generating artifacts*, they have failed to provide *sustained, structured support* for complex, ongoing life challenges. The user has repeatedly engaged with these systems, asking for help with specific, critical life domains, and has received what appear to be solutions: plans, systems, frameworks, and advice. 

However, these solutions are ephemeral and disconnected from the user's actual life context. They are a "Mardi Gras" of potential that never translates into tangible improvement. The core failures can be summarized as:

- **Context Evaporation:** Critical personal context is lost "in the middle" of long interactions or completely absent between sessions. Every conversation effectively starts from zero, forcing the user to re-explain their entire reality repeatedly.
- **Hallucination and Drift:** Over time, the AI's understanding degrades, leading to irrelevant or nonsensical outputs that betray the initial promise.
- **Lack of Persistence:** The generated systems and plans do not live anywhere. They are not integrated into a persistent framework that can track progress, adapt to new information, or provide proactive support. They are static documents, not living systems.
- **The Burden of Implementation:** The AI generates the *what*, but leaves the *how* entirely on the user, who, in this case, is dealing with executive function challenges (ADHD) that make this precise step the primary obstacle.

## 2. The Architectural Proposal: A User-Centric, Persistent System

The proposed solution is a reversal of the current paradigm. Instead of the user's context being a temporary payload for an LLM request, the user's context becomes the permanent, central system.

> "...if we copied the idea of agents and snapshots were just like scattered all over a physical device, or if our system was made first and bits and pieces were pulled in and out of the LLM requests..."

The key architectural principles are:

- **Persistent, Local-First Context:** The user's core information, goals, and history reside on a physical device or a user-controlled system. This is the permanent state.
- **Modular, On-Demand LLM Interaction:** The Large Language Model is a tool that is called upon by the user's system. "Bits and pieces" of the user's context are pulled *out* of the central system and sent to the LLM to perform a specific task. The results are then integrated *back into* the persistent system.
- **Agentic Snapshots:** The idea of "agents and snapshots scattered all over a physical device" suggests a distributed, resilient system where different components or agents manage different aspects of the user's life, all drawing from and updating the same central context.

## 3. Initial Life Domains

The system must be designed to address the following specific, high-stakes areas of the user's life:

- **ADHD Management:** This is not about generic productivity tips. It is about building an external executive function system that can handle the tasks the user struggles with, likely involving proactive reminders, task initiation support, and managing complex workflows.
- **Health Management:** A system to track health issues, appointments, treatments, and data in a structured way.
- **Family & Children:** A system to manage the complexities of co-parenting, schedules, and responsibilities related to the user's children.

## 4. Core Design Principles

Based on the user's explicit instructions, the following principles must guide any development:

- **No Assumptions on UX/UI:** The user interface and user experience must be defined *by the user* after the core architecture is understood. No pre-emptive design decisions should be made.
- **Reverse Engineering from Failure:** The starting point is the user's direct experience of what has *not* worked. The goal is to build a system that directly remedies those specific failures.
- **Conversation as the Interface:** The user still sees a conversational interface as a viable and desirable way to interact with this system, but it must be a conversation with a system that has memory, persistence, and a true understanding of the user's context.
