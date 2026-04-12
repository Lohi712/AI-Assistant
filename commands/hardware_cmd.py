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
        """Handle volume-related commands using pycaw (with fallback to virtual keys)."""
        volume = self._get_volume_interface()

        if volume is None:
            # pycaw failed — fall back to virtual key simulation
            self._handle_volume_via_keys(query, assistant)
            return

        try:
            current = volume.GetMasterVolumeLevelScalar()   # 0.0 → 1.0
            current_pct = int(current * 100)

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

    @staticmethod
    def _get_volume_interface():
        """
        Get the Windows IAudioEndpointVolume interface.

        Tries three methods to handle different pycaw versions:
          1. New pycaw (0.5+): AudioDevice._dev.Activate()
          2. Old pycaw (<0.5):  device.Activate() directly
          3. Returns None if pycaw is unavailable (triggers key fallback)
        """
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()

            # Try new pycaw API first (AudioDevice wrapper object)
            try:
                interface = devices._dev.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )
            except AttributeError:
                # Fall back to old pycaw API (raw COM interface)
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                )

            return cast(interface, POINTER(IAudioEndpointVolume))

        except ImportError:
            logger.warning("pycaw not installed — using virtual key fallback.")
            return None
        except Exception as e:
            logger.error("Volume interface error: %s", e)
            return None

    @staticmethod
    def _handle_volume_via_keys(query: str, assistant) -> None:
        """
        Fallback volume control using Windows virtual key codes.
        Works without pycaw — simulates the keyboard media keys.
        Cannot report exact percentage.
        """
        import ctypes
        KEYEVENTF_EXTENDEDKEY = 0x0001
        KEYEVENTF_KEYUP       = 0x0002
        VK_VOLUME_UP          = 0xAF
        VK_VOLUME_DOWN        = 0xAE
        VK_VOLUME_MUTE        = 0xAD

        def press_key(vk):
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

        steps = 3  # Each press = ~2% volume change

        if "mute" in query:
            press_key(VK_VOLUME_MUTE)
            assistant.speech.speak("Toggling mute.")
        elif any(w in query for w in ("up", "increase", "raise", "higher")):
            for _ in range(steps):
                press_key(VK_VOLUME_UP)
            assistant.speech.speak("Volume increased.")
            logger.info("Volume increased via virtual keys.")
        elif any(w in query for w in ("down", "decrease", "lower", "reduce")):
            for _ in range(steps):
                press_key(VK_VOLUME_DOWN)
            assistant.speech.speak("Volume decreased.")
            logger.info("Volume decreased via virtual keys.")
        else:
            assistant.speech.speak("I'm not sure what volume action you want.")

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
