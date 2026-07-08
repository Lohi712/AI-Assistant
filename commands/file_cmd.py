"""
File search and management command for VEGA AI Assistant.

Provides the ability to search for files across all local drives,
get detailed file information, open files/folders, and perform
file operations (copy, move, rename, delete) with voice confirmation.

Uses os.scandir for high-performance recursive directory traversal,
and win32api for drive discovery.
"""

import datetime
import hashlib
import msvcrt
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import win32api

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Directories to skip during search ──
# Only skip truly system/internal dirs — user-accessible dirs are searched
SKIP_DIRS = {
    "$recycle.bin", "system volume information", "windows",
    "program files", "program files (x86)",
    "recovery", "perflogs", "$windows.~bt", "$windows.~ws",
    "msocache", ".git", "node_modules",
    "__pycache__", "venv", ".venv",
}

# ── Extension mapping for natural language ──
EXTENSION_MAP = {
    "python": [".py"],
    "python files": [".py"],
    "java": [".java"],
    "java files": [".java"],
    "c++": [".cpp", ".hpp", ".cc", ".h"],
    "c++ files": [".cpp", ".hpp", ".cc", ".h"],
    "c files": [".c", ".h"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "html": [".html", ".htm"],
    "css": [".css"],
    "pdf": [".pdf"],
    "pdf files": [".pdf"],
    "word": [".docx", ".doc"],
    "word documents": [".docx", ".doc"],
    "excel": [".xlsx", ".xls", ".csv"],
    "excel files": [".xlsx", ".xls", ".csv"],
    "spreadsheets": [".xlsx", ".xls", ".csv"],
    "powerpoint": [".pptx", ".ppt"],
    "presentations": [".pptx", ".ppt"],
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"],
    "photos": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "pictures": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "music": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    "songs": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    "text": [".txt"],
    "text files": [".txt"],
    "zip": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "compressed": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "json": [".json"],
    "xml": [".xml"],
    "executables": [".exe", ".msi"],
    "installers": [".exe", ".msi", ".setup"],
}

# ── Known user folders (resolved via Windows Shell API) ──
USER_HOME = os.path.expanduser("~")


def _get_windows_folder(folder_name: str) -> str:
    """
    Get the real path of a Windows known folder using the Shell API.

    This correctly resolves OneDrive-redirected folders (e.g. Desktop
    may be at D:\\OneDrive\\Desktop instead of C:\\Users\\USER\\Desktop).

    Falls back to os.path.expanduser("~") + folder_name if the API fails.
    """
    import ctypes
    from ctypes import wintypes

    # Known folder GUIDs
    FOLDER_GUIDS = {
        "Desktop":   "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
        "Documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
        "Downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
        "Pictures":  "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
        "Videos":    "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
        "Music":     "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    }

    guid_str = FOLDER_GUIDS.get(folder_name)
    if not guid_str:
        return os.path.join(USER_HOME, folder_name)

    try:
        # Use SHGetKnownFolderPath to get the real path
        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
        CoTaskMemFree.argtypes = [ctypes.c_void_p]

        SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
        SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID), ctypes.c_ulong,
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)
        ]
        SHGetKnownFolderPath.restype = ctypes.HRESULT

        guid = GUID()
        ctypes.windll.ole32.CLSIDFromString(guid_str, ctypes.byref(guid))

        path_ptr = ctypes.c_wchar_p()
        result = SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr))

        if result == 0 and path_ptr.value:
            real_path = path_ptr.value
            CoTaskMemFree(path_ptr)
            return real_path

    except Exception:
        pass

    # Fallback to standard path
    return os.path.join(USER_HOME, folder_name)


