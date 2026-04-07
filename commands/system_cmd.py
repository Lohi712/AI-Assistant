"""
System commands for VEGA AI Assistant.

Handles application launching, time/date, screenshots,
lock screen, shutdown, restart, and other system operations.
"""

import datetime
import os
import subprocess
import time

import pyautogui

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Known Windows applications ──────────────────────────────────
# Maps spoken names to either executable names (for AppOpener)
# or full paths / shell commands.
APP_MAP = {
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "file explorer": "explorer",
    "explorer": "explorer",
    "files": "explorer",
    "task manager": "taskmgr",
    "command prompt": "cmd",
    "cmd": "cmd",
    "terminal": "wt",                      # Windows Terminal
    "powershell": "powershell",
    "settings": "ms-settings:",            # UWP settings
    "control panel": "control",
    "device manager": "devmgmt.msc",
    "camera": "microsoft.windows.camera:", # UWP camera
    "clock": "ms-clock:",
    "alarm": "ms-clock:",
    "calendar": "outlookcal:",
    "snipping tool": "snippingtool",
    "recorder": "soundrecorder:",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "code": "code",                        # VS Code
    "vs code": "code",
    "visual studio code": "code",
    "chrome": "chrome",
    "brave": "brave",
    "edge": "msedge",
    "firefox": "firefox",
}


class SystemCommand(BaseCommand):
    """
    System-level commands: launch apps, tell time/date,
    take screenshots, lock/sleep/shutdown/restart.
    """

    priority = 10  # High priority for system commands

    @property
    def triggers(self) -> list[str]:
        return [
            "open", "launch", "start",
            "the time", "the date", "what time", "what date",
            "screenshot", "take a screenshot",
            "lock", "lock screen", "lock the computer",
            "shutdown", "shut down", "turn off",
            "restart", "reboot",
            "sleep", "hibernate",
        ]

    def match(self, query: str) -> bool:
        # For "open" commands, only match if it's NOT a known website
        if query.strip().startswith("open"):
            from commands.browser_cmd import SITE_MAP
            site_name = query.replace("open", "").strip()
            # If it's a website, let browser_cmd handle it
            if (
                site_name in SITE_MAP
                or "." in site_name
            ):
                return False
            return True

        return any(trigger in query for trigger in self.triggers if trigger != "open")

    def execute(self, query: str, assistant) -> None:
        # ── Time ──
        if "time" in query:
            now = datetime.datetime.now()
            time_str = now.strftime("%I:%M %p")
            assistant.speech.speak(f"The current time is {time_str}.")
            print(f"🕐 {time_str}")
            return

        # ── Date ──
        if "date" in query:
            now = datetime.datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            assistant.speech.speak(f"Today is {date_str}.")
            print(f"📅 {date_str}")
            return

        # ── Screenshot ──
        if "screenshot" in query:
            self._take_screenshot(assistant)
            return

        # ── Lock Screen ──
        if "lock" in query:
            assistant.speech.speak("Locking the computer.")
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return

        # ── Shutdown ──
        if "shutdown" in query or "shut down" in query or "turn off" in query:
            assistant.speech.speak(
                "Are you sure you want to shut down? Say yes to confirm."
            )
            confirm = assistant.speech.listen().lower()
            if "yes" in confirm:
                assistant.speech.speak("Shutting down in 10 seconds.")
                os.system("shutdown /s /t 10")
            else:
                assistant.speech.speak("Shutdown cancelled.")
            return

        # ── Restart ──
        if "restart" in query or "reboot" in query:
            assistant.speech.speak(
                "Are you sure you want to restart? Say yes to confirm."
            )
            confirm = assistant.speech.listen().lower()
            if "yes" in confirm:
                assistant.speech.speak("Restarting in 10 seconds.")
                os.system("shutdown /r /t 10")
            else:
                assistant.speech.speak("Restart cancelled.")
            return

        # ── Sleep / Hibernate ──
        if "sleep" in query or "hibernate" in query:
            # Don't trigger on "go to sleep" (exit command)
            if "go to sleep" not in query:
                assistant.speech.speak("Putting the computer to sleep.")
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return

        # ── Open Application ──
        if query.startswith("open") or query.startswith("launch") or query.startswith("start"):
            app_name = (
                query.replace("open", "")
                .replace("launch", "")
                .replace("start", "")
                .strip()
            )
            self._open_application(app_name, assistant)
            return

    def _open_application(self, app_name: str, assistant) -> None:
        """
        Open an application by name.

        First checks the APP_MAP for known apps, then tries
        AppOpener as a fallback, then tries Start Menu search.
        """
        if not app_name:
            assistant.speech.speak("What application would you like me to open?")
            app_name = assistant.speech.listen().lower()
            if app_name in ("none", ""):
                return

        # Check known apps
        if app_name in APP_MAP:
            exe = APP_MAP[app_name]
            assistant.speech.speak(f"Opening {app_name}.")
            logger.info("Opening app: %s -> %s", app_name, exe)
            try:
                os.startfile(exe)
            except Exception:
                try:
                    subprocess.Popen(exe, shell=True)
                except Exception as e:
                    logger.error("Failed to open %s: %s", app_name, e)
                    assistant.speech.speak(f"Sorry, I couldn't open {app_name}.")
            return

        # Fallback: try AppOpener
        try:
            from AppOpener import open as app_open
            assistant.speech.speak(f"Opening {app_name}.")
            app_open(app_name, match_closest=True)
            logger.info("Opened via AppOpener: %s", app_name)
            return
        except ImportError:
            logger.warning("AppOpener not installed.")
        except Exception as e:
            logger.warning("AppOpener failed for '%s': %s", app_name, e)

        # Last resort: Start Menu search
        assistant.speech.speak(f"Searching for {app_name} in Start Menu.")
        try:
            pyautogui.press("win")
            time.sleep(0.8)
            pyautogui.write(app_name, interval=0.05)
            time.sleep(1.5)
            pyautogui.press("enter")
        except Exception as e:
            logger.error("Start Menu search failed: %s", e)
            assistant.speech.speak(f"Sorry, I couldn't find {app_name}.")

    @staticmethod
    def _take_screenshot(assistant) -> None:
        """Capture and save a screenshot."""
        try:
            screenshots_dir = os.path.join(os.path.expanduser("~"), "Pictures", "VEGA_Screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")

            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)

            assistant.speech.speak("Screenshot saved!")
            print(f"📸 Screenshot saved to: {filepath}")
            logger.info("Screenshot saved: %s", filepath)

        except Exception as e:
            logger.error("Screenshot error: %s", e)
            assistant.speech.speak("Sorry, I couldn't take a screenshot.")
