"""
Brain — Claude API integration.

Maintains conversation context within a call.
Sends user speech to Claude and returns the response.
"""

import logging
import time
from typing import Optional

import anthropic

from voice_dispatch.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    SYSTEM_PROMPT,
    MAX_CONVERSATION_TURNS,
)

logger = logging.getLogger("dispatch.brain")


class Brain:
    """Claude-powered conversation engine."""

    def __init__(self):
        self.client: Optional[anthropic.Anthropic] = None
        self.conversation: list[dict] = []
        self._loaded = False

    def load(self):
        """Initialize the Anthropic client."""
        if self._loaded:
            return
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. "
                "Set it in your .env file or environment variables."
            )
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._loaded = True
        logger.info(f"Brain loaded (model: {CLAUDE_MODEL})")

    def reset_conversation(self):
        """Clear conversation history (new call)."""
        self.conversation.clear()

    def think(self, user_text: str) -> str:
        """Send user text to Claude, return response.

        Maintains full conversation context within the call.
        Trims old turns if we exceed MAX_CONVERSATION_TURNS.
        """
        if not self._loaded:
            self.load()

        self.conversation.append({
            "role": "user",
            "content": user_text,
        })

        # Trim if too long (keep first + last N turns)
        if len(self.conversation) > MAX_CONVERSATION_TURNS:
            # Keep first 2 and last MAX-2 turns
            keep = MAX_CONVERSATION_TURNS - 2
            self.conversation = self.conversation[:2] + self.conversation[-keep:]

        start = time.time()
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=300,  # Keep responses phone-call-brief
                system=SYSTEM_PROMPT,
                messages=self.conversation,
            )

            assistant_text = response.content[0].text
            elapsed = time.time() - start

            self.conversation.append({
                "role": "assistant",
                "content": assistant_text,
            })

            logger.info(f"Claude responded ({elapsed:.1f}s): '{assistant_text[:80]}...'")
            return assistant_text

        except anthropic.APIError as e:
            elapsed = time.time() - start
            logger.error(f"Claude API error ({elapsed:.1f}s): {e}")
            # Remove the failed user message
            self.conversation.pop()
            return "I had trouble processing that. Could you say it again?"

        except Exception as e:
            logger.error(f"Unexpected error calling Claude: {e}")
            self.conversation.pop()
            return "Something went wrong on my end. Try again."

    def get_summary(self) -> str:
        """Get a summary of the conversation (for cross-call memory)."""
        if not self.conversation:
            return "No conversation yet."

        if not self._loaded:
            return "Brain not loaded."

        try:
            summary_response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=200,
                system="Summarize this phone conversation in 2-3 bullet points. Be concise.",
                messages=[{
                    "role": "user",
                    "content": "\n".join(
                        f"{m['role']}: {m['content']}" for m in self.conversation
                    ),
                }],
            )
            return summary_response.content[0].text
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return "Summary unavailable."