# Resolve all known folders at import time (cached for performance)
KNOWN_FOLDERS = {
    "downloads": _get_windows_folder("Downloads"),
    "download":  _get_windows_folder("Downloads"),
    "documents": _get_windows_folder("Documents"),
    "document":  _get_windows_folder("Documents"),
    "desktop":   _get_windows_folder("Desktop"),
    "pictures":  _get_windows_folder("Pictures"),
    "picture":   _get_windows_folder("Pictures"),
    "photos":    _get_windows_folder("Pictures"),
    "videos":    _get_windows_folder("Videos"),
    "video":     _get_windows_folder("Videos"),
    "music":     _get_windows_folder("Music"),
    "songs":     _get_windows_folder("Music"),
}


def _get_all_drives() -> list[str]:
    """Get all available drive letters on the system."""
    try:
        drives = win32api.GetLogicalDriveStrings().split('\000')
        return [d for d in drives if d]
    except Exception:
        # Fallback: check common drive letters
        drives = []
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            path = f"{letter}:\\"
            if os.path.exists(path):
                drives.append(path)
        return drives


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    if size_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def _format_time(timestamp: float) -> str:
    """Format a timestamp into a readable date string."""
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime("%B %d, %Y at %I:%M %p")
    except (OSError, ValueError):
        return "Unknown"


def _search_files_recursive(
    root: str,
    name_query: str = "",
    extensions: list[str] | None = None,
    results: list | None = None,
    max_results: int = 10,
    skip_system: bool = True,
    stop_event: threading.Event | None = None,
) -> list[str]:
    """
    Recursively search for files using os.scandir (fastest method).

    Args:
        root: Directory to start searching from.
        name_query: Partial file name to match (case-insensitive).
        extensions: List of extensions to filter by (e.g. ['.pdf', '.docx']).
        results: Shared list to accumulate results (for threading).
        max_results: Stop after this many matches.
        skip_system: Skip system/hidden directories for speed.
        stop_event: Threading event to signal early abort (for voice stop).

    Returns:
        List of matching file paths.
    """
    if results is None:
        results = []

    try:
        with os.scandir(root) as entries:
            for entry in entries:
                # Check if search was cancelled
                if stop_event and stop_event.is_set():
                    return results

                # Stop early if we have enough results
                if len(results) >= max_results:
                    return results

                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Skip system/hidden directories
                        if skip_system and entry.name.lower() in SKIP_DIRS:
                            continue
                        # Skip hidden directories (starting with .)
                        if entry.name.startswith("."):
                            continue
                        # Recurse into subdirectory
                        _search_files_recursive(
                            entry.path, name_query, extensions,
                            results, max_results, skip_system,
                            stop_event,
                        )
                    elif entry.is_file(follow_symlinks=False):
                        name_lower = entry.name.lower()

                        # Match by name
                        if name_query and name_query not in name_lower:
                            continue

                        # Match by extension
                        if extensions:
                            _, ext = os.path.splitext(name_lower)
                            if ext not in extensions:
                                continue

                        results.append(entry.path)

                except (PermissionError, OSError):
                    continue

    except (PermissionError, OSError):
        pass

    return results


