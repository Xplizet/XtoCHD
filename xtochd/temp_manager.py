"""Crash-proof temp-directory management.

The app extracts multi-gigabyte archives and runs chdman against the
extracted tracks. Temp directories are named with a timestamp + PID so
concurrent runs don't collide, and are best-effort cleaned on exit via an
``atexit`` hook. Orphans left by a prior crashed run are swept at startup
by age so disk usage doesn't balloon.
"""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime
from typing import Optional

from .constants import ORPHAN_TEMP_AGE_SECONDS

log = logging.getLogger(__name__)


class TempFileManager:
    """Manages temp subdirectories under ``<app_dir>/temp/``.

    ``app_dir`` points at the folder containing the frozen .exe (under
    PyInstaller) or main.py (when running from source), so the user can
    always find working files beside the app they launched.
    """

    def __init__(self) -> None:
        if getattr(sys, "frozen", False):
            self.app_dir: str = os.path.dirname(sys.executable)
        else:
            # main.py lives at the project root one level above this package.
            self.app_dir = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        self.temp_base_dir: str = os.path.join(self.app_dir, "temp")
        self.temp_dirs: list[str] = []
        self.cleanup_on_exit: bool = True

        self._ensure_temp_dir()
        atexit.register(self.cleanup_all_temp_dirs)

    def _ensure_temp_dir(self) -> None:
        try:
            os.makedirs(self.temp_base_dir, exist_ok=True)
        except OSError as e:
            log.warning("Could not create temp directory %s: %s", self.temp_base_dir, e)

    def create_temp_dir(self, prefix: str = "chdconv_") -> str:
        """Create a new temp subdirectory and remember it for cleanup.

        Uses ``tempfile.mkdtemp`` under the hood so back-to-back calls in
        the same second produce distinct directories (the legacy
        timestamp-plus-PID naming collided when a run processed multiple
        archives quickly). The timestamp is still included as a prefix so
        the orphan sweep's age check keeps working as expected.

        Falls back to the system temp root if the app's temp directory is
        unwritable (e.g. app installed to Program Files without elevation).
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dated_prefix = f"{prefix}{timestamp}_{os.getpid()}_"
        try:
            temp_dir = tempfile.mkdtemp(prefix=dated_prefix, dir=self.temp_base_dir)
            self.temp_dirs.append(temp_dir)
            return temp_dir
        except OSError as e:
            log.warning(
                "Could not create temp directory in %s, falling back: %s",
                self.temp_base_dir, e,
            )
            fallback_dir = tempfile.mkdtemp(prefix=dated_prefix)
            self.temp_dirs.append(fallback_dir)
            return fallback_dir

    def cleanup_temp_dir(self, temp_dir: str) -> bool:
        """Remove a single tracked temp directory. Returns True on success."""
        if temp_dir not in self.temp_dirs:
            return False
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            self.temp_dirs.remove(temp_dir)
            return True
        except OSError as e:
            log.warning("Could not clean up temp dir %s: %s", temp_dir, e)
            return False

    def cleanup_all_temp_dirs(self) -> int:
        """Remove every tracked temp directory. Called from atexit."""
        if not self.cleanup_on_exit:
            return 0
        cleaned = 0
        for temp_dir in list(self.temp_dirs):
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    cleaned += 1
            except OSError as e:
                log.warning("Could not clean up temp dir %s: %s", temp_dir, e)
        self.temp_dirs.clear()
        return cleaned

    def cleanup_orphaned_temp_dirs(self) -> int:
        """Sweep temp subdirs left by prior runs. Age-gated so the startup
        sweep never deletes a subdirectory belonging to an in-flight
        conversion that another XtoCHD instance might be running."""
        if not os.path.exists(self.temp_base_dir):
            return 0
        cleaned = 0
        try:
            for item in os.listdir(self.temp_base_dir):
                item_path = os.path.join(self.temp_base_dir, item)
                if not os.path.isdir(item_path):
                    continue
                try:
                    age_seconds = time.time() - os.stat(item_path).st_mtime
                    if age_seconds > ORPHAN_TEMP_AGE_SECONDS:
                        shutil.rmtree(item_path)
                        cleaned += 1
                except OSError as e:
                    log.warning("Could not check/clean temp dir %s: %s", item_path, e)
        except OSError as e:
            log.warning("Could not scan temp directory: %s", e)
        return cleaned

    def purge_temp_base_dir(self) -> int:
        """Delete every subdirectory under the temp base regardless of age.

        This is what the user is asking for when they click "Clean Temp
        Directory" in the Tools menu: a forceful cleanup, not the gentle
        age-gated sweep the startup path uses. Any directories we know
        we're currently using are also removed from the tracker.
        """
        if not os.path.exists(self.temp_base_dir):
            return 0
        cleaned = 0
        try:
            for item in os.listdir(self.temp_base_dir):
                item_path = os.path.join(self.temp_base_dir, item)
                if not os.path.isdir(item_path):
                    continue
                try:
                    shutil.rmtree(item_path)
                    cleaned += 1
                    if item_path in self.temp_dirs:
                        self.temp_dirs.remove(item_path)
                except OSError as e:
                    log.warning("Could not purge temp dir %s: %s", item_path, e)
        except OSError as e:
            log.warning("Could not scan temp directory: %s", e)
        return cleaned

    def get_temp_dir_size(self) -> int:
        """Return total bytes under the temp base directory (0 if missing)."""
        if not os.path.exists(self.temp_base_dir):
            return 0
        total = 0
        for root, _dirs, files in os.walk(self.temp_base_dir):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    @staticmethod
    def format_size(size_bytes: float) -> str:
        """Format a byte count as human-readable KB/MB/GB."""
        if size_bytes <= 0:
            return "0 B"
        units = ("B", "KB", "MB", "GB", "TB")
        i = 0
        while size_bytes >= 1024 and i < len(units) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {units[i]}"


# Module-level singleton used by the workers and the GUI.
temp_manager: TempFileManager = TempFileManager()
