"""
Network control command for VEGA AI Assistant.

Toggles WiFi, Bluetooth, and Mobile Hotspot on/off.

WiFi uses netsh CLI, Bluetooth and Hotspot use PowerShell
with Windows Runtime (WinRT) APIs.

Note: These operations typically require administrator privileges.
"""

import ctypes
import subprocess

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


def _is_admin() -> bool:
    """Check if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _run_powershell(script: str) -> tuple[bool, str]:
    """
    Execute a PowerShell script and return (success, output).

    Uses -ExecutionPolicy Bypass to avoid policy restrictions.
    """
    try:
        result = subprocess.run(
            [
                "powershell", "-ExecutionPolicy", "Bypass",
                "-NoProfile", "-Command", script,
            ],
            capture_output=True, text=True, timeout=15,
        )
        success = result.returncode == 0
        output = result.stdout.strip() or result.stderr.strip()
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


class NetworkCommand(BaseCommand):
    """
    Network connectivity control — WiFi, Bluetooth, Mobile Hotspot.
    """

    priority = 12

    @property
    def triggers(self) -> list[str]:
        return [
            # WiFi
            "wifi on", "wifi off", "turn on wifi", "turn off wifi",
            "enable wifi", "disable wifi", "connect wifi",
            "disconnect wifi", "wi-fi",
            # Bluetooth
            "bluetooth on", "bluetooth off",
            "turn on bluetooth", "turn off bluetooth",
            "enable bluetooth", "disable bluetooth",
            # Hotspot
            "hotspot on", "hotspot off",
            "turn on hotspot", "turn off hotspot",
            "enable hotspot", "disable hotspot",
            "mobile hotspot", "start hotspot", "stop hotspot",
        ]

    def execute(self, query: str, assistant) -> None:
        # ── WiFi ──
        if "wifi" in query or "wi-fi" in query:
            enable = any(w in query for w in ("on", "enable", "turn on", "connect"))
            disable = any(w in query for w in ("off", "disable", "turn off", "disconnect"))

            if disable:
                self._toggle_wifi(False, assistant)
            elif enable:
                self._toggle_wifi(True, assistant)
            else:
                # Just "wifi" — check status
                self._wifi_status(assistant)
            return

        # ── Bluetooth ──
        if "bluetooth" in query:
            enable = any(w in query for w in ("on", "enable", "turn on"))
            disable = any(w in query for w in ("off", "disable", "turn off"))

            if disable:
                self._toggle_bluetooth(False, assistant)
            elif enable:
                self._toggle_bluetooth(True, assistant)
            else:
                assistant.speech.speak(
                    "Would you like me to turn bluetooth on or off?"
                )
            return

        # ── Hotspot ──
        if "hotspot" in query:
            enable = any(w in query for w in ("on", "enable", "turn on", "start"))
            disable = any(w in query for w in ("off", "disable", "turn off", "stop"))

            if disable:
                self._toggle_hotspot(False, assistant)
            elif enable:
                self._toggle_hotspot(True, assistant)
            else:
                assistant.speech.speak(
                    "Would you like me to turn the hotspot on or off?"
                )
            return

    # ── WiFi ──────────────────────────────────────────────────────

    def _toggle_wifi(self, enable: bool, assistant) -> None:
        """Toggle WiFi using netsh interface command."""
        if not _is_admin():
            assistant.speech.speak(
                "WiFi control requires administrator privileges. "
                "Please restart VEGA as administrator."
            )
            print("⚠️  Admin required: Right-click → Run as Administrator")
            return

        action = "enabled" if enable else "disabled"
        action_word = "on" if enable else "off"

        # Try common WiFi interface names
        interface_names = ["Wi-Fi", "WiFi", "Wireless Network Connection"]

        for iface in interface_names:
            try:
                result = subprocess.run(
                    f'netsh interface set interface "{iface}" {action}',
                    shell=True, capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    assistant.speech.speak(f"WiFi turned {action_word}.")
                    logger.info("WiFi %s (interface: %s)", action, iface)
                    print(f"📶 WiFi: {action_word.upper()}")
                    return
            except Exception:
                continue

        assistant.speech.speak(
            "I couldn't find the WiFi interface. "
            "Your WiFi adapter might have a different name."
        )
        logger.error("WiFi toggle failed — no matching interface found.")

    def _wifi_status(self, assistant) -> None:
        """Check current WiFi status."""
        try:
            result = subprocess.run(
                "netsh wlan show interfaces",
                shell=True, capture_output=True, text=True, timeout=10,
            )
            output = result.stdout

            if "connected" in output.lower():
                # Extract SSID
                for line in output.split("\n"):
                    if "SSID" in line and "BSSID" not in line:
                        ssid = line.split(":")[1].strip()
                        assistant.speech.speak(f"WiFi is connected to {ssid}.")
                        print(f"📶 WiFi: Connected to {ssid}")
                        return

                assistant.speech.speak("WiFi is connected.")
            elif "disconnected" in output.lower():
                assistant.speech.speak("WiFi is disconnected.")
                print("📶 WiFi: Disconnected")
            else:
                assistant.speech.speak("WiFi adapter is available but not connected.")
        except Exception as e:
            logger.error("WiFi status error: %s", e)
            assistant.speech.speak("I couldn't check the WiFi status.")

    # ── Bluetooth ─────────────────────────────────────────────────

    def _toggle_bluetooth(self, enable: bool, assistant) -> None:
        """
        Toggle Bluetooth using multiple approaches for reliability.

        Method 1: PowerShell WinRT Radio API (cleanest)
        Method 2: Automated Settings UI toggle via pyautogui (fallback)
        """
        action_word = "on" if enable else "off"
        assistant.speech.speak(f"Turning bluetooth {action_word}.")

        # ── Method 1: WinRT Radio API ──
        if self._bt_via_winrt(enable):
            assistant.speech.speak(f"Bluetooth turned {action_word}.")
            logger.info("Bluetooth %s via WinRT.", action_word)
            print(f"🔵 Bluetooth: {action_word.upper()}")
            return

        logger.warning("WinRT Bluetooth toggle failed, trying Settings UI...")

        # ── Method 2: Automated Settings UI ──
        if self._bt_via_settings_ui(enable):
            assistant.speech.speak(f"Bluetooth turned {action_word}.")
            logger.info("Bluetooth %s via Settings UI.", action_word)
            print(f"🔵 Bluetooth: {action_word.upper()}")
            return

        # All methods failed
        assistant.speech.speak(
            f"I couldn't turn bluetooth {action_word} automatically. "
            "Opening the bluetooth settings for you."
        )
        try:
            import os
            os.startfile("ms-settings:bluetooth")
        except Exception:
            pass

    @staticmethod
    def _bt_via_winrt(enable: bool) -> bool:
        """Try toggling Bluetooth via PowerShell WinRT Radio API."""
        state = "On" if enable else "Off"

        ps_script = f"""
        try {{
            Add-Type -AssemblyName System.Runtime.WindowsRuntime

            [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null

            $asyncOp = [Windows.Devices.Radios.Radio]::GetRadiosAsync()
            $radios = $asyncOp.GetAwaiter().GetResult()

            $btRadio = $radios | Where-Object {{ $_.Kind -eq 'Bluetooth' }}

            if ($btRadio) {{
                $btRadio.SetStateAsync([Windows.Devices.Radios.RadioState]::{state}).GetAwaiter().GetResult() | Out-Null
                Write-Output "SUCCESS"
            }} else {{
                Write-Output "NO_BT"
            }}
        }} catch {{
            Write-Output "ERROR: $_"
        }}
        """

        success, output = _run_powershell(ps_script)
        if "SUCCESS" in output:
            return True

        logger.debug("WinRT Bluetooth result: %s", output)
        return False

    @staticmethod
    def _bt_via_settings_ui(enable: bool) -> bool:
        """
        Toggle Bluetooth by opening Settings and clicking the toggle.

        Uses pyautogui for automated UI interaction.
        """
        import os
        import time

        try:
            import pyautogui
        except ImportError:
            return False

        try:
            # Open Bluetooth settings
            os.startfile("ms-settings:bluetooth")
            time.sleep(2.5)  # Wait for Settings to fully load

            # Bring the Settings window to foreground
            try:
                hwnd = ctypes.windll.user32.FindWindowW(
                    "ApplicationFrameWindow", None
                )
                if hwnd:
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    time.sleep(0.5)
            except Exception:
                pass

            # The Bluetooth toggle is the first interactive element
            pyautogui.press("tab")
            time.sleep(0.3)
            pyautogui.press("space")
            time.sleep(1.0)

            # Close ONLY the Settings app (not other windows)
            try:
                subprocess.run(
                    ["taskkill", "/f", "/im", "SystemSettings.exe"],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

            return True
        except Exception as e:
            logger.debug("Settings UI Bluetooth toggle failed: %s", e)
            return False

    # ── Mobile Hotspot ────────────────────────────────────────────

    def _toggle_hotspot(self, enable: bool, assistant) -> None:
        """Toggle Mobile Hotspot using PowerShell WinRT API."""
        action = "Start" if enable else "Stop"
        action_word = "on" if enable else "off"

        ps_script = f"""
        try {{
            # Load WinRT types
            [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime] | Out-Null
            [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null

            $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()

            if ($null -eq $connectionProfile) {{
                Write-Output "NO_INTERNET"
            }} else {{
                $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($connectionProfile)
                $result = $tetheringManager.{action}TetheringAsync().GetAwaiter().GetResult()
                Write-Output "SUCCESS: $($result.Status)"
            }}
        }} catch {{
            Write-Output "ERROR: $_"
        }}
        """

        assistant.speech.speak(f"Turning mobile hotspot {action_word}.")

        success, output = _run_powershell(ps_script)

        if "SUCCESS" in output:
            assistant.speech.speak(f"Mobile hotspot turned {action_word}.")
            logger.info("Hotspot %s.", action_word)
            print(f"📡 Hotspot: {action_word.upper()}")
        elif "NO_INTERNET" in output:
            assistant.speech.speak(
                "There's no active internet connection to share via hotspot."
            )
        else:
            assistant.speech.speak(
                f"I had trouble with the hotspot. You may need to toggle it manually from settings."
            )
            logger.error("Hotspot toggle failed: %s", output)
