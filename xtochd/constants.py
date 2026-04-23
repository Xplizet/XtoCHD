"""Extension sets and format-priority tables used across the app.

These live in one place so scanner, validator, worker, and GUI all agree on
which files are "disc images," which are "archives," and which index format
wins when a single disc ships multiple manifests (e.g. Dreamcast dumps that
carry both .cue and .gdi).
"""

from __future__ import annotations

from typing import Final

# Every file type we accept as input (directly or inside an archive).
#
# This set is intentionally narrow: every entry must be a format that
# `chdman createcd` handles natively. Extensions that would need a
# different subcommand (createhd/createdvd/createld) or that chdman
# doesn't understand at all are omitted on purpose, because quietly
# accepting them was resulting in silent conversion failures.
#
# Removed in v2.7.1 after an audit:
#   .nrg   - Nero image, chdman has no parser
#   .vcd   - Video CD descriptor, not a chdman input
#   .cdr   - Apple raw CD, chdman can't read it
#   .hdi   - Anex86 hard-disk image, needs `createhd`
#   .vhd   - Microsoft/VirtualPC disk, needs `createhd`
#   .vmdk  - VMware disk, not supported by chdman as of 0.287
#   .dsk   - Generic disk image, needs `createhd`
#   .chd   - would trigger a conversion of an already-converted file
COMPATIBLE_EXTS: Final[frozenset[str]] = frozenset({
    ".cue", ".bin", ".iso", ".img", ".gdi", ".toc", ".ccd",
    ".zip", ".rar", ".7z",
})

# Archive containers we know how to crack open. .zip is handled via stdlib
# zipfile; .rar/.7z via Windows' bundled bsdtar (libarchive).
ARCHIVE_EXTS: Final[frozenset[str]] = frozenset({".zip", ".rar", ".7z"})

# Disc image extensions the conversion scanner recognises.
DISK_IMAGE_EXTS: Final[frozenset[str]] = frozenset({".cue", ".bin", ".iso", ".img"})

# Index ("manifest") formats - describe a disc layout; chdman reads them and
# opens the referenced track files itself. Never feed chdman a standalone
# track .bin when an index lives beside it: chdman 0.287 spins forever on
# bare tracks because it has no pregap / track-type context.
INDEX_EXTS: Final[frozenset[str]] = frozenset({".cue", ".gdi", ".toc", ".ccd"})

# Raw track / subchannel files referenced by an index.
TRACK_EXTS: Final[frozenset[str]] = frozenset({".bin", ".img", ".sub", ".raw"})

# When a single disc ships multiple index formats, keep one - chdman only
# needs one to reconstruct the whole disc. Preference is by how universally
# chdman handles each format; .cue first because it's the richest manifest.
INDEX_PRIORITY: Final[tuple[str, ...]] = (".cue", ".gdi", ".toc", ".ccd")

# Buffer sizes used during lightweight validation of disc-image headers.
ISO_9660_SIGNATURE: Final[bytes] = b"CD001\x01"
ISO_MIN_SIZE_BYTES: Final[int] = 2048
ISO_FULL_SCAN_BYTES: Final[int] = 32 * 1024
CUE_FAST_READ_BYTES: Final[int] = 512
CUE_FULL_READ_BYTES: Final[int] = 1024
BIN_MIN_SIZE_BYTES: Final[int] = 1024
IMG_MIN_SIZE_BYTES: Final[int] = 1024
ZIP_MAGIC: Final[bytes] = b"PK\x03\x04"

# Archive magic bytes. RAR has two signatures (legacy + RAR5). 7-Zip has one.
RAR_MAGIC_LEGACY: Final[bytes] = b"Rar!\x1a\x07\x00"
RAR_MAGIC_V5: Final[bytes] = b"Rar!\x1a\x07\x01\x00"
SEVENZIP_MAGIC: Final[bytes] = b"7z\xbc\xaf\x27\x1c"

# Text-sniff sizes for disc-index formats.
GDI_READ_BYTES: Final[int] = 64     # GDI headers are tiny: first line = track count
TOC_READ_BYTES: Final[int] = 512
CCD_READ_BYTES: Final[int] = 256

# How long a temp subdirectory from a previous run has to be idle before the
# startup sweep deletes it as orphaned.
ORPHAN_TEMP_AGE_SECONDS: Final[int] = 60 * 60
