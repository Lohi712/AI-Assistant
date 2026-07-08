"""
Disk analysis and cleanup command for VEGA AI Assistant.

Provides storage analysis, large file detection, duplicate file finding,
temporary/junk file cleanup, and folder size calculation.

Uses os.scandir for fast traversal and hashlib for duplicate detection.
"""

import datetime
import hashlib
import os
import shutil
import tempfile
from collections import defaultdict

import win32api

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

# Reuse helpers from file_cmd
from commands.file_cmd import _get_all_drives, _human_size, SKIP_DIRS

# ── Known temp/junk locations ────────────────────────────────────
USER_HOME = os.path.expanduser("~")

TEMP_LOCATIONS = [
    tempfile.gettempdir(),                                           # %TEMP%
    os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "Temp"),  # C:\Windows\Temp
]

BROWSER_CACHE_LOCATIONS = [
    os.path.join(USER_HOME, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Cache"),
    os.path.join(USER_HOME, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Cache"),
    os.path.join(USER_HOME, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data", "Default", "Cache"),
]

JUNK_EXTENSIONS = {
    ".tmp", ".temp", ".log", ".bak", ".old", ".chk",
    ".dmp", ".crash", ".stackdump",
}

JUNK_FILENAMES = {
    "thumbs.db", "desktop.ini", ".ds_store",
}

# Minimum size (bytes) for "large file" detection — 100 MB
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024


def _get_dir_size(path: str) -> int:
    """Calculate total size of a directory recursively."""
    total = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += _get_dir_size(entry.path)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass
    return total


def _find_large_files(
    root: str,
    threshold: int = LARGE_FILE_THRESHOLD,
    results: list | None = None,
    max_results: int = 15,
) -> list[tuple[str, int]]:
    """Find files larger than threshold bytes."""
    if results is None:
        results = []

    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if len(results) >= max_results:
                    return results
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.lower() in SKIP_DIRS:
                            continue
                        _find_large_files(entry.path, threshold, results, max_results)
                    elif entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        if size >= threshold:
                            results.append((entry.path, size))
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass

    return results


def _find_temp_junk_files() -> list[tuple[str, int]]:
    """Find temporary and junk files across known locations."""
    junk_files = []

    # Scan temp directories
    for temp_dir in TEMP_LOCATIONS:
        if not os.path.isdir(temp_dir):
            continue
        try:
            with os.scandir(temp_dir) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            junk_files.append(
                                (entry.path, entry.stat(follow_symlinks=False).st_size)
                            )
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue

    # Scan browser caches
    for cache_dir in BROWSER_CACHE_LOCATIONS:
        if not os.path.isdir(cache_dir):
            continue
        try:
            cache_size = _get_dir_size(cache_dir)
            if cache_size > 0:
                junk_files.append((cache_dir, cache_size))
        except (PermissionError, OSError):
            continue

    return junk_files


def _get_file_hash(filepath: str, chunk_size: int = 8192) -> str | None:
    """Calculate MD5 hash of a file using chunked reading."""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, OSError):
        return None


class DiskCommand(BaseCommand):
    """
    Disk analysis and cleanup command.

    Provides disk usage reports, finds large/duplicate/junk files,
    and offers cleanup with confirmation.
    """

    priority = 12

    @property
    def triggers(self) -> list[str]:
        return [
            # Disk usage
            "disk usage", "storage status", "how much space",
            "drive space", "check storage", "disk space",
            "storage left", "free space",
            # Large files
            "find large files", "biggest files", "find big files",
            "what's taking space", "taking up space", "largest files",
            # Duplicates
            "find duplicates", "duplicate files", "duplicate finder",
            "find duplicate",
            # Junk / cleanup
            "find junk", "find junk files", "junk files",
            "clean temp", "clean temporary", "cleanup",
            "find useless files", "useless files", "free up space",
            "clear temp", "temp files",
            # Folder size
            "folder size", "how big is",
        ]

    def execute(self, query: str, assistant) -> None:
        # ── Disk usage ──
        if any(t in query for t in ("disk usage", "storage status", "how much space",
                                     "drive space", "check storage", "disk space",
                                     "storage left", "free space")):
            self._disk_usage(assistant)
            return

        # ── Large files ──
        if any(t in query for t in ("large files", "biggest files", "big files",
                                     "taking space", "taking up space", "largest files")):
            self._find_large_files(assistant)
            return

        # ── Duplicates ──
        if "duplicate" in query:
            self._find_duplicates(assistant)
            return

        # ── Junk / Cleanup ──
        if any(t in query for t in ("junk", "useless", "cleanup", "clean temp",
                                     "clean temporary", "free up space",
                                     "clear temp", "temp files")):
            self._find_junk(assistant)
            return

        # ── Folder size ──
        if "folder size" in query or "how big is" in query:
            self._folder_size(query, assistant)
            return

    # ── Disk Usage ────────────────────────────────────────────────

    def _disk_usage(self, assistant) -> None:
        """Report disk usage for all drives."""
        drives = _get_all_drives()
        print("\n💾 Disk Usage:\n")

        report_parts = []
        for drive in drives:
            try:
                usage = shutil.disk_usage(drive)
                total = _human_size(usage.total)
                used = _human_size(usage.used)
                free = _human_size(usage.free)
                percent = (usage.used / usage.total) * 100

                bar_len = 20
                filled = int(bar_len * usage.used / usage.total)
                bar = "█" * filled + "░" * (bar_len - filled)

                print(f"   {drive}  [{bar}] {percent:.0f}%")
                print(f"         Total: {total}  |  Used: {used}  |  Free: {free}\n")

                report_parts.append(
                    f"Drive {drive.rstrip(chr(92))} is {percent:.0f}% full with {free} free"
                )
            except Exception as e:
                logger.warning("Can't read drive %s: %s", drive, e)

        if report_parts:
            assistant.speech.speak(". ".join(report_parts) + ".")
        else:
            assistant.speech.speak("I couldn't read any drive information.")

    # ── Large Files ───────────────────────────────────────────────

    def _find_large_files(self, assistant) -> None:
        """Find the largest files on the system."""
        assistant.speech.speak(
            "Searching for large files over 100 megabytes. This may take a moment."
        )
        print("\n🔎 Scanning for large files (>100 MB)...\n")

        results = []
        drives = _get_all_drives()

        for drive in drives:
            print(f"   Scanning {drive}...")
            _find_large_files(drive, LARGE_FILE_THRESHOLD, results, max_results=15)

        if not results:
            assistant.speech.speak("I didn't find any files larger than 100 megabytes.")
            print("   No large files found.")
            return

        # Sort by size descending
        results.sort(key=lambda x: x[1], reverse=True)
        top = results[:10]

        print(f"\n📦 Top {len(top)} Largest Files:\n")
        total_size = 0
        for i, (path, size) in enumerate(top, 1):
            total_size += size
            print(f"   {i}. {_human_size(size):>10}  {path}")

        print(f"\n   Total: {_human_size(total_size)}\n")

        # Speak summary
        assistant.speech.speak(
            f"I found {len(results)} large files. "
            f"The biggest is {os.path.basename(top[0][0])} at {_human_size(top[0][1])}. "
            f"Check the console for the full list."
        )

    # ── Duplicate Files ───────────────────────────────────────────

    def _find_duplicates(self, assistant) -> None:
        """Find duplicate files in user directories."""
        assistant.speech.speak(
            "Scanning your user folders for duplicate files. This may take a while."
        )
        print("\n🔍 Scanning for duplicate files...\n")

        # Only scan user directories (not system dirs)
        scan_dirs = [
            os.path.join(USER_HOME, "Downloads"),
            os.path.join(USER_HOME, "Documents"),
            os.path.join(USER_HOME, "Desktop"),
            os.path.join(USER_HOME, "Pictures"),
            os.path.join(USER_HOME, "Videos"),
            os.path.join(USER_HOME, "Music"),
        ]

        # Phase 1: Group files by size
        size_map: dict[int, list[str]] = defaultdict(list)
        file_count = 0

        for scan_dir in scan_dirs:
            if not os.path.isdir(scan_dir):
                continue
            try:
                for root, dirs, files in os.walk(scan_dir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        try:
                            fsize = os.path.getsize(fpath)
                            if fsize > 1024:  # Skip tiny files
                                size_map[fsize].append(fpath)
                                file_count += 1
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                continue

        print(f"   Scanned {file_count} files.")

        # Phase 2: Hash files with same size
        potential = {s: paths for s, paths in size_map.items() if len(paths) > 1}
        hash_map: dict[str, list[str]] = defaultdict(list)

        for size, paths in potential.items():
            for path in paths:
                file_hash = _get_file_hash(path)
                if file_hash:
                    hash_map[file_hash].append(path)

        # Phase 3: Report duplicates
        duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}

        if not duplicates:
            assistant.speech.speak("No duplicate files found. Your system looks clean!")
            print("   ✅ No duplicates found.")
            return

        total_wasted = 0
        dup_count = 0

        print(f"\n📋 Found {len(duplicates)} groups of duplicate files:\n")
        for i, (hash_val, paths) in enumerate(duplicates.items(), 1):
            size = os.path.getsize(paths[0])
            wasted = size * (len(paths) - 1)
            total_wasted += wasted
            dup_count += len(paths) - 1

            print(f"   Group {i} ({_human_size(size)} each, {len(paths)} copies):")
            for p in paths:
                print(f"      • {p}")
            print()

        print(f"   💡 {dup_count} duplicate files wasting {_human_size(total_wasted)}\n")

        assistant.speech.speak(
            f"I found {dup_count} duplicate files wasting {_human_size(total_wasted)} of space. "
            "Check the console for details."
        )

    # ── Junk / Temp Files ─────────────────────────────────────────

    def _find_junk(self, assistant) -> None:
        """Find and optionally clean junk/temp files."""
        assistant.speech.speak("Scanning for temporary and junk files.")
        print("\n🗑️  Scanning for junk files...\n")

        junk_files = _find_temp_junk_files()

        if not junk_files:
            assistant.speech.speak("Your system looks clean! No junk files found.")
            print("   ✅ No junk files found.")
            return

        total_size = sum(size for _, size in junk_files)
        file_count = len(junk_files)

        print(f"   Found {file_count} items ({_human_size(total_size)}):\n")

        # Group by category
        temp_files = [(p, s) for p, s in junk_files if "Temp" in p or "temp" in p]
        cache_files = [(p, s) for p, s in junk_files if "Cache" in p or "cache" in p]
        other_files = [(p, s) for p, s in junk_files if p not in dict(temp_files) and p not in dict(cache_files)]

        if temp_files:
            temp_total = sum(s for _, s in temp_files)
            print(f"   📁 Temporary files: {len(temp_files)} items ({_human_size(temp_total)})")

        if cache_files:
            cache_total = sum(s for _, s in cache_files)
            print(f"   📁 Browser caches:  {len(cache_files)} items ({_human_size(cache_total)})")

        if other_files:
            other_total = sum(s for _, s in other_files)
            print(f"   📁 Other junk:      {len(other_files)} items ({_human_size(other_total)})")

        print(f"\n   Total: {_human_size(total_size)}\n")

        assistant.speech.speak(
            f"I found {_human_size(total_size)} of junk files including "
            f"temporary files and browser caches. "
            "Would you like me to clean them up? Say yes to confirm."
        )

        confirm = assistant.speech.listen()
        if not confirm:
            confirm = "none"
        confirm = confirm.lower()
        if "yes" in confirm or "confirm" in confirm or "clean" in confirm:
            cleaned = 0
            freed = 0

            for path, size in junk_files:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    elif os.path.isfile(path):
                        os.remove(path)
                    cleaned += 1
                    freed += size
                except (PermissionError, OSError) as e:
                    logger.debug("Couldn't delete %s: %s", path, e)

            assistant.speech.speak(
                f"Cleanup complete! Removed {cleaned} items and freed {_human_size(freed)}."
            )
            print(f"   ✅ Cleaned {cleaned} items, freed {_human_size(freed)}")
            logger.info("Junk cleanup: %d items, %s freed", cleaned, _human_size(freed))
        else:
            assistant.speech.speak("Cleanup cancelled. No files were deleted.")

    # ── Folder Size ───────────────────────────────────────────────

    def _folder_size(self, query: str, assistant) -> None:
        """Calculate the size of a specific folder."""
        from commands.file_cmd import KNOWN_FOLDERS

        # Check if a known folder is mentioned
        target = None
        for name, path in KNOWN_FOLDERS.items():
            if name in query:
                target = (name, path)
                break

        if not target:
            assistant.speech.speak("Which folder would you like me to check the size of?")
            folder_name = assistant.speech.listen()
            if not folder_name:
                folder_name = "none"
            folder_name = folder_name.strip().lower()
            if folder_name in ("none", ""):
                return
            if folder_name in KNOWN_FOLDERS:
                target = (folder_name, KNOWN_FOLDERS[folder_name])
            elif os.path.isdir(folder_name):
                target = (folder_name, folder_name)
            else:
                assistant.speech.speak(f"I can't find the folder {folder_name}.")
                return

        name, path = target
        assistant.speech.speak(f"Calculating the size of {name} folder. Please wait.")
        print(f"\n📁 Calculating size of: {path}")

        size = _get_dir_size(path)
        human = _human_size(size)

        print(f"   Size: {human}\n")
        assistant.speech.speak(f"The {name} folder is {human}.")
