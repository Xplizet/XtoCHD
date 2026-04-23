"""Tests for the per-format validators and get_file_info."""

from __future__ import annotations

import os
import zipfile

import pytest

from xtochd.validators import get_file_info, validate_file


def test_missing_file_reports_invalid(tmp_path):
    missing = tmp_path / "nope.iso"
    ok, msg = validate_file(str(missing))
    assert not ok
    assert msg


def test_empty_file_reports_invalid(tmp_path):
    empty = tmp_path / "empty.iso"
    empty.write_bytes(b"")
    ok, msg = validate_file(str(empty))
    assert not ok
    assert "Empty" in msg or "small" in msg.lower()


def test_iso_fast_mode_accepts_two_kb(tmp_path):
    iso = tmp_path / "ok.iso"
    iso.write_bytes(b"\x00" * 4096)
    ok, _msg = validate_file(str(iso), fast_mode=True)
    assert ok


def test_cue_with_file_and_track_is_valid(tmp_path):
    cue = tmp_path / "game.cue"
    cue.write_text('FILE "game.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n')
    ok, _msg = validate_file(str(cue), fast_mode=True)
    assert ok


def test_cue_without_track_is_invalid(tmp_path):
    cue = tmp_path / "bad.cue"
    cue.write_text('FILE "game.bin" BINARY\n')
    ok, msg = validate_file(str(cue), fast_mode=True)
    assert not ok
    assert "CUE" in msg or "structure" in msg.lower()


def test_bin_larger_than_1k_passes(tmp_path):
    b = tmp_path / "game.bin"
    b.write_bytes(b"\x00" * 2048)
    ok, _msg = validate_file(str(b))
    assert ok


def test_bin_too_small_fails(tmp_path):
    b = tmp_path / "tiny.bin"
    b.write_bytes(b"\x00" * 100)
    ok, msg = validate_file(str(b))
    assert not ok
    assert "small" in msg.lower()


def test_zip_fast_mode_checks_magic(tmp_path):
    real_zip = tmp_path / "real.zip"
    with zipfile.ZipFile(real_zip, "w") as z:
        z.writestr("dummy.txt", "hi")
    ok, _msg = validate_file(str(real_zip), fast_mode=True)
    assert ok

    fake = tmp_path / "fake.zip"
    fake.write_bytes(b"not a zip at all")
    ok, msg = validate_file(str(fake), fast_mode=True)
    assert not ok
    assert "ZIP" in msg or "invalid" in msg.lower()


def test_zip_thorough_mode_catches_corruption(tmp_path):
    corrupt = tmp_path / "bad.zip"
    corrupt.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
    ok, _msg = validate_file(str(corrupt), fast_mode=False)
    assert not ok


def test_unknown_extension_is_treated_as_valid(tmp_path):
    other = tmp_path / "game.vhd"
    other.write_bytes(b"\x00" * 4096)
    ok, _msg = validate_file(str(other))
    assert ok


def test_get_file_info_structure(tmp_path):
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"\x00" * 4096)
    info = get_file_info(str(iso), fast_validation=True)
    assert set(info) >= {
        "name", "path", "size", "size_str", "extension",
        "is_valid", "validation_msg",
    }
    assert info["extension"] == ".iso"
    assert info["size"] == 4096
    assert info["is_valid"]


# ----- Archive validators -------------------------------------------------


def test_rar_legacy_magic_accepted(tmp_path):
    r = tmp_path / "game.rar"
    # Rar! 1A 07 00 = legacy (RAR 1.5 - 4.x) signature.
    r.write_bytes(b"Rar!\x1a\x07\x00" + b"\x00" * 64)
    ok, _msg = validate_file(str(r), fast_mode=True)
    assert ok


def test_rar_v5_magic_accepted(tmp_path):
    r = tmp_path / "game.rar"
    r.write_bytes(b"Rar!\x1a\x07\x01\x00" + b"\x00" * 64)
    ok, _msg = validate_file(str(r), fast_mode=True)
    assert ok


