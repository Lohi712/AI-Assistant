"""
Media playback command for VEGA AI Assistant.

Plays songs/videos on YouTube using pywhatkit.
"""

import pywhatkit

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


class MediaCommand(BaseCommand):
    """Play music or videos on YouTube."""

    priority = 25

    @property
    def triggers(self) -> list[str]:
        return ["play"]

    def match(self, query: str) -> bool:
        # Only match if "play" is at the beginning or preceded by common words
        words = query.split()
        return "play" in words

    def execute(self, query: str, assistant) -> None:
        song = query.replace("play", "").strip()

        if not song:
            assistant.speech.speak("What would you like me to play?")
            song = assistant.speech.listen()
            if song == "None" or not song:
                assistant.speech.speak("I didn't catch what you want to play.")
                return

        assistant.speech.speak(f"Playing {song} on YouTube.")
        logger.info("Playing on YouTube: %s", song)

        try:
            pywhatkit.playonyt(song)
        except Exception as e:
            logger.error("YouTube playback error: %s", e)
            assistant.speech.speak("Sorry, I couldn't play that on YouTube.")
