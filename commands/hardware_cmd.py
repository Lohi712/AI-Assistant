"""
Hardware control command for VEGA AI Assistant.

Controls system volume and screen brightness — bringing
Google Assistant-level hardware control to the laptop.
"""

import re

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


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
        ]

    def execute(self, query: str, assistant) -> None:
        if "volume" in query or "mute" in query:
            self._handle_volume(query, assistant)
        elif "brightness" in query:
            self._handle_brightness(query, assistant)

    # ── Volume Control ──────────────────────────────────────────

    def _handle_volume(self, query: str, assistant) -> None:
        """Handle volume-related commands using pycaw."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            current = volume.GetMasterVolumeLevelScalar()  # 0.0 to 1.0
            current_pct = int(current * 100)

        except ImportError:
            logger.error("pycaw or comtypes not installed.")
            assistant.speech.speak(
                "Volume control requires pycaw. "
                "Please install it with: pip install pycaw comtypes"
            )
            return
        except Exception as e:
            logger.error("Volume initialization error: %s", e)
            assistant.speech.speak("Sorry, I couldn't access volume controls.")
            return

        try:
            # ── Mute / Unmute ──
            if "unmute" in query:
                volume.SetMute(0, None)
                assistant.speech.speak("Volume unmuted.")
                logger.info("Volume unmuted.")
                return
            if "mute" in query:
                volume.SetMute(1, None)
                assistant.speech.speak("Volume muted.")
                logger.info("Volume muted.")
                return

            # ── Set to specific percentage ──
            specific = self._extract_number(query)
            if specific is not None:
                level = max(0, min(100, specific)) / 100.0
                volume.SetMasterVolumeLevelScalar(level, None)
                assistant.speech.speak(f"Volume set to {int(level * 100)} percent.")
                logger.info("Volume set to %d%%", int(level * 100))
                return

            # ── Increase / Decrease ──
            if any(w in query for w in ("up", "increase", "raise", "higher")):
                new = min(1.0, current + 0.10)
                volume.SetMasterVolumeLevelScalar(new, None)
                assistant.speech.speak(f"Volume increased to {int(new * 100)} percent.")
                logger.info("Volume: %d%% -> %d%%", current_pct, int(new * 100))
                return

            if any(w in query for w in ("down", "decrease", "lower", "reduce")):
                new = max(0.0, current - 0.10)
                volume.SetMasterVolumeLevelScalar(new, None)
                assistant.speech.speak(f"Volume decreased to {int(new * 100)} percent.")
                logger.info("Volume: %d%% -> %d%%", current_pct, int(new * 100))
                return

            # ── Just "volume" — report current level ──
            assistant.speech.speak(f"Volume is currently at {current_pct} percent.")

        except Exception as e:
            logger.error("Volume control error: %s", e)
            assistant.speech.speak("Sorry, I had trouble adjusting the volume.")

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
            if any(w in query for w in ("up", "increase", "raise", "higher")):
                new = min(100, current + 10)
                sbc.set_brightness(new, display=0)
                assistant.speech.speak(f"Brightness increased to {new} percent.")
                logger.info("Brightness: %d%% -> %d%%", current, new)
                return

            if any(w in query for w in ("down", "decrease", "lower", "reduce")):
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
        # Using word-to-number for common spoken numbers too
        numbers = re.findall(r"\d+", text)
        if numbers:
            return int(numbers[0])
        return None
