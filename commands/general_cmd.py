"""
General / Fallback command for VEGA AI Assistant.

Handles any query that doesn't match a specific command
by forwarding it to the AI conversation engine.
"""

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


class GeneralCommand(BaseCommand):
    """
    Fallback command that sends unmatched queries to Gemini AI.

    This has the lowest priority, so it only activates when
    no other command matches.
    """

    priority = 100  # Always last

    @property
    def triggers(self) -> list[str]:
        return []  # Matches everything via custom match()

    def match(self, query: str) -> bool:
        """Always match — this is the catch-all fallback."""
        return bool(query and query != "none")

    def execute(self, query: str, assistant) -> None:
        assistant.speech.speak("Let me think about that.")

        response = assistant.ai.ask(query)

        if response:
            print(f"\n🤖 VEGA: {response}\n")
            assistant.speech.speak(response)
        else:
            assistant.speech.speak("Sorry, I couldn't come up with an answer.")
