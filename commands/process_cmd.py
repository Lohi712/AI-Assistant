"""
Process and application management command for VEGA AI Assistant.

Lists and kills running processes, shows installed applications,
and manages startup programs.

Uses psutil for process management and winreg for startup/installed apps.
"""

import os
import winreg

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_top_processes(sort_by: str = "memory", count: int = 10) -> list[dict]:
    """
    Get top processes sorted by CPU or memory usage.

    Args:
        sort_by: 'cpu' or 'memory'.
        count: Number of processes to return.

    Returns:
        List of dicts with name, pid, cpu_percent, memory_percent.
    """
    import psutil

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            if info["name"] and info["name"] not in ("System Idle Process", ""):
                processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "memory_percent" if sort_by == "memory" else "cpu_percent"
    processes.sort(key=lambda p: p.get(key, 0) or 0, reverse=True)
    return processes[:count]


def _kill_process_by_name(name: str) -> tuple[int, list[str]]:
    """
    Kill all processes matching the given name.

    Returns:
        Tuple of (count_killed, list_of_names_killed).
    """
    import psutil

    killed = 0
    killed_names = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc_name = proc.info["name"] or ""
            # Match by partial name (case-insensitive)
            if name.lower() in proc_name.lower():
                proc.kill()
                killed += 1
                killed_names.append(proc_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return killed, killed_names


def _get_installed_apps() -> list[dict]:
    """
    Get list of installed applications from the Windows Registry.

    Returns:
        List of dicts with name, version, publisher.
    """
    apps = []
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)

                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    except FileNotFoundError:
                        continue

                    try:
                        version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                    except FileNotFoundError:
                        version = ""

                    try:
                        publisher = winreg.QueryValueEx(subkey, "Publisher")[0]
                    except FileNotFoundError:
                        publisher = ""

                    if name and name.strip():
                        apps.append({
                            "name": name.strip(),
                            "version": version,
                            "publisher": publisher,
                        })

                    winreg.CloseKey(subkey)

                except (OSError, WindowsError):
                    continue

            winreg.CloseKey(key)

        except (OSError, WindowsError):
            continue

    # Deduplicate by name
    seen = set()
    unique = []
    for app in sorted(apps, key=lambda a: a["name"].lower()):
        if app["name"].lower() not in seen:
            seen.add(app["name"].lower())
            unique.append(app)

    return unique


def _get_startup_programs() -> list[dict]:
    """
    Get programs that run at startup from the Registry.

    Returns:
        List of dicts with name and command.
    """
    startups = []
    reg_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ]

    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            num_values = winreg.QueryInfoKey(key)[1]

            for i in range(num_values):
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    startups.append({
                        "name": name,
                        "command": value,
                        "scope": "User" if hive == winreg.HKEY_CURRENT_USER else "System",
                    })
                except (OSError, WindowsError):
                    continue

            winreg.CloseKey(key)
        except (OSError, WindowsError):
            continue

    return startups


