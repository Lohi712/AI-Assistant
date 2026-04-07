"""
Web search command for VEGA AI Assistant.

Uses DuckDuckGo for privacy-friendly web search, then
optionally summarizes results using the AI engine.
"""

import webbrowser

from ddgs import DDGS

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchCommand(BaseCommand):
    """Search the web using DuckDuckGo and summarize results."""

    priority = 40  # Lower priority — 'search' is a common word

    @property
    def triggers(self) -> list[str]:
        return ["search"]

    def match(self, query: str) -> bool:
        # Avoid matching when "search" is part of "wikipedia search"
        if "wikipedia" in query:
            return False
        return super().match(query)

    def execute(self, query: str, assistant) -> None:
        search_term = query.replace("search", "").strip()

        if not search_term:
            assistant.speech.speak("What would you like to search for?")
            search_term = assistant.speech.listen().lower()
            if search_term in ("none", ""):
                return

        assistant.speech.speak(f"Searching the web for {search_term}.")

        first_url = None  # Track for fallback opening
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(search_term, max_results=3))

            if not results:
                assistant.speech.speak("Sorry, I couldn't find any results.")
                return

            first = results[0]
            page_title = first.get("title", "")
            summary = first.get("body", "")
            first_url = first.get("href", "")

            assistant.speech.speak(f"The top result is: {page_title}")
            print(f"\n🔍 {page_title}")
            print(f"   {summary}")
            print(f"   🔗 {first_url}\n")

            # Use AI to provide a better summary if available
            if assistant.ai and summary:
                ai_summary = assistant.ai.ask(
                    f"Summarize this in 2-3 sentences for speaking aloud: {summary}"
                )
                assistant.speech.speak(ai_summary)
            else:
                assistant.speech.speak(summary)

            assistant.speech.speak("Opening the page for you now.")
            webbrowser.open(first_url)

        except Exception as e:
            logger.error("Web search error: %s", e)
            assistant.speech.speak("I had trouble searching the web.")
            if first_url:
                webbrowser.open(first_url)
