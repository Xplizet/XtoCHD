"""QThread workers: scanning, validation, and CHD conversion.

Public surface (consumed by the GUI):

    ConversionWorker(files, output_dir, chdman_path)
      signals: progress_updated(int), progress_text(str), log_updated(str),
               conversion_finished()
      methods: start(), cancel(), cleanup_temp_dirs()
      attrs:   cancelled

    ScanWorker(input_paths)
      signals: scan_progress(str), scan_complete(list), scan_error(str)

    ValidationWorker(file_paths, max_workers=4, fast_validation=True)
      signals: validation_complete(dict), validation_progress(str, dict)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import QThread, pyqtSignal

from .constants import (
    ARCHIVE_EXTS,
    COMPATIBLE_EXTS,
    DISK_IMAGE_EXTS,
    INDEX_EXTS,
    TRACK_EXTS,
)
from .stats import ConversionStats, SuccessfulFile
from .temp_manager import temp_manager
from .validators import filter_conversion_candidates, get_file_info

log = logging.getLogger(__name__)

# Platforms other than Windows don't have CREATE_NO_WINDOW; fall back to 0.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _bsdtar_path() -> str | None:
    """Locate a tar binary that handles .rar/.7z via libarchive.

    Windows 10 1803+ ships bsdtar at ``%SystemRoot%\\System32\\tar.exe``.
    We target it by absolute path because Git for Windows puts a GNU tar on
    PATH that doesn't understand rar/7z and would shadow it.
    """
    if os.name == "nt":
        system_tar = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe"
        )
        if os.path.isfile(system_tar):
            return system_tar
    for candidate in ("bsdtar", "tar"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


class ConversionWorker(QThread):
    """Runs a batch of CHD conversions in the background.

    The worker owns a single ``chdman`` / bsdtar subprocess at any time
    (tracked via ``self.proc`` under ``_proc_lock``), so ``cancel()`` can
    kill it synchronously.
    """

    progress_updated = pyqtSignal(int)
    progress_text = pyqtSignal(str)
    log_updated = pyqtSignal(str)
    conversion_finished = pyqtSignal()

    def __init__(
        self, files: list[str], output_dir: str, chdman_path: str
    ) -> None:
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.chdman_path = chdman_path
        self.temp_dirs: list[str] = []
        self.stats = ConversionStats(total_files=len(files))
        self.cancelled = False
        self.proc: subprocess.Popen | None = None
        self._proc_lock = threading.Lock()

    # -- Cancellation ------------------------------------------------------

    def cancel(self) -> None:
        """Set the cancel flag and kill any in-flight subprocess."""
        self.cancelled = True
        self._kill_running_process()

    def _kill_running_process(self) -> None:
        with self._proc_lock:
            proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                # Kill the tree: chdman may spawn helpers we don't track.
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=_CREATE_NO_WINDOW,
                )
            else:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
        except OSError as e:
            self.log_updated.emit(f"Warning: failed to kill chdman: {e}")

    def _check_cancelled(self) -> bool:
        if self.cancelled:
            self.progress_text.emit("Stopping conversion...")
            return True
        return False

    # -- Entry point -------------------------------------------------------

    def run(self) -> None:  # noqa: D401  (QThread.run)
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except OSError as e:
            self.log_updated.emit(f"Failed to create output directory: {e}")
            self.conversion_finished.emit()
            return

        total_files = len(self.files)

        for idx, file_path in enumerate(self.files, start=1):
            if self._check_cancelled():
                break

            ext = os.path.splitext(file_path)[1].lower()
            progress_percent = int((idx - 1) / total_files * 100)
            self.progress_updated.emit(progress_percent)
            self.progress_text.emit(
                f"Processing {os.path.basename(file_path)} ({idx}/{total_files})"
            )

            if ext == ".zip":
                self.log_updated.emit(f"Processing zip: {file_path}")
                self._process_zip_file(file_path, idx, total_files)
            elif ext in ARCHIVE_EXTS:
                self.log_updated.emit(f"Processing archive: {file_path}")
                self._process_archive_file(file_path, idx, total_files)
            else:
                self._convert_single_file(file_path, idx, total_files)

        if not self.cancelled:
            self.progress_updated.emit(100)
            self.progress_text.emit("Conversion complete!")
            self.log_updated.emit("Conversion complete.")
            self._emit_summary()
        else:
            self.progress_text.emit("Conversion stopped.")
            self.log_updated.emit("Conversion stopped by user.")

        self.conversion_finished.emit()

    # -- Summary -----------------------------------------------------------

    def _emit_summary(self) -> None:
        s = self.stats
        lines: list[str] = []
        lines.append("=" * 50)
        lines.append("CONVERSION SUMMARY")
        lines.append("=" * 50)

        if s.successful_files:
            lines.append("SUCCESSFULLY CONVERTED:")
            for f in s.successful_files:
                lines.append(
                    f"  ✓ {f.name} ({f.original_size_mb:.1f} MB → {f.compressed_size_mb:.1f} MB)"
                )
            lines.append("")

        if s.skipped_files_list:
            lines.append("SKIPPED (CHD already exists):")
            for name in s.skipped_files_list:
                lines.append(f"  ⏭ {name}")
            lines.append("")

        if s.failed_files:
            lines.append("FAILED CONVERSIONS:")
            for name in s.failed_files:
                lines.append(f"  ✗ {name}")
            lines.append("")

        lines.append(f"Total files processed: {s.total_files}")
        lines.append(f"Successfully converted: {s.successful_conversions}")
        lines.append(f"Failed conversions: {s.failed_conversions}")
        lines.append(f"Skipped (already exist): {s.skipped_files}")
        if s.success_rate is not None:
            lines.append(f"Success rate: {s.success_rate:.1f}%")

        if s.original_size > 0:
            original_gb = s.original_size / (1024**3)
            compressed_gb = s.compressed_size / (1024**3)
            saved_gb = original_gb - compressed_gb
            lines.append("")
            lines.append("SIZE STATISTICS:")
            lines.append(f"Original total size: {original_gb:.2f} GB")
            lines.append(f"Compressed total size: {compressed_gb:.2f} GB")
            lines.append(f"Space saved: {saved_gb:.2f} GB")
            if s.compression_ratio is not None:
                lines.append(f"Compression ratio: {s.compression_ratio:.1f}%")

        lines.append("=" * 50)
        for line in lines:
            self.log_updated.emit(line)

    # -- Archive handlers --------------------------------------------------

    def _process_zip_file(
        self, zip_path: str, current_file: int, total_files: int
    ) -> None:
        if self._check_cancelled():
            return

        self.progress_text.emit(f"Extracting {os.path.basename(zip_path)}...")
        temp_dir = temp_manager.create_temp_dir(prefix="chdconv_zip_")
        self.temp_dirs.append(temp_dir)

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                zip_files = z.namelist()
                total_zip_files = len(zip_files) or 1

                # Cheap pre-check: if every candidate already has a .chd,
                # avoid extracting. Uses the same candidate-filter the real
                # conversion does so the count actually matches reality.
                candidate_entries = filter_conversion_candidates(zip_files)
                missing = 0
                for entry in candidate_entries:
                    base_name = os.path.splitext(os.path.basename(entry))[0]
                    chd_file = os.path.join(self.output_dir, base_name + ".chd")
                    if os.path.exists(chd_file):
                        self.log_updated.emit(
                            f"Skipped: {base_name} (CHD already exists)"
                        )
                        self.stats.skipped_files += 1
                        self.stats.skipped_files_list.append(base_name)
                    else:
                        missing += 1
                if candidate_entries and missing == 0:
                    self.log_updated.emit(
                        f"All disk images in {os.path.basename(zip_path)} "
                        f"already have CHD versions. Skipping extraction."
                    )
                    return

                for i, zip_file in enumerate(zip_files):
                    if self._check_cancelled():
                        return
                    # Skip extracting a track or index whose .chd already exists.
                    base_name = os.path.splitext(os.path.basename(zip_file))[0]
                    ext = os.path.splitext(zip_file)[1].lower()
                    if ext in DISK_IMAGE_EXTS or ext in INDEX_EXTS or ext in TRACK_EXTS:
                        chd_file = os.path.join(
                            self.output_dir, base_name + ".chd"
                        )
                        if os.path.exists(chd_file):
                            continue
                    z.extract(zip_file, temp_dir)
                    extraction_pct = int((i + 1) / total_zip_files * 20)
                    file_pct = int((current_file - 1) / total_files * 100)
                    self.progress_updated.emit(min(file_pct + extraction_pct, 99))
                    self.progress_text.emit(
                        f"Extracting {zip_file} from {os.path.basename(zip_path)}"
                    )

            if self._check_cancelled():
                return

            self.progress_text.emit("Scanning extracted files...")
            candidates = self._walk_candidates(temp_dir)
            for i, extracted in enumerate(candidates):
                if self._check_cancelled():
                    return
                self.progress_text.emit(
                    f"Converting extracted file {os.path.basename(extracted)} "
                    f"({i+1}/{len(candidates)})"
                )
                self._convert_single_file(extracted, current_file, total_files)
        except (OSError, zipfile.BadZipFile) as e:
            self.log_updated.emit(f"Failed to process zip {zip_path}: {e}")

    def _process_archive_file(
        self, archive_path: str, current_file: int, total_files: int
    ) -> None:
        """Extract .rar/.7z via bsdtar (libarchive) and convert images inside."""
        if self._check_cancelled():
            return

        tar_path = _bsdtar_path()
        if tar_path is None:
            self.log_updated.emit(
                f"Cannot extract {os.path.basename(archive_path)}: no bsdtar/tar "
                f"with rar/7z support found on this system."
            )
            self.stats.failed_conversions += 1
            self.stats.failed_files.append(os.path.basename(archive_path))
            return

        self.progress_text.emit(f"Listing {os.path.basename(archive_path)}...")
        temp_dir = temp_manager.create_temp_dir(prefix="chdconv_arc_")
        self.temp_dirs.append(temp_dir)

        try:
            list_result = subprocess.run(
                [tar_path, "-tf", archive_path],
                capture_output=True,
                text=True,
                creationflags=_CREATE_NO_WINDOW,
            )
            if list_result.returncode != 0:
                self.log_updated.emit(
                    f"Failed to list {os.path.basename(archive_path)}: "
                    f"{list_result.stderr.strip()}"
                )
                self.stats.failed_conversions += 1
                self.stats.failed_files.append(os.path.basename(archive_path))
                return

            entries = [
                e for e in list_result.stdout.splitlines()
                if e and not e.endswith("/")
            ]
            disk_entries = filter_conversion_candidates(entries)

            if disk_entries:
                missing: list[str] = []
                for entry in disk_entries:
                    base_name = os.path.splitext(os.path.basename(entry))[0]
                    chd_file = os.path.join(self.output_dir, base_name + ".chd")
                    if os.path.exists(chd_file):
                        self.log_updated.emit(
                            f"Skipped: {base_name} (CHD already exists)"
                        )
                        self.stats.skipped_files += 1
                        self.stats.skipped_files_list.append(base_name)
                    else:
                        missing.append(entry)
                if not missing:
                    self.log_updated.emit(
                        f"All disk images in {os.path.basename(archive_path)} "
                        f"already have CHD versions. Skipping extraction."
                    )
                    return

            if self._check_cancelled():
                return

            self.progress_text.emit(
                f"Extracting {os.path.basename(archive_path)}..."
            )
            extract_proc = subprocess.Popen(
                [tar_path, "-xf", archive_path, "-C", temp_dir],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=_CREATE_NO_WINDOW,
            )
            with self._proc_lock:
                self.proc = extract_proc
            try:
                _, err = extract_proc.communicate()
            finally:
                with self._proc_lock:
                    self.proc = None

            if self.cancelled:
                return
            if extract_proc.returncode != 0:
                self.log_updated.emit(
                    f"Failed to extract {os.path.basename(archive_path)}: "
                    f"{err.strip()}"
                )
                self.stats.failed_conversions += 1
                self.stats.failed_files.append(os.path.basename(archive_path))
                return

            candidates = self._walk_candidates(temp_dir)
            for i, extracted in enumerate(candidates):
                if self._check_cancelled():
                    return
                self.progress_text.emit(
                    f"Converting extracted file {os.path.basename(extracted)} "
                    f"({i+1}/{len(candidates)})"
                )
                self._convert_single_file(extracted, current_file, total_files)
        except OSError as e:
            self.log_updated.emit(
                f"Failed to process archive {archive_path}: {e}"
            )

    def _walk_candidates(self, temp_dir: str) -> list[str]:
        """Find disk-image files under ``temp_dir`` and filter to conversion targets."""
        all_found: list[str] = []
        for root, _dirs, files in os.walk(temp_dir):
            for fname in files:
                if self.cancelled:
                    return []
                ext = os.path.splitext(fname)[1].lower()
                if ext in DISK_IMAGE_EXTS or ext in INDEX_EXTS or ext in TRACK_EXTS:
                    all_found.append(os.path.join(root, fname))
        return filter_conversion_candidates(all_found)

    # -- Single-file conversion -------------------------------------------

    def _convert_single_file(
        self, file_path: str, _current_file: int, _total_files: int
    ) -> None:
        if self._check_cancelled():
            return

        ext = os.path.splitext(file_path)[1].lower()
        base_name = os.path.basename(file_path)
        stem = os.path.splitext(base_name)[0]
        output_chd_path = os.path.join(self.output_dir, stem + ".chd")

        if os.path.exists(output_chd_path):
            self.log_updated.emit(
                f"Skipped: {base_name} "
                f"(CHD already exists: {os.path.basename(output_chd_path)})"
            )
            self.stats.skipped_files += 1
            self.stats.skipped_files_list.append(base_name)
            return

        self.log_updated.emit(f"Converting: {file_path}")
        self.progress_text.emit(f"Converting {base_name} to CHD format...")

        original_size = self._measure_original_size(file_path, ext)
        self.stats.original_size += original_size

        if ext not in COMPATIBLE_EXTS:
            self.log_updated.emit(
                f"Skipped unsupported file type ({ext}): {file_path}"
            )
            self.stats.failed_conversions += 1
            self.stats.failed_files.append(base_name)
            return

        intermediate_chd = file_path + ".chd"
        cmd = [
            self.chdman_path,
            "createcd",
            "-i",
            file_path,
            "-o",
            intermediate_chd,
        ]

        self.progress_text.emit(f"Running CHD conversion on {base_name}...")
        try:
            return_code, _stdout, stderr = self._run_chdman(cmd)
        except OSError as e:
            self._discard_incomplete_output(intermediate_chd)
            self.log_updated.emit(f"Exception: {e}")
            self.progress_text.emit(f"✗ Error: {base_name}")
            self.stats.failed_conversions += 1
            self.stats.failed_files.append(base_name)
            return

        if self.cancelled:
            self._discard_incomplete_output(intermediate_chd)
            return

        if return_code != 0:
            self._discard_incomplete_output(intermediate_chd)
            self.log_updated.emit(f"Error converting {file_path}: {stderr}")
            self.progress_text.emit(f"✗ Failed: {base_name}")
            self.stats.failed_conversions += 1
            self.stats.failed_files.append(base_name)
            return

        # Success - move the intermediate .chd into the output dir.
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            shutil.move(intermediate_chd, output_chd_path)
            compressed_size = os.path.getsize(output_chd_path)
        except OSError as e:
            self._discard_incomplete_output(intermediate_chd)
            self.log_updated.emit(f"Error moving file to output directory: {e}")
            self.progress_text.emit(f"✗ Failed to move: {base_name}")
            self.stats.failed_conversions += 1
            self.stats.failed_files.append(base_name)
            return

        self.stats.compressed_size += compressed_size
        self.stats.successful_conversions += 1
        self.stats.successful_files.append(
            SuccessfulFile(
                name=os.path.basename(output_chd_path),
                original_size_mb=original_size / (1024**2),
                compressed_size_mb=compressed_size / (1024**2),
            )
        )
        self.log_updated.emit(f"Success: {output_chd_path}")
        self.progress_text.emit(f"✓ Completed: {os.path.basename(output_chd_path)}")
        self._cleanup_temp_files_for_file(file_path)

    def _run_chdman(
        self, cmd: list[str]
    ) -> tuple[int, str, str]:
        """Run chdman and return (return_code, stdout, stderr).

        - ``stdin=DEVNULL`` so chdman never blocks on an interactive prompt.
        - stdout/stderr drained in background threads: newer chdman emits
          continuous progress to stderr, which fills Windows' ~4 KB pipe
          buffer and would deadlock ``subprocess.run(capture_output=True)``.
        - The running process is exposed on ``self.proc`` so ``cancel()``
          can kill it synchronously.
        """
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=_CREATE_NO_WINDOW,
        )
        with self._proc_lock:
            self.proc = proc

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def drain(stream, sink: list[str]) -> None:
            try:
                for line in iter(stream.readline, ""):
                    sink.append(line)
            finally:
                try:
                    stream.close()
                except OSError:
                    pass

        t_out = threading.Thread(
            target=drain, args=(proc.stdout, stdout_chunks), daemon=True
        )
        t_err = threading.Thread(
            target=drain, args=(proc.stderr, stderr_chunks), daemon=True
        )
        t_out.start()
        t_err.start()

        return_code = proc.wait()
        t_out.join(timeout=2)
        t_err.join(timeout=2)

        with self._proc_lock:
            self.proc = None

        return return_code, "".join(stdout_chunks), "".join(stderr_chunks)

    def _measure_original_size(self, file_path: str, ext: str) -> int:
        """For index files, sum every non-.chd file in the same directory.

        The index file itself is a tiny text manifest (a few hundred bytes);
        the actual disc data is the track .bin/.raw/.sub files beside it.
        Stat'ing only the index would produce a meaningless compression
        ratio in the summary.
        """
        if ext in INDEX_EXTS:
            parent = os.path.dirname(file_path) or "."
            total = 0
            try:
                for entry in os.listdir(parent):
                    ep = os.path.join(parent, entry)
                    if os.path.isfile(ep) and not entry.lower().endswith(".chd"):
                        total += os.path.getsize(ep)
                return total
            except OSError:
                pass
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0

    def _discard_incomplete_output(self, path: str) -> None:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                self.log_updated.emit(f"Could not remove incomplete file: {e}")

    def _cleanup_temp_files_for_file(self, file_path: str) -> None:
        """Delete any leftover temp files whose name shares the converted file's stem."""
        stem = os.path.splitext(os.path.basename(file_path))[0]
        for temp_dir in self.temp_dirs:
            if not os.path.exists(temp_dir):
                continue
            for root, _dirs, files in os.walk(temp_dir):
                for name in files:
                    if stem in name:
                        try:
                            os.remove(os.path.join(root, name))
                        except OSError:
                            pass

    def cleanup_temp_dirs(self) -> int:
        """Public: remove every temp dir this worker created. Returns count cleaned."""
        cleaned = 0
        for d in self.temp_dirs:
            if temp_manager.cleanup_temp_dir(d):
                cleaned += 1
        self.temp_dirs = []
        return cleaned