class ProcessCommand(BaseCommand):
    """
    Process and application management command.

    Lists running processes, kills processes, shows installed apps,
    and manages startup programs.
    """

    priority = 14

    @property
    def triggers(self) -> list[str]:
        return [
            # Processes
            "running processes", "what's running", "active programs",
            "show processes", "list processes", "task manager",
            "running apps", "running applications",
            # Kill process
            "kill", "end task", "force close", "close app",
            "stop process", "terminate",
            # Installed apps
            "installed apps", "installed programs", "installed software",
            "list programs", "what apps", "what software",
            "what is installed",
            # Startup
            "startup programs", "startup apps", "what starts on boot",
            "boot programs", "autostart", "startup items",
        ]

    def match(self, query: str) -> bool:
        """Custom match to avoid conflicts with other commands."""
        # "kill" and "close" need context — avoid matching simple phrases
        if query.strip() in ("kill", "close", "stop"):
            return False

        # Check specific trigger phrases
        return any(trigger in query for trigger in self.triggers)

    def execute(self, query: str, assistant) -> None:
        # ── Kill process ──
        if any(t in query for t in ("kill", "end task", "force close",
                                     "close app", "stop process", "terminate")):
            self._kill_process(query, assistant)
            return

        # ── Running processes ──
        if any(t in query for t in ("running", "processes", "active programs",
                                     "task manager")):
            self._list_processes(assistant)
            return

        # ── Installed apps ──
        if any(t in query for t in ("installed", "list programs", "what apps",
                                     "what software")):
            self._list_installed(assistant)
            return

        # ── Startup programs ──
        if any(t in query for t in ("startup", "boot programs", "autostart")):
            self._list_startup(assistant)
            return

    # ── List Processes ────────────────────────────────────────────

    def _list_processes(self, assistant) -> None:
        """List top processes by memory usage."""
        try:
            import psutil
        except ImportError:
            assistant.speech.speak(
                "Process management requires psutil. "
                "Please install it with pip install psutil."
            )
            return

        assistant.speech.speak("Here are the top running processes.")

        processes = _get_top_processes(sort_by="memory", count=10)

        print("\n📊 Top 10 Processes (by Memory):\n")
        print(f"   {'Name':<30} {'PID':<8} {'CPU %':<8} {'Memory %':<8}")
        print(f"   {'─' * 30} {'─' * 8} {'─' * 8} {'─' * 8}")

        names = []
        for proc in processes:
            name = proc["name"][:30]
            pid = proc["pid"]
            cpu = proc.get("cpu_percent", 0) or 0
            mem = proc.get("memory_percent", 0) or 0

            print(f"   {name:<30} {pid:<8} {cpu:<8.1f} {mem:<8.1f}")
            names.append(proc["name"])

        print()

        # Speak top 3
        top3 = ", ".join(names[:3])
        assistant.speech.speak(
            f"The top processes by memory usage are: {top3}. "
            "Check the console for the full list."
        )

    # ── Kill Process ──────────────────────────────────────────────

    def _kill_process(self, query: str, assistant) -> None:
        """Kill a process by name with confirmation."""
        # Extract process name from query
        process_name = query
        for phrase in ("kill", "end task", "force close", "close app",
                       "stop process", "terminate", "process", "app"):
            process_name = process_name.replace(phrase, "")
        process_name = process_name.strip()

        if not process_name:
            assistant.speech.speak("Which process would you like me to kill?")
            process_name = assistant.speech.listen().strip()
            if process_name.lower() in ("none", ""):
                return

        # Confirm before killing
        assistant.speech.speak(
            f"Are you sure you want to kill all {process_name} processes? "
            "Say yes to confirm."
        )
        confirm = assistant.speech.listen().lower()

        if "yes" in confirm or "confirm" in confirm:
            try:
                import psutil
            except ImportError:
                assistant.speech.speak("Process management requires psutil.")
                return

            killed, names = _kill_process_by_name(process_name)

            if killed > 0:
                assistant.speech.speak(
                    f"Killed {killed} {process_name} process{'es' if killed > 1 else ''}."
                )
                logger.info("Killed %d processes matching '%s': %s", killed, process_name, names)
                print(f"   ✅ Killed {killed} process(es): {', '.join(names)}")
            else:
                assistant.speech.speak(f"No running process found matching {process_name}.")
        else:
            assistant.speech.speak("Process kill cancelled.")

    # ── Installed Apps ────────────────────────────────────────────

    def _list_installed(self, assistant) -> None:
        """List installed applications."""
        assistant.speech.speak("Let me check your installed applications.")

        apps = _get_installed_apps()

        if not apps:
            assistant.speech.speak("I couldn't find any installed applications.")
            return

        print(f"\n📦 Installed Applications ({len(apps)} found):\n")
        for i, app in enumerate(apps[:30], 1):  # Show first 30
            version = f" (v{app['version']})" if app["version"] else ""
            print(f"   {i:>3}. {app['name']}{version}")

        if len(apps) > 30:
            print(f"\n   ... and {len(apps) - 30} more.\n")
        else:
            print()

        assistant.speech.speak(
            f"You have {len(apps)} applications installed. "
            f"Some of them include: {', '.join(a['name'] for a in apps[:5])}. "
            "Check the console for the full list."
        )

    # ── Startup Programs ──────────────────────────────────────────

    def _list_startup(self, assistant) -> None:
        """List programs that run at startup."""
        startups = _get_startup_programs()

        if not startups:
            assistant.speech.speak("No startup programs found.")
            return

        print(f"\n🚀 Startup Programs ({len(startups)}):\n")
        for i, prog in enumerate(startups, 1):
            print(f"   {i}. [{prog['scope']}] {prog['name']}")
            print(f"      Command: {prog['command'][:80]}...")

        print()

        names = ", ".join(p["name"] for p in startups[:5])
        assistant.speech.speak(
            f"You have {len(startups)} startup programs including: {names}. "
            "Check the console for details."
        )
