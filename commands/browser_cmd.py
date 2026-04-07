"""
Browser command for VEGA AI Assistant.

Opens websites dynamically — supports common sites by name
and arbitrary URLs.
"""

import webbrowser

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

# Common site shortcuts — easily extensible
SITE_MAP = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "gmail": "https://mail.google.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "linkedin": "https://www.linkedin.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "whatsapp web": "https://web.whatsapp.com",
    "chatgpt": "https://chat.openai.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "classroom": "https://classroom.google.com",
}


class BrowserCommand(BaseCommand):
    """Open websites in the default browser."""

    priority = 15  # High priority for "open ..." commands

    @property
    def triggers(self) -> list[str]:
        return ["open"]

    def match(self, query: str) -> bool:
        """Match 'open <something>' but not 'open <application>' system commands."""
        if not query.strip().startswith("open"):
            return False
        # Delegate to system_cmd if it looks like an app
        site_name = query.replace("open", "").strip()
        # Check if it's a known website or contains a dot (URL)
        return (
            site_name in SITE_MAP
            or "." in site_name
            or site_name.endswith(".com")
            or site_name.endswith(".in")
            or site_name.endswith(".org")
        )

    def execute(self, query: str, assistant) -> None:
        site_name = query.replace("open", "").strip()

        # Check known sites
        if site_name in SITE_MAP:
            url = SITE_MAP[site_name]
            assistant.speech.speak(f"Opening {site_name}.")
            logger.info("Opening website: %s -> %s", site_name, url)
            webbrowser.open(url)
            return

        # Try as a direct URL
        if "." in site_name:
            url = site_name if site_name.startswith("http") else f"https://{site_name}"
            assistant.speech.speak(f"Opening {site_name}.")
            logger.info("Opening URL: %s", url)
            webbrowser.open(url)
            return

        assistant.speech.speak(
            f"I'm not sure which website '{site_name}' is. "
            "Could you try again with a more specific name?"
        )