class ScanWorker(QThread):
    """Walks user-supplied paths and emits the list of COMPATIBLE files found."""

    scan_progress = pyqtSignal(str)
    scan_complete = pyqtSignal(list)
    scan_error = pyqtSignal(str)

    def __init__(self, input_paths) -> None:
        super().__init__()
        self.input_paths = (
            input_paths if isinstance(input_paths, list) else [input_paths]
        )

    def run(self) -> None:
        try:
            self.scan_progress.emit("Scanning for files...")
            found: list[str] = []
            for input_path in self.input_paths:
                if os.path.isfile(input_path):
                    if os.path.splitext(input_path)[1].lower() in COMPATIBLE_EXTS:
                        found.append(input_path)
                        self.scan_progress.emit(
                            f"Found: {os.path.basename(input_path)}"
                        )
                    continue
                for root, dirs, files in os.walk(input_path):
                    # Skip hidden directories (anything starting with '.').
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    for fname in files:
                        if os.path.splitext(fname)[1].lower() in COMPATIBLE_EXTS:
                            fpath = os.path.join(root, fname)
                            found.append(fpath)
                            self.scan_progress.emit(f"Found: {os.path.basename(fpath)}")
            self.scan_complete.emit(found)
        except OSError as e:
            self.scan_error.emit(f"Scan error: {e}")


