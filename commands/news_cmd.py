"""
News headlines command for VEGA AI Assistant.

Fetches top headlines from the GNews API.
"""

import requests

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

GNEWS_URL = "https://gnews.io/api/v4/top-headlines"


class NewsCommand(BaseCommand):
    """Fetch and read the latest news headlines."""

    priority = 30

    @property
    def triggers(self) -> list[str]:
        return ["news", "headlines"]

    def execute(self, query: str, assistant) -> None:
        api_key = assistant.settings.gnews_api_key
        if not api_key:
            assistant.speech.speak(
                "News service is not configured. Please set your GNews API key."
            )
            return

        assistant.speech.speak("Fetching the latest news headlines.")

        try:
            response = requests.get(
                GNEWS_URL,
                params={"lang": "en", "country": "in", "token": api_key},
                timeout=10,
            )
            response.raise_for_status()

            articles = response.json().get("articles", [])

            if not articles:
                assistant.speech.speak(
                    "Sorry, I couldn't find any news headlines at the moment."
                )
                return

            assistant.speech.speak("Here are the top headlines:")
            for i, article in enumerate(articles[:5], start=1):
                title = article.get("title", "No title")
                source = article.get("source", {}).get("name", "Unknown")
                description = article.get("description", "")

                print(f"\n📰 Headline {i}: {title}")
                print(f"   Source: {source}")
                if description:
                    print(f"   {description}")

                assistant.speech.speak(f"Headline {i}: {title}")

            assistant.speech.speak("That's all for the top headlines.")

        except requests.RequestException as e:
            logger.error("News API error: %s", e)
            assistant.speech.speak(
                "Sorry, I encountered an error while fetching the news."
            )
