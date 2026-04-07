"""
Wikipedia search command for VEGA AI Assistant.
"""

import wikipedia

from commands.base import BaseCommand
from utils.logger import get_logger
from utils.text_format import clean_query_words

logger = get_logger(__name__)


class WikipediaCommand(BaseCommand):
    """Search Wikipedia for information on a topic."""

    priority = 20  # Higher priority than generic search

    @property
    def triggers(self) -> list[str]:
        return ["wikipedia"]

    def execute(self, query: str, assistant) -> None:
        assistant.speech.speak("Searching Wikipedia...")

        clean_query = clean_query_words(query)
        logger.info("Wikipedia search: '%s'", clean_query)

        if not clean_query.strip():
            assistant.speech.speak(
                "I heard you say Wikipedia, but I couldn't get the topic. "
                "Please try again."
            )
            return

        try:
            results = wikipedia.summary(clean_query, sentences=2, auto_suggest=True)
            assistant.speech.speak("According to Wikipedia...")
            print(f"\n📖 {results}\n")
            assistant.speech.speak(results)

        except wikipedia.exceptions.DisambiguationError as e:
            assistant.speech.speak(
                f"Your search for {clean_query} is ambiguous. "
                "It could refer to many things."
            )
            logger.info("Disambiguation options: %s", e.options[:5])
            print(f"Disambiguation: {e.options[:5]}")
            assistant.speech.speak("Please be more specific.")

        except wikipedia.exceptions.PageError:
            assistant.speech.speak(
                f"Sorry, I couldn't find a page for {clean_query} on Wikipedia."
            )

        except Exception as e:
            logger.error("Wikipedia error: %s", e)
            assistant.speech.speak(
                "Sorry, an error occurred while searching Wikipedia."
            )
