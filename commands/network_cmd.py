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

    def __init__(self):
        super().__init__()
        self.last_target = None  # "wifi", "bluetooth", or "hotspot"

    @property
    def triggers(self) -> list[str]:
        return [
            # WiFi
            "wifi", "wifi on", "wifi off", "turn on wifi", "turn off wifi",
            "enable wifi", "disable wifi", "connect wifi",
            "disconnect wifi", "wi-fi",
            # Bluetooth
            "bluetooth", "bluetooth on", "bluetooth off",
            "turn on bluetooth", "turn off bluetooth",
            "enable bluetooth", "disable bluetooth",
            # Hotspot
            "hotspot", "hotspot on", "hotspot off",
            "turn on hotspot", "turn off hotspot",
            "enable hotspot", "disable hotspot",
            "mobile hotspot", "start hotspot", "stop hotspot",
        ]

    def match_followup(self, query: str) -> bool:
        """Match follow-ups like 'turn it on', 'enable it', 'switch it off'."""
        followup_words = [
            "on", "off", "enable", "disable", "turn on", "turn off",
            "toggle", "switch", "connect", "disconnect",
        ]
        return any(word in query for word in followup_words)

    def execute(self, query: str, assistant) -> None:
        # Determine target from query, or fall back to context
        if "wifi" in query or "wi-fi" in query:
            self.last_target = "wifi"
        elif "bluetooth" in query:
            self.last_target = "bluetooth"
        elif "hotspot" in query:
            self.last_target = "hotspot"

        target = self.last_target

        if target == "wifi":
            enable = any(w in query for w in ("on", "enable", "turn on", "connect"))
            disable = any(w in query for w in ("off", "disable", "turn off", "disconnect"))

            if disable:
                self._toggle_wifi(False, assistant)
            elif enable:
                self._toggle_wifi(True, assistant)
            else:
                self._wifi_status(assistant)
            return

        if target == "bluetooth":
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

        if target == "hotspot":
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

        # No target set from context — ask the user
        assistant.speech.speak(
            "I can control WiFi, Bluetooth, or Hotspot. Which one?"
        )

    # ── WiFi ──────────────────────────────────────────────────────

    def _toggle_wifi(self, enable: bool, assistant) -> None:
        """
        Toggle WiFi directly via the WinRT Radio API (winsdk).
        Requires administrator privileges for write access to the radio.
        """
        if not _is_admin():
            assistant.speech.speak(
                "WiFi control requires administrator privileges. "
                "Please restart VEGA as administrator."
            )
            print("⚠️  Admin required: Right-click → Run as Administrator")
            return

        action_word = "on" if enable else "off"

        try:
            import asyncio
            from winsdk.windows.devices.radios import Radio, RadioState

            async def _toggle():
                radios = await Radio.get_radios_async()
                for radio in radios:
                    if radio.kind.name == "WI_FI":
                        # Check if already in the desired state
                        is_on = radio.state == RadioState.ON
                        if is_on == enable:
                            return "ALREADY"

                        target = RadioState.ON if enable else RadioState.OFF
                        await radio.set_state_async(target)

                        # Verify the state changed
                        radios2 = await Radio.get_radios_async()
                        for r2 in radios2:
                            if r2.kind.name == "WI_FI":
                                return "OK" if (r2.state == target) else "FAILED"
                        return "OK"
                return "NO_WIFI"

            result = asyncio.run(_toggle())

            if result == "ALREADY":
                assistant.speech.speak(f"WiFi is already {action_word}.")
            elif result == "OK":
                assistant.speech.speak(f"WiFi turned {action_word}.")
                logger.info("WiFi %s via WinRT Radio API.", action_word)
                print(f"📶 WiFi: {action_word.upper()}")
            elif result == "NO_WIFI":
                assistant.speech.speak(
                    "I couldn't find a WiFi adapter on this computer."
                )
            else:
                assistant.speech.speak(
                    "I tried to toggle WiFi but it didn't seem to change."
                )

        except ImportError:
            logger.error("winsdk is not installed.")
            assistant.speech.speak(
                "WiFi control requires the winsdk package. "
                "Please run: pip install winsdk"
            )
        except Exception as e:
            logger.error("WiFi toggle error: %s", e)
            assistant.speech.speak(
                "I encountered an error trying to toggle WiFi."
            )

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
        Toggle Bluetooth directly via the WinRT Radio API (winsdk).
        Requires administrator privileges for write access to the radio.
        """
        if not _is_admin():
            assistant.speech.speak(
                "Bluetooth control requires administrator privileges. "
                "Please restart VEGA as administrator."
            )
            print("⚠️  Admin required: Right-click → Run as Administrator")
            return

        action_word = "on" if enable else "off"

        try:
            import asyncio
            from winsdk.windows.devices.radios import Radio, RadioState

            async def _toggle():
                radios = await Radio.get_radios_async()
                for radio in radios:
                    if radio.kind.name == "BLUETOOTH":
                        # Check if already in the desired state
                        is_on = radio.state == RadioState.ON
                        if is_on == enable:
                            return "ALREADY"

                        target = RadioState.ON if enable else RadioState.OFF
                        await radio.set_state_async(target)

                        # Verify the state changed
                        radios2 = await Radio.get_radios_async()
                        for r2 in radios2:
                            if r2.kind.name == "BLUETOOTH":
                                return "OK" if (r2.state == target) else "FAILED"
                        return "OK"
                return "NO_BT"

            result = asyncio.run(_toggle())

            if result == "ALREADY":
                assistant.speech.speak(f"Bluetooth is already {action_word}.")
            elif result == "OK":
                assistant.speech.speak(f"Bluetooth turned {action_word}.")
                logger.info("Bluetooth %s via WinRT Radio API.", action_word)
                print(f"🔵 Bluetooth: {action_word.upper()}")
            elif result == "NO_BT":
                assistant.speech.speak(
                    "I couldn't find a Bluetooth adapter on this computer."
                )
            else:
                assistant.speech.speak(
                    "I tried to toggle Bluetooth but it didn't seem to change. "
                    "You may need to toggle it manually from Settings."
                )

        except ImportError:
            logger.error("winsdk is not installed.")
            assistant.speech.speak(
                "Bluetooth control requires the winsdk package. "
                "Please run: pip install winsdk"
            )
        except Exception as e:
            logger.error("Bluetooth toggle error: %s", e)
            assistant.speech.speak(
                "I encountered an error trying to toggle Bluetooth."
            )



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
