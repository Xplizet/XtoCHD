"""Disc-image validation and conversion-candidate filtering.

Validation is a lightweight sanity check - chdman does the real work. The
goal is only to flag obviously broken files in the GUI's file list before a
user spends 10 minutes on a run that was never going to succeed.

``filter_conversion_candidates`` is the most important function in this
module: given a pile of extracted files, it chooses which ones to hand to
chdman and which to skip. Getting this wrong is what made chdman 0.287
appear to hang in earlier versions of the tool.
"""

from __future__ import annotations

import os
import zipfile
from typing import Callable, Iterable

from .constants import (
    BIN_MIN_SIZE_BYTES,
    CCD_READ_BYTES,
    CUE_FAST_READ_BYTES,
    CUE_FULL_READ_BYTES,
    GDI_READ_BYTES,
    IMG_MIN_SIZE_BYTES,
    INDEX_EXTS,
    INDEX_PRIORITY,
    ISO_9660_SIGNATURE,
    ISO_FULL_SCAN_BYTES,
    ISO_MIN_SIZE_BYTES,
    RAR_MAGIC_LEGACY,
    RAR_MAGIC_V5,
    SEVENZIP_MAGIC,
    TOC_READ_BYTES,
    TRACK_EXTS,
    ZIP_MAGIC,
)

ValidationResult = tuple[bool, str]


def filter_conversion_candidates(paths: Iterable[str]) -> list[str]:
    """Return only the files that chdman should actually run on.

    - If a directory contains any of .cue/.gdi/.toc/.ccd, keep exactly one
      (by INDEX_PRIORITY). The others are duplicates of the same disc.
    - Drop .bin/.img/.sub/.raw tracks whose directory already has an index:
      chdman reads them transitively via the index file.
    - Standalone .iso passes through.
    - An orphan .bin/.img/.sub/.raw (no sibling index) passes through -
      chdman may or may not handle it, but the user asked for it.
    """
    paths = list(paths)

    # Decide the winning index file for each directory.
    chosen_index_by_dir: dict[str, str] = {}
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext not in INDEX_EXTS:
            continue
        d = os.path.dirname(p)
        current = chosen_index_by_dir.get(d)
        if current is None or INDEX_PRIORITY.index(ext) < INDEX_PRIORITY.index(
            os.path.splitext(current)[1].lower()
        ):
            chosen_index_by_dir[d] = p
    chosen = set(chosen_index_by_dir.values())
    dirs_with_index = set(chosen_index_by_dir.keys())

    kept: list[str] = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext in INDEX_EXTS:
            if p in chosen:
                kept.append(p)
        elif ext == ".iso":
            kept.append(p)
        elif ext in TRACK_EXTS:
            if os.path.dirname(p) not in dirs_with_index:
                kept.append(p)
    return kept


def validate_file(file_path: str, fast_mode: bool = True) -> ValidationResult:
    """Check that ``file_path`` exists, is non-empty, and passes a cheap per-format sniff."""
    try:
        if not os.path.isfile(file_path):
            return False, "Not a file"
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "Empty file"

        with open(file_path, "rb") as f:
            header = f.read(ISO_MIN_SIZE_BYTES)
        if not header:
            return False, "Cannot read file"

        ext = os.path.splitext(file_path)[1].lower()
        validator = _VALIDATORS.get(ext)
        if validator is None:
            return True, "File appears valid"
        return validator(file_path, header, file_size, fast_mode)
    except OSError as e:
        return False, f"Validation error: {e}"


def _validate_iso(
    _path: str, header: bytes, file_size: int, fast_mode: bool
) -> ValidationResult:
    if fast_mode:
        if file_size >= ISO_MIN_SIZE_BYTES:
            return True, "ISO file appears valid (fast mode)"
        return False, "ISO file too small"

    # Thorough: look for an ISO 9660 primary volume descriptor in the
    # header region. In real ISO images the PVD lives at LBA 16 (offset
    # 32768), beyond the 2 KB header we read - so for headers shorter than
    # that, we only confirm a minimum size. That's intentional; chdman
    # will catch truly malformed files.
    if len(header) >= ISO_FULL_SCAN_BYTES:
        for i in range(0, min(len(header), ISO_FULL_SCAN_BYTES), 2048):
            if header[i : i + 6] == ISO_9660_SIGNATURE:
                return True, "Valid ISO 9660 format"
    if file_size >= ISO_MIN_SIZE_BYTES:
        return True, "ISO file appears valid"
    return False, "ISO file too small"


def _validate_cue(
    file_path: str, _header: bytes, _file_size: int, fast_mode: bool
) -> ValidationResult:
    try:
        read_bytes = CUE_FAST_READ_BYTES if fast_mode else CUE_FULL_READ_BYTES
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(read_bytes)
        if not content.strip():
            return False, "Empty CUE file"
        has_file = False
        has_track = False
        for raw in content.splitlines():
            line = raw.strip().upper()
            if line.startswith("FILE"):
                has_file = True
            elif line.startswith("TRACK"):
                has_track = True
        if has_file and has_track:
            return True, "Valid CUE file" + (" (fast mode)" if fast_mode else "")
        return False, "Invalid CUE file structure"
    except OSError as e:
        return False, f"CUE validation error: {e}"


def _validate_bin(
    _path: str, _header: bytes, file_size: int, _fast_mode: bool
) -> ValidationResult:
    if file_size >= BIN_MIN_SIZE_BYTES:
        return True, "BIN file appears valid"
    return False, "BIN file too small"


