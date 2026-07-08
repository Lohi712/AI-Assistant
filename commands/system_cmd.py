"""
System commands for VEGA AI Assistant.

Handles application launching, time/date, screenshots,
lock screen, shutdown, restart, battery, system info,
clipboard, recycle bin, and other system operations.
"""

import datetime
import os
import platform
import socket
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
    take screenshots, lock/sleep/shutdown/restart,
    battery status, system info, clipboard, recycle bin.
    """

    priority = 10  # High priority for system commands

    @property
    def triggers(self) -> list[str]:
        return [
            "open", "launch", "start",
            "the time", "the date", "what time", "what date",
            "screenshot", "take a screenshot",
            "lock", "lock screen", "lock the computer",
            "shutdown", "shut down", "turn off computer", "turn off pc",
            "restart", "reboot",
            "sleep", "hibernate",
            # Battery
            "battery", "battery status", "battery level",
            "charging", "am i charging", "power status",
            # System info
            "system info", "system information", "about my laptop",
            "my computer", "computer specs", "my system", "system specs",
            # Clipboard
            "clipboard", "clear clipboard", "read clipboard",
            "what's in clipboard", "copy clipboard",
            # Recycle bin
            "recycle bin", "empty recycle", "empty trash",
            "clear recycle", "empty the recycle",
        ]

    def match_followup(self, query: str) -> bool:
        """Match follow-ups like 'open <app>' after a previous system command."""
        followup_words = [
            "open", "launch", "start", "close", "again",
        ]
        return any(word in query for word in followup_words)

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
        # ── Battery ──
        if any(t in query for t in ("battery", "charging", "power status")):
            self._battery_status(assistant)
            return

        # ── System Info ──
        if any(t in query for t in ("system info", "system information", "about my laptop",
                                     "computer specs", "my system", "my computer", "system specs")):
            self._system_info(assistant)
            return

        # ── Clipboard ──
        if "clipboard" in query:
            self._clipboard(query, assistant)
            return

        # ── Recycle Bin ──
        if any(t in query for t in ("recycle bin", "recycle", "empty trash")):
            self._empty_recycle_bin(assistant)
            return

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
        if "shutdown" in query or "shut down" in query or "turn off computer" in query or "turn off pc" in query:
            assistant.speech.speak(
                "Are you sure you want to shut down? Say yes to confirm."
            )
            confirm = assistant.speech.listen()
            if not confirm:
                confirm = "none"
            confirm = confirm.lower()
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
            confirm = assistant.speech.listen()
            if not confirm:
                confirm = "none"
            confirm = confirm.lower()
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
                action = "hibernate" if "hibernate" in query else "sleep"
                assistant.speech.speak(
                    f"Are you sure you want to put the computer to {action}? Say yes to confirm."
                )
                confirm = assistant.speech.listen()
                if not confirm:
                    confirm = "none"
                confirm = confirm.lower()
                if "yes" in confirm:
                    assistant.speech.speak(f"Putting the computer to {action}.")
                    # SetSuspendState parameters: Hibernate (0=sleep, 1=hibernate), Force, DisableWakeEvents
                    state = "1" if action == "hibernate" else "0"
                    os.system(f"rundll32.exe powrprof.dll,SetSuspendState {state},1,0")
                else:
                    assistant.speech.speak(f"{action.capitalize()} cancelled.")
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
            app_name = assistant.speech.listen()
            if not app_name:
                app_name = "none"
            app_name = app_name.lower()
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

    # ── Battery Status ────────────────────────────────────────────

    @staticmethod
    def _battery_status(assistant) -> None:
        """Report battery percentage, charging state, and time remaining."""
        try:
            import psutil
            battery = psutil.sensors_battery()

            if battery is None:
                assistant.speech.speak(
                    "I couldn't detect a battery. This might be a desktop computer."
                )
                return

            percent = battery.percent
            plugged = battery.power_plugged
            secs_left = battery.secsleft

            status = "plugged in and charging" if plugged else "on battery power"

            # Time remaining
            if secs_left == -1 or secs_left == psutil.POWER_TIME_UNLIMITED:
                time_str = ""
            elif secs_left == psutil.POWER_TIME_UNKNOWN:
                time_str = ""
            else:
                hours = secs_left // 3600
                mins = (secs_left % 3600) // 60
                time_str = f" with about {hours} hours and {mins} minutes remaining" if hours > 0 else f" with about {mins} minutes remaining"

            print(f"\n🔋 Battery: {percent}% | {'⚡ Charging' if plugged else '🔌 On battery'}{time_str}\n")

            assistant.speech.speak(
                f"Battery is at {percent} percent, {status}{time_str}."
            )
            logger.info("Battery: %d%%, plugged=%s", percent, plugged)

        except ImportError:
            assistant.speech.speak(
                "Battery monitoring requires psutil. "
                "Please install it with pip install psutil."
            )
        except Exception as e:
            logger.error("Battery check error: %s", e)
            assistant.speech.speak("Sorry, I couldn't check the battery status.")

    # ── System Info ───────────────────────────────────────────────

    @staticmethod
    def _system_info(assistant) -> None:
        """Report comprehensive system information."""
        try:
            import psutil
            import shutil

            # OS info
            os_name = platform.system()
            os_version = platform.version()
            os_release = platform.release()
            machine = platform.machine()
            processor = platform.processor() or "Unknown"
            hostname = socket.gethostname()

            # CPU info
            cpu_count = psutil.cpu_count(logical=True)
            cpu_physical = psutil.cpu_count(logical=False)
            cpu_percent = psutil.cpu_percent(interval=0.5)

            # RAM info
            ram = psutil.virtual_memory()
            ram_total_gb = ram.total / (1024 ** 3)
            ram_used_gb = ram.used / (1024 ** 3)
            ram_free_gb = ram.available / (1024 ** 3)

            # IP address
            try:
                ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                ip = "Unknown"

            info = (
                f"\n💻 System Information:\n"
                f"   ─────────────────────────────────\n"
                f"   Computer:   {hostname}\n"
                f"   OS:         {os_name} {os_release} ({os_version})\n"
                f"   Arch:       {machine}\n"
                f"   Processor:  {processor}\n"
                f"   CPU Cores:  {cpu_physical} physical / {cpu_count} logical\n"
                f"   CPU Usage:  {cpu_percent}%\n"
                f"   RAM:        {ram_used_gb:.1f} GB / {ram_total_gb:.1f} GB ({ram.percent}% used)\n"
                f"   Free RAM:   {ram_free_gb:.1f} GB\n"
                f"   IP Address: {ip}\n"
            )

            # Disk info
            partitions = psutil.disk_partitions()
            for part in partitions:
                try:
                    usage = shutil.disk_usage(part.mountpoint)
                    total_gb = usage.total / (1024 ** 3)
                    free_gb = usage.free / (1024 ** 3)
                    info += f"   Drive {part.mountpoint}  {free_gb:.1f} GB free / {total_gb:.1f} GB total\n"
                except (PermissionError, OSError):
                    continue

            info += "   ─────────────────────────────────\n"
            print(info)

            assistant.speech.speak(
                f"You're running {os_name} {os_release} on a {machine} machine. "
                f"CPU is at {cpu_percent}%, "
                f"RAM is {ram.percent}% used with {ram_free_gb:.1f} gigabytes free. "
                "Check the console for full details."
            )
            logger.info("System info displayed.")

        except ImportError:
            assistant.speech.speak(
                "System info requires psutil. "
                "Please install it with pip install psutil."
            )
        except Exception as e:
            logger.error("System info error: %s", e)
            assistant.speech.speak("Sorry, I had trouble getting system information.")

    # ── Clipboard ─────────────────────────────────────────────────

    @staticmethod
    def _clipboard(query: str, assistant) -> None:
        """Read or clear the clipboard."""
        try:
            import pyperclip

            if any(w in query for w in ("clear", "empty", "wipe")):
                pyperclip.copy("")
                assistant.speech.speak("Clipboard cleared.")
                print("📋 Clipboard: Cleared")
                logger.info("Clipboard cleared.")
            else:
                content = pyperclip.paste()
                if content:
                    # Truncate for speech
                    preview = content[:200]
                    print(f"\n📋 Clipboard contents:\n   {content[:500]}\n")
                    assistant.speech.speak(
                        f"The clipboard contains: {preview}"
                    )
                else:
                    assistant.speech.speak("The clipboard is empty.")
                    print("📋 Clipboard: Empty")

        except ImportError:
            assistant.speech.speak(
                "Clipboard access requires pyperclip. "
                "Please install it with pip install pyperclip."
            )
        except Exception as e:
            logger.error("Clipboard error: %s", e)
            assistant.speech.speak("Sorry, I had trouble accessing the clipboard.")

    # ── Recycle Bin ────────────────────────────────────────────────

    @staticmethod
    def _empty_recycle_bin(assistant) -> None:
        """Empty the recycle bin with confirmation."""
        assistant.speech.speak(
            "Are you sure you want to empty the recycle bin? "
            "This cannot be undone. Say yes to confirm."
        )
        confirm = assistant.speech.listen()
        if not confirm:
            confirm = "none"
        confirm = confirm.lower()

        if "yes" not in confirm and "confirm" not in confirm:
            assistant.speech.speak("Recycle bin emptying cancelled.")
            return

        try:
            import winshell
            winshell.recycle_bin().empty(
                confirm=False, show_progress=False, sound=True
            )
            assistant.speech.speak("Recycle bin emptied successfully.")
            print("🗑️  Recycle bin: Emptied")
            logger.info("Recycle bin emptied.")
        except ImportError:
            # Fallback: use PowerShell
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, timeout=10,
                )
                assistant.speech.speak("Recycle bin emptied.")
                print("🗑️  Recycle bin: Emptied (via PowerShell)")
                logger.info("Recycle bin emptied via PowerShell.")
            except Exception as e:
                logger.error("Recycle bin error: %s", e)
                assistant.speech.speak("Sorry, I couldn't empty the recycle bin.")
        except Exception as e:
            logger.error("Recycle bin error: %s", e)
            assistant.speech.speak("Sorry, I couldn't empty the recycle bin.")