class ValidationWorker(QThread):
    """Validates a list of files in parallel, emitting per-file results as they finish."""

    validation_complete = pyqtSignal(dict)
    validation_progress = pyqtSignal(str, dict)  # file_path, file_info

    def __init__(
        self,
        file_paths: list[str],
        max_workers: int = 4,
        fast_validation: bool = True,
    ) -> None:
        super().__init__()
        self.file_paths = file_paths
        self.max_workers = max_workers
        self.fast_validation = fast_validation
        self._lock = threading.Lock()

    def _validate_single_file(self, file_path: str) -> tuple[str, dict]:
        try:
            return file_path, get_file_info(file_path, self.fast_validation)
        except OSError as e:
            return file_path, {
                "name": os.path.basename(file_path),
                "path": file_path,
                "size": 0,
                "size_str": "Unknown",
                "extension": os.path.splitext(file_path)[1].lower(),
                "is_valid": False,
                "validation_msg": f"Validation error: {e}",
            }

    def run(self) -> None:
        results: dict[str, dict] = {}
        # Cap worker count to file count - firing up four threads for two
        # files wastes scheduler time.
        effective_workers = max(1, min(self.max_workers, len(self.file_paths) or 1))
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = {
                executor.submit(self._validate_single_file, p): p
                for p in self.file_paths
            }
            for future in as_completed(futures):
                file_path, info = future.result()
                with self._lock:
                    results[file_path] = info
                self.validation_progress.emit(file_path, info)
        self.validation_complete.emit(results)