def _validate_img(
    _path: str, _header: bytes, file_size: int, _fast_mode: bool
) -> ValidationResult:
    if file_size >= IMG_MIN_SIZE_BYTES:
        return True, "IMG file appears valid"
    return False, "IMG file too small"


def _validate_zip(
    file_path: str, _header: bytes, _file_size: int, fast_mode: bool
) -> ValidationResult:
    try:
        if fast_mode:
            with open(file_path, "rb") as f:
                magic = f.read(4)
            if magic == ZIP_MAGIC:
                return True, "Valid ZIP file (fast mode)"
            return False, "Invalid ZIP file format"
        with zipfile.ZipFile(file_path, "r") as z:
            bad = z.testzip()
            if bad is None:
                return True, "Valid ZIP file"
            return False, f"ZIP file corrupted: {bad}"
    except zipfile.BadZipFile:
        return False, "Invalid ZIP file format"
    except OSError as e:
        return False, f"ZIP validation error: {e}"


def _validate_rar(
    _path: str, header: bytes, _file_size: int, fast_mode: bool
) -> ValidationResult:
    """Check the RAR signature. Both legacy (RAR 1.5-4) and RAR5 layouts."""
    if header.startswith(RAR_MAGIC_V5):
        return True, "Valid RAR5 archive" + (" (fast mode)" if fast_mode else "")
    if header.startswith(RAR_MAGIC_LEGACY):
        return True, "Valid RAR archive" + (" (fast mode)" if fast_mode else "")
    return False, "Invalid RAR file format"


def _validate_7z(
    _path: str, header: bytes, _file_size: int, fast_mode: bool
) -> ValidationResult:
    if header.startswith(SEVENZIP_MAGIC):
        return True, "Valid 7z archive" + (" (fast mode)" if fast_mode else "")
    return False, "Invalid 7z file format"


def _validate_gdi(
    file_path: str, _header: bytes, _file_size: int, _fast_mode: bool
) -> ValidationResult:
    """A GDI manifest starts with a single integer (the track count), then
    one line per track. We sanity-check just the first line."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            first = f.readline(GDI_READ_BYTES).strip()
        if not first:
            return False, "Empty GDI file"
        try:
            track_count = int(first)
        except ValueError:
            return False, "GDI file does not start with a track count"
        if track_count <= 0 or track_count > 99:
            return False, f"GDI track count out of range: {track_count}"
        return True, f"Valid GDI file ({track_count} tracks)"
    except OSError as e:
        return False, f"GDI validation error: {e}"


def _validate_toc(
    file_path: str, _header: bytes, _file_size: int, _fast_mode: bool
) -> ValidationResult:
    """CDRDAO .toc files are text. They always mention one of a small set
    of session/track-mode keywords up near the top."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(TOC_READ_BYTES).upper()
        if not head.strip():
            return False, "Empty TOC file"
        if any(token in head for token in (
            "CD_DA", "CD_ROM_XA", "CD_ROM", "CD_I", "CATALOG", "TRACK",
        )):
            return True, "Valid TOC file"
        return False, "TOC file does not contain expected CDRDAO keywords"
    except OSError as e:
        return False, f"TOC validation error: {e}"


def _validate_ccd(
    file_path: str, _header: bytes, _file_size: int, _fast_mode: bool
) -> ValidationResult:
    """CloneCD .ccd files are INI-shaped. The [CloneCD] or [Disc] section
    appears at the top of every valid descriptor."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(CCD_READ_BYTES)
        if not head.strip():
            return False, "Empty CCD file"
        if "[CloneCD]" in head or "[Disc]" in head:
            return True, "Valid CCD file"
        return False, "CCD file missing [CloneCD] / [Disc] header"
    except OSError as e:
        return False, f"CCD validation error: {e}"


# Dispatch table - one entry per format we actually accept. If you add a
# format to COMPATIBLE_EXTS, add its validator here.
_VALIDATORS: dict[str, Callable[[str, bytes, int, bool], ValidationResult]] = {
    ".iso": _validate_iso,
    ".cue": _validate_cue,
    ".bin": _validate_bin,
    ".img": _validate_img,
    ".zip": _validate_zip,
    ".rar": _validate_rar,
    ".7z": _validate_7z,
    ".gdi": _validate_gdi,
    ".toc": _validate_toc,
    ".ccd": _validate_ccd,
}


def _format_size(size_bytes: int) -> str:
    """Human-readable size: KB/MB/GB picked by magnitude."""
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    if size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


def get_file_info(file_path: str, fast_validation: bool = True) -> dict:
    """Return a dict describing ``file_path`` for display in the GUI file list."""
    try:
        file_size = os.path.getsize(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        is_valid, validation_msg = validate_file(file_path, fast_validation)
        return {
            "name": os.path.basename(file_path),
            "path": file_path,
            "size": file_size,
            "size_str": _format_size(file_size),
            "extension": ext,
            "is_valid": is_valid,
            "validation_msg": validation_msg,
        }
    except OSError as e:
        return {
            "name": os.path.basename(file_path),
            "path": file_path,
            "size": 0,
            "size_str": "Unknown",
            "extension": os.path.splitext(file_path)[1].lower(),
            "is_valid": False,
            "validation_msg": f"Error reading file: {e}",
        }
