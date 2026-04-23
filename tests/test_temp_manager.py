"""Tests for TempFileManager lifecycle and size reporting."""

from __future__ import annotations

import os
import time

import pytest

from xtochd.temp_manager import TempFileManager


@pytest.fixture
def isolated_manager(tmp_path, monkeypatch):
    """Return a TempFileManager rooted at a pytest tmp_path, not the app dir."""
    mgr = TempFileManager()
    mgr.temp_base_dir = str(tmp_path / "temp")
    os.makedirs(mgr.temp_base_dir, exist_ok=True)
    # Drop any temp dirs the bare constructor tracked (it scanned the real
    # app dir). This keeps our assertions about ``temp_dirs`` clean.
    mgr.temp_dirs = []
    yield mgr
    mgr.cleanup_all_temp_dirs()


def test_create_temp_dir_makes_real_folder(isolated_manager):
    d = isolated_manager.create_temp_dir(prefix="unit_")
    assert os.path.isdir(d)
    assert d in isolated_manager.temp_dirs
    assert os.path.basename(d).startswith("unit_")


def test_cleanup_temp_dir_removes_it(isolated_manager):
    d = isolated_manager.create_temp_dir()
    with open(os.path.join(d, "payload.txt"), "w") as f:
        f.write("hello")
    assert isolated_manager.cleanup_temp_dir(d) is True
    assert not os.path.exists(d)
    assert d not in isolated_manager.temp_dirs


def test_cleanup_all_empties_the_tracker(isolated_manager):
    a = isolated_manager.create_temp_dir()
    b = isolated_manager.create_temp_dir()
    assert len(isolated_manager.temp_dirs) == 2
    cleaned = isolated_manager.cleanup_all_temp_dirs()
    assert cleaned == 2
    assert isolated_manager.temp_dirs == []
    assert not os.path.exists(a)
    assert not os.path.exists(b)


def test_orphan_sweep_ignores_recent(isolated_manager):
    """Directories younger than the orphan threshold stay put."""
    recent = os.path.join(isolated_manager.temp_base_dir, "chdconv_recent")
    os.makedirs(recent)
    assert isolated_manager.cleanup_orphaned_temp_dirs() == 0
    assert os.path.isdir(recent)


def test_orphan_sweep_deletes_stale(isolated_manager):
    stale = os.path.join(isolated_manager.temp_base_dir, "chdconv_stale")
    os.makedirs(stale)
    # Age it beyond the 1-hour threshold.
    old = time.time() - 60 * 60 * 3
    os.utime(stale, (old, old))
    assert isolated_manager.cleanup_orphaned_temp_dirs() == 1
    assert not os.path.exists(stale)


def test_get_temp_dir_size_counts_contents(isolated_manager):
    d = isolated_manager.create_temp_dir()
    with open(os.path.join(d, "blob.bin"), "wb") as f:
        f.write(b"\x00" * 4096)
    assert isolated_manager.get_temp_dir_size() >= 4096


def test_purge_ignores_age_and_removes_everything(isolated_manager):
    """purge_temp_base_dir is what 'Clean Temp Directory' in the Tools
    menu calls. It must remove even freshly-created subdirs (the whole
    reason the age-gated orphan sweep is not used there)."""
    recent = os.path.join(isolated_manager.temp_base_dir, "chdconv_fresh")
    os.makedirs(recent)
    # Populate so we know it has content, not an empty shell.
    with open(os.path.join(recent, "blob.bin"), "wb") as f:
        f.write(b"\x00" * 1024)
    assert isolated_manager.cleanup_orphaned_temp_dirs() == 0
    assert os.path.isdir(recent)
    assert isolated_manager.purge_temp_base_dir() == 1
    assert not os.path.exists(recent)


def test_purge_skips_regular_files(isolated_manager):
    """A stray file in temp/ shouldn't trip up purge_temp_base_dir."""
    stray = os.path.join(isolated_manager.temp_base_dir, "README.txt")
    with open(stray, "w") as f:
        f.write("not a temp dir")
    # Also drop an actual temp subdir.
    d = os.path.join(isolated_manager.temp_base_dir, "chdconv_x")
    os.makedirs(d)
    assert isolated_manager.purge_temp_base_dir() == 1
    assert os.path.isfile(stray)  # file preserved
    assert not os.path.exists(d)


def test_format_size_readable_units():
    assert TempFileManager.format_size(0) == "0 B"
    assert TempFileManager.format_size(500).endswith("B")
    assert TempFileManager.format_size(2048).endswith("KB")
    assert TempFileManager.format_size(5 * 1024 * 1024).endswith("MB")
    assert TempFileManager.format_size(3 * 1024**3).endswith("GB")
