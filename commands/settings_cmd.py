"""
System settings and customization command for VEGA AI Assistant.

Controls Windows appearance (dark/light mode, wallpaper),
display (night light), power plans, and focus/DND mode.

Uses winreg for registry modifications, ctypes for Windows API,
and subprocess for PowerShell/system commands.
"""

import ctypes
import os
import subprocess
import winreg

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Windows API constants ────────────────────────────────────────
SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02

# ── Power plan GUIDs ────────────────────────────────────────────
POWER_PLANS = {
    "balanced":         "381b4222-f694-41f0-9685-ff5bb260df2e",
    "high performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
    "power saver":      "a1841308-3541-4fab-bc81-f71556f20b4a",
}

# Aliases for more natural commands
POWER_ALIASES = {
    "gaming mode": "high performance",
    "gaming": "high performance",
    "performance": "high performance",
    "performance mode": "high performance",
    "saver": "power saver",
    "save power": "power saver",
    "battery saver": "power saver",
    "balance": "balanced",
    "normal": "balanced",
    "normal mode": "balanced",
}

# ── Theme registry path ─────────────────────────────────────────
THEME_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


class SettingsCommand(BaseCommand):
    """
    Controls system settings: theme, wallpaper, night light,
    power plan, and Do Not Disturb mode.
    """

    priority = 12

    def __init__(self):
        super().__init__()
        self.last_target = None  # "theme", "wallpaper", "night_light", "power", "dnd"

    @property
    def triggers(self) -> list[str]:
        return [
            # Theme
            "dark mode", "light mode", "dark theme", "light theme",
            "switch to dark", "switch to light",
            "enable dark", "enable light",
            "turn on dark", "turn on light",
            # Wallpaper
            "change wallpaper", "set wallpaper", "change background",
            "change desktop background", "new wallpaper",
            # Night light
            "night light", "blue light", "blue light filter",
            "warm light", "eye protection",
            "night light strength", "night light intensity",
            "night light warmth", "set night light",
            # Power plan
            "power saver", "high performance", "balanced mode",
            "gaming mode", "power plan", "performance mode",
            "battery saver", "save power",
            # DND / Focus
            "do not disturb", "focus mode", "focus assist",
            "dnd", "quiet mode",
        ]

    def match_followup(self, query: str) -> bool:
        """Match follow-ups like 'turn it on', 'increase it', 'change it'."""
        followup_words = [
            "on", "off", "enable", "disable", "turn on", "turn off",
            "increase", "decrease", "change", "switch", "toggle",
        ]
        return any(word in query for word in followup_words)

    def execute(self, query: str, assistant) -> None:
        # ── Dark/Light mode ──
        if any(t in query for t in ("dark mode", "dark theme", "switch to dark",
                                     "enable dark", "turn on dark")):
            self.last_target = "theme"
            self._set_theme(dark=True, assistant=assistant)
            return

        if any(t in query for t in ("light mode", "light theme", "switch to light",
                                     "enable light", "turn on light")):
            self.last_target = "theme"
            self._set_theme(dark=False, assistant=assistant)
            return

        # ── Wallpaper ──
        if any(t in query for t in ("wallpaper", "desktop background")):
            self.last_target = "wallpaper"
            self._change_wallpaper(assistant)
            return

        # ── Night light ──
        if any(t in query for t in ("night light", "blue light", "warm light", "eye protection")):
            self.last_target = "night_light"
            # Check if user wants to set strength/intensity
            import re
            has_number = re.search(r'\b(\d+)\b', query)
            is_strength = any(w in query for w in ("strength", "intensity", "warmth", "level"))

            if has_number and (is_strength or "set" in query):
                value = int(has_number.group(1))
                self._set_night_light_strength(value, assistant)
            elif is_strength and not has_number:
                # They said "strength" but no number — ask for it
                assistant.speech.speak("What strength level? Say a number from 0 to 100.")
                response = assistant.speech.listen()
                if not response:
                    response = "none"
                response = response.strip()
                num_match = re.search(r'\b(\d+)\b', response)
                if num_match:
                    self._set_night_light_strength(int(num_match.group(1)), assistant)
                else:
                    assistant.speech.speak("Sorry, I didn't catch a number.")
            else:
                self._toggle_night_light(query, assistant)
            return

        # ── Power plan ──
        if any(t in query for t in ("power saver", "high performance", "balanced",
                                     "gaming mode", "power plan", "performance mode",
                                     "battery saver", "save power", "normal mode")):
            self.last_target = "power"
            self._set_power_plan(query, assistant)
            return

        # ── Do Not Disturb ──
        if any(t in query for t in ("do not disturb", "focus mode", "focus assist",
                                     "dnd", "quiet mode")):
            self.last_target = "dnd"
            self._toggle_dnd(query, assistant)
            return

        # ── Context follow-up: route based on last_target ──
        if self.last_target == "night_light":
            self._toggle_night_light(query, assistant)
            return
        if self.last_target == "theme":
            if any(w in query for w in ("dark", "on", "enable")):
                self._set_theme(dark=True, assistant=assistant)
            else:
                self._set_theme(dark=False, assistant=assistant)
            return
        if self.last_target == "dnd":
            self._toggle_dnd(query, assistant)
            return

    # ── Theme (Dark / Light Mode) ─────────────────────────────────

    def _set_theme(self, dark: bool, assistant) -> None:
        """Toggle dark or light mode via registry."""
        value = 0 if dark else 1
        mode_name = "dark" if dark else "light"

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, THEME_REG_PATH,
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
            winreg.CloseKey(key)

            # Broadcast setting change for immediate refresh
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                "ImmersiveColorSet", 0, 1000, None
            )

            assistant.speech.speak(f"Switched to {mode_name} mode.")
            logger.info("Theme set to %s mode.", mode_name)
            print(f"🎨 Theme: {mode_name.capitalize()} mode activated")

        except Exception as e:
            logger.error("Theme change error: %s", e)
            assistant.speech.speak(f"Sorry, I couldn't switch to {mode_name} mode.")

    # ── Wallpaper ─────────────────────────────────────────────────

    def _change_wallpaper(self, assistant) -> None:
        """Change the desktop wallpaper."""
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        wallpapers_dir = os.path.join(pictures_dir, "Wallpapers")

        # Check if Wallpapers folder exists with images
        if os.path.isdir(wallpapers_dir):
            images = [
                f for f in os.listdir(wallpapers_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
            ]
            if images:
                # Cycle to next wallpaper
                current = self._get_current_wallpaper()
                current_name = os.path.basename(current) if current else ""

                # Find next image after current
                try:
                    idx = images.index(current_name)
                    next_idx = (idx + 1) % len(images)
                except ValueError:
                    next_idx = 0

                image_path = os.path.join(wallpapers_dir, images[next_idx])
                self._apply_wallpaper(image_path, assistant)
                return

        # No wallpapers folder — ask user for path
        assistant.speech.speak(
            "I don't have a wallpapers folder set up. "
            "You can create a 'Wallpapers' folder in your Pictures directory "
            "and add images there. Or tell me the full path to an image."
        )
        user_input = assistant.speech.listen()
        if not user_input:
            user_input = "none"
        user_input = user_input.strip()
        if user_input.lower() in ("none", ""):
            return

        if os.path.isfile(user_input):
            self._apply_wallpaper(user_input, assistant)
        else:
            assistant.speech.speak("I couldn't find that image file.")

    def _apply_wallpaper(self, image_path: str, assistant) -> None:
        """Apply a wallpaper image."""
        try:
            abs_path = os.path.abspath(image_path)
            result = ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, abs_path,
                SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
            )
            if result:
                assistant.speech.speak(f"Wallpaper changed to {os.path.basename(image_path)}.")
                logger.info("Wallpaper set: %s", abs_path)
                print(f"🖼️  Wallpaper: {abs_path}")
            else:
                assistant.speech.speak("The wallpaper change didn't seem to work.")
        except Exception as e:
            logger.error("Wallpaper error: %s", e)
            assistant.speech.speak("Sorry, I couldn't change the wallpaper.")

    @staticmethod
    def _get_current_wallpaper() -> str:
        """Get the current wallpaper path from registry."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\Desktop", 0, winreg.KEY_READ
            )
            value, _ = winreg.QueryValueEx(key, "WallPaper")
            winreg.CloseKey(key)
            return value
        except Exception:
            return ""

    # ── Night Light ───────────────────────────────────────────────

    def _toggle_night_light(self, query: str, assistant) -> None:
        """
        Toggle night light automatically using PowerShell UI Automation.

        Runs scripts/toggle_nightlight.ps1 which:
         1. Opens ms-settings:nightlight
         2. Finds the "Turn on now" / "Turn off now" button by AutomationId
         3. Clicks it via InvokePattern (100% reliable, no Tab/Space guessing)
         4. Closes only the Settings app
        """
        turning_on = any(w in query for w in ("on", "enable", "turn on", "start"))
        turning_off = any(w in query for w in ("off", "disable", "turn off", "stop"))

        action = "off" if turning_off else "on" if turning_on else "toggle"

        assistant.speech.speak(f"Turning night light {action}. Please wait.")

        # Locate the PowerShell script (relative to this file)
        script_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts"
        )
        script_path = os.path.join(script_dir, "toggle_nightlight.ps1")

        if not os.path.isfile(script_path):
            logger.error("Night light script not found: %s", script_path)
            assistant.speech.speak(
                "Night light automation script is missing. "
                "Opening settings for you instead."
            )
            os.startfile("ms-settings:nightlight")
            return

        try:
            result = subprocess.run(
                [
                    "powershell", "-ExecutionPolicy", "Bypass",
                    "-NoProfile", "-File", script_path,
                ],
                capture_output=True, text=True, timeout=20,
            )
            output = result.stdout.strip()
            logger.debug("Night light script output: %s", output)

            if "SUCCESS" in output:
                assistant.speech.speak(f"Night light turned {action}.")
                logger.info("Night light toggled: %s", action)
                print(f"🌙 Night Light: {action.upper()}")
            elif "NO_TOGGLE" in output:
                logger.warning("Night light: toggle button not found.")
                assistant.speech.speak(
                    "I couldn't find the night light button. "
                    "I'll leave the settings open for you."
                )
                os.startfile("ms-settings:nightlight")
            elif "NO_WINDOW" in output:
                logger.warning("Night light: Settings window not found.")
                assistant.speech.speak(
                    "I couldn't open the settings window. Let me try again."
                )
                os.startfile("ms-settings:nightlight")
            else:
                logger.warning("Night light: unexpected output: %s", output)
                assistant.speech.speak(
                    f"Night light might have been toggled. Please check."
                )

        except subprocess.TimeoutExpired:
            logger.error("Night light script timed out.")
            assistant.speech.speak(
                "The night light toggle took too long. Please try again."
            )
            self._close_settings_app()
        except Exception as e:
            logger.error("Night light toggle error: %s", e)
            assistant.speech.speak(
                "Sorry, I had trouble toggling the night light. "
                "Let me open the settings for you."
            )
            try:
                os.startfile("ms-settings:nightlight")
            except Exception:
                pass

    @staticmethod
    def _focus_settings_window() -> None:
        """Bring the Windows Settings window to the foreground."""
        try:
            # Find the Settings window by class name
            hwnd = ctypes.windll.user32.FindWindowW(
                "ApplicationFrameWindow", None
            )
            if hwnd:
                # Try to bring it to front
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    @staticmethod
    def _close_settings_app() -> None:
        """Close only the Windows Settings app (SystemSettings.exe)."""
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", "SystemSettings.exe"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

    # ── Night Light Strength ──────────────────────────────────────

    def _set_night_light_strength(self, value: int, assistant) -> None:
        """
        Set night light strength (0-100) using PowerShell UI Automation.

        Runs scripts/set_nightlight_strength.ps1 which finds the
        "Strength" slider by AutomationId and sets its value.
        """
        # Clamp to valid range
        value = max(0, min(100, value))

        assistant.speech.speak(
            f"Setting night light strength to {value} percent. Please wait."
        )

        script_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts"
        )
        script_path = os.path.join(script_dir, "set_nightlight_strength.ps1")

        if not os.path.isfile(script_path):
            logger.error("Night light strength script not found: %s", script_path)
            assistant.speech.speak(
                "Night light strength script is missing. "
                "Opening settings for you instead."
            )
            os.startfile("ms-settings:nightlight")
            return

        try:
            result = subprocess.run(
                [
                    "powershell", "-ExecutionPolicy", "Bypass",
                    "-NoProfile", "-File", script_path,
                    "-Value", str(value),
                ],
                capture_output=True, text=True, timeout=20,
            )
            output = result.stdout.strip()
            logger.debug("Night light strength output: %s", output)

            if "SUCCESS" in output:
                assistant.speech.speak(
                    f"Night light strength set to {value} percent."
                )
                logger.info("Night light strength: %d", value)
                print(f"🌙 Night Light strength: {value}%")
            elif "NO_SLIDER" in output:
                assistant.speech.speak(
                    "I couldn't find the strength slider. "
                    "Make sure night light is turned on first."
                )
            else:
                logger.warning("Night light strength: %s", output)
                assistant.speech.speak(
                    "I had trouble setting the strength. Please try again."
                )

        except subprocess.TimeoutExpired:
            logger.error("Night light strength script timed out.")
            assistant.speech.speak("That took too long. Please try again.")
            self._close_settings_app()
        except Exception as e:
            logger.error("Night light strength error: %s", e)
            assistant.speech.speak("Sorry, I couldn't set the night light strength.")

    # ── Power Plan ────────────────────────────────────────────────

    def _set_power_plan(self, query: str, assistant) -> None:
        """Switch the active power plan."""
        # Find which plan the user wants
        plan_name = None
        plan_guid = None

        # Check aliases first
        for alias, real_name in POWER_ALIASES.items():
            if alias in query:
                plan_name = real_name
                plan_guid = POWER_PLANS[real_name]
                break

        # Check direct plan names
        if not plan_name:
            for name, guid in POWER_PLANS.items():
                if name in query:
                    plan_name = name
                    plan_guid = guid
                    break

        if not plan_name:
            # If just "power plan" — show current
            try:
                result = subprocess.run(
                    ["powercfg", "/getactivescheme"],
                    capture_output=True, text=True, shell=True
                )
                assistant.speech.speak(f"Current power plan: {result.stdout.strip()}")
                print(f"⚡ {result.stdout.strip()}")
            except Exception:
                assistant.speech.speak(
                    "I can set the power plan to balanced, high performance, or power saver. "
                    "Which one would you like?"
                )
            return

        try:
            subprocess.run(
                ["powercfg", "/setactive", plan_guid],
                capture_output=True, text=True, shell=True
            )
            assistant.speech.speak(f"Power plan set to {plan_name}.")
            logger.info("Power plan: %s (%s)", plan_name, plan_guid)
            print(f"⚡ Power plan: {plan_name.capitalize()}")
        except Exception as e:
            logger.error("Power plan error: %s", e)
            assistant.speech.speak(f"Sorry, I couldn't change the power plan.")

    # ── Do Not Disturb / Focus Assist ─────────────────────────────

    def _toggle_dnd(self, query: str, assistant) -> None:
        """
        Toggle Do Not Disturb directly via registry.

        Sets NOC_GLOBAL_SETTING_TOASTS_ENABLED:
          0 = DND ON  (notifications suppressed)
          1 = DND OFF (notifications allowed)
        """
        turning_on = any(w in query for w in ("on", "enable", "turn on", "start"))
        turning_off = any(w in query for w in ("off", "disable", "turn off", "stop"))

        DND_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
        DND_VALUE_NAME = "NOC_GLOBAL_SETTING_TOASTS_ENABLED"

        try:
            # If no direction specified, check current state and toggle
            if not turning_on and not turning_off:
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, DND_REG_PATH,
                        0, winreg.KEY_READ
                    )
                    current, _ = winreg.QueryValueEx(key, DND_VALUE_NAME)
                    winreg.CloseKey(key)
                    # Toggle: if toasts enabled (1), turn DND on (set to 0)
                    turning_on = (current == 1)
                    turning_off = (current == 0)
                except FileNotFoundError:
                    turning_on = True  # Default: turn on

            # DND ON = suppress notifications = set value to 0
            # DND OFF = allow notifications = set value to 1
            dnd_value = 0 if turning_on else 1
            dnd_state = "on" if turning_on else "off"

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, DND_REG_PATH,
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, DND_VALUE_NAME, 0, winreg.REG_DWORD, dnd_value)
            winreg.CloseKey(key)

            assistant.speech.speak(f"Do not disturb turned {dnd_state}.")
            logger.info("DND set to %s (value=%d)", dnd_state, dnd_value)
            print(f"🔕 Do Not Disturb: {dnd_state.upper()}")

        except Exception as e:
            logger.error("DND toggle error: %s", e)
            assistant.speech.speak(
                "Sorry, I couldn't toggle Do Not Disturb automatically. "
                "Let me open the settings for you."
            )
            try:
                os.startfile("ms-settings:quiethours")
            except Exception:
                pass
