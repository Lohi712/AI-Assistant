"""
Hardware control command for VEGA AI Assistant.

Controls system volume and screen brightness — bringing
Google Assistant-level hardware control to the laptop.

Volume uses Windows virtual key simulation (100% reliable, no COM crashes).
Brightness uses screen-brightness-control library.
"""

import ctypes
import re
import time

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Windows Virtual Key constants ────────────────────────────────
VK_VOLUME_UP   = 0xAF
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_MUTE = 0xAD
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002

_user32 = ctypes.windll.user32


def _press_key(vk: int) -> None:
    """Simulate a single key press + release."""
    _user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
    _user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


class HardwareCommand(BaseCommand):
    """Control volume and screen brightness."""

    priority = 15

    @property
    def triggers(self) -> list[str]:
        return [
            "volume", "volume up", "volume down", "mute", "unmute",
            "brightness", "brightness up", "brightness down",
            "increase volume", "decrease volume",
            "increase brightness", "decrease brightness",
            "set volume", "set brightness",
            "make volume", "max volume", "full volume",
            "louder", "softer", "quieter",
        ]

    def execute(self, query: str, assistant) -> None:
        if "volume" in query or "mute" in query or "louder" in query or "softer" in query or "quieter" in query:
            self._handle_volume(query, assistant)
        elif "brightness" in query:
            self._handle_brightness(query, assistant)

    # ── Volume Control (via Windows Virtual Keys) ────────────────

    def _handle_volume(self, query: str, assistant) -> None:
        """
        Handle volume commands using Windows media key simulation.

        Each virtual key press changes volume by ~2%.
        This approach uses zero COM objects — no pycaw, no crashes.
        """

        # ── Mute / Unmute ──
        if "unmute" in query:
            _press_key(VK_VOLUME_MUTE)  # Toggles mute
            assistant.speech.speak("Volume unmuted.")
            logger.info("Volume unmuted via virtual key.")
            return
        if "mute" in query:
            _press_key(VK_VOLUME_MUTE)  # Toggles mute
            assistant.speech.speak("Volume muted.")
            logger.info("Volume muted via virtual key.")
            return

        # ── Set to specific percentage ──
        specific = self._extract_number(query)
        if specific is not None:
            level = max(0, min(100, specific))
            # Strategy: mute → set to 0 → press UP (level/2) times
            # Each key press = 2% volume change
            steps = level // 2

            # First, set volume to 0 by pressing DOWN 50 times (guaranteed)
            for _ in range(50):
                _press_key(VK_VOLUME_DOWN)
                time.sleep(0.01)

            # Then press UP to reach the desired level
            for _ in range(steps):
                _press_key(VK_VOLUME_UP)
                time.sleep(0.01)

            assistant.speech.speak(f"Volume set to approximately {level} percent.")
            logger.info("Volume set to ~%d%% via virtual keys.", level)
            return

        # ── Max / Full ──
        if any(w in query for w in ("max", "full", "maximum")):
            for _ in range(50):
                _press_key(VK_VOLUME_UP)
                time.sleep(0.01)
            assistant.speech.speak("Volume set to maximum.")
            logger.info("Volume set to max via virtual keys.")
            return

        # ── Increase ──
        if any(w in query for w in ("up", "increase", "raise", "higher", "more", "louder", "make")):
            for _ in range(5):  # ~10% increase
                _press_key(VK_VOLUME_UP)
                time.sleep(0.01)
            assistant.speech.speak("Volume increased.")
            logger.info("Volume increased via virtual keys.")
            return

        # ── Decrease ──
        if any(w in query for w in ("down", "decrease", "lower", "reduce", "less", "softer", "quieter")):
            for _ in range(5):  # ~10% decrease
                _press_key(VK_VOLUME_DOWN)
                time.sleep(0.01)
            assistant.speech.speak("Volume decreased.")
            logger.info("Volume decreased via virtual keys.")
            return

        # ── Just "volume" — tell the user we can't report exact level ──
        assistant.speech.speak(
            "I can increase, decrease, mute, or set the volume to a specific level. "
            "What would you like me to do?"
        )

    # ── Brightness Control ──────────────────────────────────────

    def _handle_brightness(self, query: str, assistant) -> None:
        """Handle brightness commands using screen-brightness-control."""
        try:
            import screen_brightness_control as sbc
        except ImportError:
            logger.error("screen-brightness-control not installed.")
            assistant.speech.speak(
                "Brightness control requires screen-brightness-control. "
                "Please install it with: pip install screen-brightness-control"
            )
            return

        try:
            current = sbc.get_brightness(display=0)
            if isinstance(current, list):
                current = current[0]

            # ── Set to specific percentage ──
            specific = self._extract_number(query)
            if specific is not None:
                level = max(0, min(100, specific))
                sbc.set_brightness(level, display=0)
                assistant.speech.speak(f"Brightness set to {level} percent.")
                logger.info("Brightness set to %d%%", level)
                return

            # ── Increase / Decrease ──
            if any(w in query for w in ("up", "increase", "raise", "higher", "more")):
                new = min(100, current + 10)
                sbc.set_brightness(new, display=0)
                assistant.speech.speak(f"Brightness increased to {new} percent.")
                logger.info("Brightness: %d%% -> %d%%", current, new)
                return

            if any(w in query for w in ("down", "decrease", "lower", "reduce", "less")):
                new = max(0, current - 10)
                sbc.set_brightness(new, display=0)
                assistant.speech.speak(f"Brightness decreased to {new} percent.")
                logger.info("Brightness: %d%% -> %d%%", current, new)
                return

            # ── Just "brightness" — report current level ──
            assistant.speech.speak(f"Brightness is currently at {current} percent.")

        except Exception as e:
            logger.error("Brightness control error: %s", e)
            assistant.speech.speak("Sorry, I had trouble adjusting the brightness.")

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_number(text: str) -> int | None:
        """Extract a number from text, e.g., 'set volume to 50' -> 50."""
        numbers = re.findall(r"\d+", text)
        if numbers:
            return int(numbers[0])
        return None