class FileCommand(BaseCommand):
    """
    File search and management command.

    Searches files across all local drives, provides file info,
    opens files/folders, and handles file operations.
    """

    priority = 8  # High priority — core feature

    def __init__(self):
        super().__init__()
        self._last_search_results: list[str] = []
        self._search_in_progress = False
        self._stop_search = threading.Event()  # Signal to stop file search

    @property
    def triggers(self) -> list[str]:
        return [
            # Search
            "find file", "find files", "search file", "search files",
            "search for", "find my", "locate", "look for",
            "find all", "where is",
            # Info
            "file info", "file details", "tell me about",
            "about this file", "file size",
            # Open folder — match the folder NAMES so natural phrases work
            "downloads", "documents", "desktop",
            "pictures", "videos", "music",
            "open folder", "go to folder", "go to",
            # File operations
            "delete file", "remove file",
            "rename file", "copy file", "move file",
            # Open file location
            "open location", "open file location",
            "show in folder", "show in explorer",
        ]

    def match(self, query: str) -> bool:
        """Match file-related queries, avoiding overlap with app/website opens."""
        # Check if any known folder name is mentioned
        # (handles: "open videos", "open my videos", "go to downloads", etc.)
        if any(folder in query for folder in KNOWN_FOLDERS):
            return True

        # "open location" / "show in explorer" for revealing files
        if any(t in query for t in ("open location", "file location",
                                     "show in folder", "show in explorer")):
            return True

        # Don't match plain "open" commands — those go to system/browser
        if query.strip().startswith("open") and "folder" not in query:
            return False

        return any(trigger in query for trigger in self.triggers)

    def execute(self, query: str, assistant) -> None:
        # ── Open file location from last search ──
        if any(t in query for t in ("open location", "file location",
                                     "show in folder", "show in explorer")):
            self._open_file_location(assistant)
            return

        # ── Open known folder ──
        # Flexible matching: if any known folder name appears in the query
        # This handles: "open videos", "open my videos", "go to videos",
        # "open the downloads folder", "videos folder", etc.
        for folder_name, folder_path in KNOWN_FOLDERS.items():
            if folder_name in query:
                self._open_folder(folder_path, folder_name, assistant)
                return

        if "open folder" in query or "go to folder" in query:
            assistant.speech.speak("Which folder would you like me to open?")
            folder = assistant.speech.listen()
            if not folder:
                folder = "none"
            folder = folder.strip()
            if folder and folder.lower() not in ("none", ""):
                # Check known folders first
                folder_lower = folder.lower()
                if folder_lower in KNOWN_FOLDERS:
                    self._open_folder(KNOWN_FOLDERS[folder_lower], folder_lower, assistant)
                elif os.path.isdir(folder):
                    self._open_folder(folder, folder, assistant)
                else:
                    assistant.speech.speak(f"I can't find a folder called {folder}.")
            return

        # ── File info ──
        if any(t in query for t in ("file info", "file details", "tell me about", "about this file", "file size")):
            self._file_info(query, assistant)
            return

        # ── File operations ──
        if "delete file" in query or "remove file" in query:
            self._delete_file(query, assistant)
            return
        if "rename file" in query:
            self._rename_file(assistant)
            return
        if "copy file" in query:
            self._copy_file(assistant)
            return
        if "move file" in query:
            self._move_file(assistant)
            return

        # ── File search ──
        self._search_files(query, assistant)

    # ── Search Implementation ──────────────────────────────────────

    def _search_files(self, query: str, assistant) -> None:
        """Search for files across all drives (interruptible by voice or ESC)."""

        # Determine what to search for
        search_term = ""
        target_extensions = None

        # Check for extension-based search: "find all pdf files"
        for keyword, exts in EXTENSION_MAP.items():
            if keyword in query:
                target_extensions = exts
                assistant.speech.speak(
                    f"Searching for {keyword} across all drives. "
                    "Say stop or press Escape to cancel."
                )
                logger.info("Extension search: %s -> %s", keyword, exts)
                break

        # If no extension match, extract the file name to search
        if target_extensions is None:
            # Remove trigger phrases to get the actual search term
            search_term = query
            for phrase in ("find file", "find files", "search file", "search files",
                           "search for", "find my", "locate", "look for",
                           "find all", "where is", "named", "called"):
                search_term = search_term.replace(phrase, "")
            search_term = search_term.strip()

            if not search_term:
                assistant.speech.speak("What file would you like me to search for?")
                search_term = assistant.speech.listen()
                if not search_term:
                    search_term = "none"
                search_term = search_term.strip().lower()
                if search_term in ("none", ""):
                    return

            assistant.speech.speak(
                f"Searching for {search_term} across all drives. "
                "Say stop or press Escape to cancel."
            )
            logger.info("Name search: '%s'", search_term)

        # ── Run search in background thread (so we can listen for "stop") ──
        print(f"\n🔍 Searching{'...' if not search_term else f' for: {search_term}'}")
        print("   (Say 'stop' or press ESC to cancel)\n")

        results = []
        drives = _get_all_drives()
        self._stop_search.clear()
        self._search_in_progress = True

        def _background_scan():
            """Worker: scan all drives in the background."""
            for drive in drives:
                if self._stop_search.is_set() or len(results) >= 25:
                    break
                try:
                    print(f"   Scanning {drive}...")
                    _search_files_recursive(
                        root=drive,
                        name_query=search_term.lower() if search_term else "",
                        extensions=target_extensions,
                        results=results,
                        max_results=25,
                        skip_system=True,
                        stop_event=self._stop_search,
                    )
                except Exception as e:
                    logger.warning("Error scanning %s: %s", drive, e)
            self._search_in_progress = False

        # Start the background search
        scan_thread = threading.Thread(
            target=_background_scan, daemon=True, name="vega-file-search"
        )
        scan_thread.start()

        # ── Main thread: listen for stop/cancel while search runs ──
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        STOP_PHRASES = {"stop", "cancel", "stop searching", "cancel search",
                        "stop it", "enough", "vega stop", "abort"}

        while scan_thread.is_alive():
            # Check ESC key
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'\x1b':  # Escape
                    print("\n   ⛔ Search cancelled (ESC).")
                    self._stop_search.set()
                    break

            # Try quick voice recognition (non-blocking, short timeout)
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.1)
                    audio = recognizer.listen(source, timeout=1.5, phrase_time_limit=3)

                phrase = recognizer.recognize_google(
                    audio, language="en-in"
                ).lower().strip()
                logger.debug("Search interrupt listener heard: '%s'", phrase)

                if any(s in phrase for s in STOP_PHRASES):
                    print(f"\n   ⛔ Search cancelled ('{phrase}').")
                    self._stop_search.set()
                    break

            except (sr.WaitTimeoutError, sr.UnknownValueError):
                pass
            except Exception as e:
                logger.debug("Search interrupt listener: %s", e)

        # Wait for the scan thread to finish (it should exit quickly after stop)
        scan_thread.join(timeout=2.0)
        self._search_in_progress = False

        # Check if search was cancelled
        was_cancelled = self._stop_search.is_set()

        # Store results for follow-up commands
        self._last_search_results = results

        if was_cancelled:
            if results:
                print(f"\n   ⚠️  Search stopped early. Found {len(results)} file(s) so far:\n")
                for i, path in enumerate(results, 1):
                    try:
                        size = _human_size(os.path.getsize(path))
                    except OSError:
                        size = "?"
                    print(f"   {i}. {path}  ({size})")

                assistant.speech.speak(
                    f"Search cancelled. I found {len(results)} files before stopping. "
                    "Check the console for results."
                )
            else:
                assistant.speech.speak("Search cancelled. No files were found yet.")
            return

        if not results:
            assistant.speech.speak("I couldn't find any matching files.")
            print("   ❌ No files found.")
            return

        # Report results
        print(f"\n📁 Found {len(results)} file(s):\n")
        for i, path in enumerate(results, 1):
            try:
                size = _human_size(os.path.getsize(path))
            except OSError:
                size = "?"
            print(f"   {i}. {path}  ({size})")

        # Auto-open the first result's location in Explorer
        first_file = results[0]
        try:
            # /select highlights the file in Explorer
            subprocess.Popen(["explorer", "/select,", first_file])
            logger.info("Opened file location: %s", first_file)
            print(f"\n   📂 Opened location of: {os.path.basename(first_file)}")
        except Exception as e:
            logger.warning("Couldn't open file location: %s", e)

        # Speak top results
        if len(results) == 1:
            assistant.speech.speak(
                f"I found one file: {os.path.basename(results[0])}. "
                "I've opened its location in Explorer."
            )
        else:
            top = min(3, len(results))
            names = ", ".join(os.path.basename(r) for r in results[:top])
            assistant.speech.speak(
                f"I found {len(results)} files. The top results are: {names}. "
                "I've opened the first file's location in Explorer."
            )

    # ── File Info ──────────────────────────────────────────────────

    def _file_info(self, query: str, assistant) -> None:
        """Get detailed info about a file."""
        # Check if there are recent search results
        if self._last_search_results:
            path = self._last_search_results[0]
            assistant.speech.speak(
                f"Here's info about the last found file: {os.path.basename(path)}"
            )
        else:
            assistant.speech.speak("Please tell me the file name or path.")
            user_input = assistant.speech.listen()
            if not user_input:
                user_input = "none"
            user_input = user_input.strip()
            if user_input.lower() in ("none", ""):
                return

            # Try as a direct path first
            if os.path.exists(user_input):
                path = user_input
            else:
                # Search for it
                assistant.speech.speak("Let me search for that file.")
                results = []
                for drive in _get_all_drives():
                    _search_files_recursive(
                        drive, user_input.lower(), None, results, 1, True
                    )
                    if results:
                        break
                if not results:
                    assistant.speech.speak("I couldn't find that file.")
                    return
                path = results[0]

        # Get file stats
        try:
            stat = os.stat(path)
            name = os.path.basename(path)
            _, ext = os.path.splitext(name)
            size = _human_size(stat.st_size)
            created = _format_time(stat.st_ctime)
            modified = _format_time(stat.st_mtime)
            accessed = _format_time(stat.st_atime)

            info = (
                f"\n📄 File Information:\n"
                f"   Name:     {name}\n"
                f"   Type:     {ext if ext else 'No extension'}\n"
                f"   Size:     {size}\n"
                f"   Path:     {path}\n"
                f"   Created:  {created}\n"
                f"   Modified: {modified}\n"
                f"   Accessed: {accessed}\n"
            )
            print(info)

            assistant.speech.speak(
                f"{name} is a {ext or 'unknown type'} file, "
                f"{size} in size, "
                f"last modified on {modified}."
            )

        except Exception as e:
            logger.error("File info error: %s", e)
            assistant.speech.speak("Sorry, I couldn't get information about that file.")

    # ── Folder Navigation ─────────────────────────────────────────

    @staticmethod
    def _open_folder(path: str, name: str, assistant) -> None:
        """Open a folder in Windows Explorer."""
        if os.path.isdir(path):
            assistant.speech.speak(f"Opening {name} folder.")
            subprocess.Popen(["explorer", os.path.normpath(path)])
            logger.info("Opened folder: %s", path)
        else:
            # Try common locations as fallback
            fallbacks = [
                os.path.join(os.path.expanduser("~"), name.capitalize()),
                os.path.join(os.path.expanduser("~"), name),
            ]
            for fb in fallbacks:
                if os.path.isdir(fb):
                    assistant.speech.speak(f"Opening {name} folder.")
                    subprocess.Popen(["explorer", os.path.normpath(fb)])
                    logger.info("Opened folder (fallback): %s", fb)
                    return
            assistant.speech.speak(
                f"I couldn't find the {name} folder. "
                f"The expected path was {path}."
            )
            logger.warning("Folder not found: %s", path)

    def _open_file_location(self, assistant) -> None:
        """Open Explorer with the last found file highlighted."""
        if not self._last_search_results:
            assistant.speech.speak(
                "I don't have any file to show. Please search for a file first."
            )
            return

        path = self._last_search_results[0]
        if os.path.exists(path):
            assistant.speech.speak(
                f"Opening the location of {os.path.basename(path)}."
            )
            subprocess.Popen(["explorer", "/select,", path])
            logger.info("Opened file location: %s", path)
        else:
            assistant.speech.speak("That file no longer exists.")

    # ── File Operations (with confirmation) ───────────────────────

    def _delete_file(self, query: str, assistant) -> None:
        """Delete a file with confirmation."""
        if not self._last_search_results:
            assistant.speech.speak("I don't have any file selected. Please search for a file first.")
            return

        path = self._last_search_results[0]
        name = os.path.basename(path)

        assistant.speech.speak(
            f"Are you sure you want to delete {name}? Say yes to confirm."
        )
        confirm = assistant.speech.listen()
        if not confirm:
            confirm = "none"
        confirm = confirm.lower()

        if "yes" in confirm or "confirm" in confirm:
            try:
                os.remove(path)
                assistant.speech.speak(f"{name} has been deleted.")
                logger.info("Deleted file: %s", path)
                self._last_search_results.pop(0)
            except Exception as e:
                logger.error("Delete failed: %s", e)
                assistant.speech.speak(f"Sorry, I couldn't delete {name}. {e}")
        else:
            assistant.speech.speak("Deletion cancelled.")

    def _rename_file(self, assistant) -> None:
        """Rename a file."""
        if not self._last_search_results:
            assistant.speech.speak("I don't have any file selected. Please search for a file first.")
            return

        path = self._last_search_results[0]
        name = os.path.basename(path)

        assistant.speech.speak(f"What would you like to rename {name} to?")
        new_name = assistant.speech.listen()
        if not new_name or new_name.lower() == "none":
            assistant.speech.speak("I didn't catch the new name.")
            return
        new_name = new_name.strip()

        try:
            directory = os.path.dirname(path)
            new_path = os.path.join(directory, new_name)
            os.rename(path, new_path)
            assistant.speech.speak(f"File renamed to {new_name}.")
            logger.info("Renamed: %s -> %s", path, new_path)
            self._last_search_results[0] = new_path
        except Exception as e:
            logger.error("Rename failed: %s", e)
            assistant.speech.speak(f"Sorry, I couldn't rename the file. {e}")

    def _copy_file(self, assistant) -> None:
        """Copy a file to a new location."""
        if not self._last_search_results:
            assistant.speech.speak("I don't have any file selected. Please search for a file first.")
            return

        path = self._last_search_results[0]
        name = os.path.basename(path)

        assistant.speech.speak(f"Where would you like to copy {name}? Say a folder name like downloads or documents.")
        target_folder = assistant.speech.listen()
        if not target_folder or target_folder.lower() == "none":
            assistant.speech.speak("I didn't catch the destination folder.")
            return
        dest = target_folder.strip().lower()

        # Map to known folders
        dest_path = KNOWN_FOLDERS.get(dest, dest)
        if not os.path.isdir(dest_path):
            assistant.speech.speak(f"I can't find the folder {dest}.")
            return

        try:
            shutil.copy2(path, dest_path)
            assistant.speech.speak(f"{name} copied to {dest}.")
            logger.info("Copied: %s -> %s", path, dest_path)
        except Exception as e:
            logger.error("Copy failed: %s", e)
            assistant.speech.speak(f"Sorry, I couldn't copy the file. {e}")

    def _move_file(self, assistant) -> None:
        """Move a file to a new location."""
        if not self._last_search_results:
            assistant.speech.speak("I don't have any file selected. Please search for a file first.")
            return

        path = self._last_search_results[0]
        name = os.path.basename(path)

        assistant.speech.speak(f"Where would you like to move {name}? Say a folder name like downloads or documents.")
        dest = assistant.speech.listen()
        if not dest:
            dest = "none"
        dest = dest.strip().lower()
        if dest in ("none", ""):
            return

        dest_path = KNOWN_FOLDERS.get(dest, dest)
        if not os.path.isdir(dest_path):
            assistant.speech.speak(f"I can't find the folder {dest}.")
            return

        assistant.speech.speak(
            f"Moving {name} to {dest}. Say yes to confirm."
        )
        confirm = assistant.speech.listen()
        if not confirm:
            confirm = "none"
        confirm = confirm.lower()

        if "yes" in confirm or "confirm" in confirm:
            try:
                shutil.move(path, dest_path)
                assistant.speech.speak(f"{name} moved to {dest}.")
                logger.info("Moved: %s -> %s", path, dest_path)
                self._last_search_results.pop(0)
            except Exception as e:
                logger.error("Move failed: %s", e)
                assistant.speech.speak(f"Sorry, I couldn't move the file. {e}")
        else:
            assistant.speech.speak("Move cancelled.")