def test_rar_garbage_rejected(tmp_path):
    r = tmp_path / "fake.rar"
    r.write_bytes(b"NOTARAR" + b"\x00" * 100)
    ok, msg = validate_file(str(r), fast_mode=True)
    assert not ok
    assert "RAR" in msg or "invalid" in msg.lower()


def test_7z_magic_accepted(tmp_path):
    z = tmp_path / "game.7z"
    z.write_bytes(b"7z\xbc\xaf\x27\x1c" + b"\x00" * 64)
    ok, _msg = validate_file(str(z), fast_mode=True)
    assert ok


def test_7z_garbage_rejected(tmp_path):
    z = tmp_path / "fake.7z"
    z.write_bytes(b"XXXX" * 16)
    ok, msg = validate_file(str(z), fast_mode=True)
    assert not ok
    assert "7z" in msg or "invalid" in msg.lower()


# ----- Disc-index validators ----------------------------------------------


def test_gdi_with_track_count_accepted(tmp_path):
    g = tmp_path / "game.gdi"
    g.write_text(
        "3\n"
        "1 0 4 2352 track01.bin 0\n"
        "2 600 0 2352 track02.raw 0\n"
        "3 45000 4 2352 track03.bin 0\n"
    )
    ok, msg = validate_file(str(g))
    assert ok
    assert "3 tracks" in msg


def test_gdi_without_track_count_rejected(tmp_path):
    g = tmp_path / "bad.gdi"
    g.write_text("FILE \"track01.bin\" BINARY\n")
    ok, _msg = validate_file(str(g))
    assert not ok


def test_gdi_empty_rejected(tmp_path):
    g = tmp_path / "empty.gdi"
    g.write_bytes(b"")
    ok, _msg = validate_file(str(g))
    assert not ok


def test_toc_with_track_keyword_accepted(tmp_path):
    t = tmp_path / "game.toc"
    t.write_text("CD_ROM_XA\n\nTRACK MODE2_FORM_MIX\nFILE \"game.bin\" 0\n")
    ok, _msg = validate_file(str(t))
    assert ok


def test_toc_without_keywords_rejected(tmp_path):
    t = tmp_path / "bad.toc"
    t.write_text("this is not a CDRDAO file\n")
    ok, _msg = validate_file(str(t))
    assert not ok


def test_ccd_with_clonecd_header_accepted(tmp_path):
    c = tmp_path / "game.ccd"
    c.write_text("[CloneCD]\nVersion=3\n[Disc]\nTocEntries=3\n")
    ok, _msg = validate_file(str(c))
    assert ok


def test_ccd_with_disc_header_accepted(tmp_path):
    c = tmp_path / "game.ccd"
    c.write_text("[Disc]\nTocEntries=3\n")
    ok, _msg = validate_file(str(c))
    assert ok


def test_ccd_without_any_header_rejected(tmp_path):
    c = tmp_path / "bad.ccd"
    c.write_text("NOT A CLONECD FILE\n")
    ok, _msg = validate_file(str(c))
    assert not ok


# ----- COMPATIBLE_EXTS / validator dispatch coverage ---------------------


def test_every_compatible_ext_has_a_validator():
    """If a format is in COMPATIBLE_EXTS, it must have a real validator.

    Regression guard: the v2.7.0 release shipped with .rar and .7z in
    COMPATIBLE_EXTS but no registered validator, which silently passed
    every archive as valid. This test fails loudly if that ever recurs.
    """
    from xtochd.constants import COMPATIBLE_EXTS
    from xtochd.validators import _VALIDATORS

    missing = sorted(ext for ext in COMPATIBLE_EXTS if ext not in _VALIDATORS)
    assert not missing, (
        f"COMPATIBLE_EXTS includes {missing} but they have no entry in "
        f"_VALIDATORS - they would silently pass as 'File appears valid'."
    )
