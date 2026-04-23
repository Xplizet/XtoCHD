"""Tests for ``filter_conversion_candidates``.

This is the function that prevents chdman 0.287 from spinning forever on
bare .bin tracks. A regression here = the tool hangs. Cover every path:
cue+bin, cue+gdi, orphan tracks, standalone iso, multi-directory archives.
"""

from __future__ import annotations

from xtochd.validators import filter_conversion_candidates


def _paths(*names: str) -> list[str]:
    """Helper: turn 'dir/file.cue' strings into posix-style paths."""
    return list(names)


def test_cue_with_bin_tracks_drops_bins():
    """Classic CUE+BIN disc: we should hand chdman only the .cue."""
    entries = _paths(
        "MvC2/MvC2.cue",
        "MvC2/MvC2 (Track 1).bin",
        "MvC2/MvC2 (Track 2).bin",
        "MvC2/MvC2 (Track 3).bin",
    )
    assert filter_conversion_candidates(entries) == ["MvC2/MvC2.cue"]


def test_cue_beats_gdi_when_both_present():
    """When a Dreamcast dump ships both, keep .cue - it's higher priority."""
    entries = _paths(
        "disc/game.cue",
        "disc/game.gdi",
        "disc/game (Track 1).bin",
    )
    assert filter_conversion_candidates(entries) == ["disc/game.cue"]


def test_gdi_alone_is_kept():
    entries = _paths("disc/game.gdi", "disc/game_track01.raw")
    kept = filter_conversion_candidates(entries)
    assert kept == ["disc/game.gdi"]


def test_orphan_bin_without_sibling_index_is_kept():
    """A .bin with no cue/gdi/toc/ccd nearby gets passed through - user intent."""
    entries = _paths("loose/game.bin")
    assert filter_conversion_candidates(entries) == ["loose/game.bin"]


def test_iso_passes_through():
    entries = _paths("iso/game.iso", "iso/extra.bin")
    kept = filter_conversion_candidates(entries)
    assert "iso/game.iso" in kept
    # .bin is orphaned (no index in this dir) so it's also kept.
    assert "iso/extra.bin" in kept


def test_multiple_discs_in_different_dirs_each_get_one_index():
    """Two independent discs; we should pick one index per directory."""
    entries = _paths(
        "disc_a/a.cue",
        "disc_a/a.bin",
        "disc_b/b.cue",
        "disc_b/b.gdi",
        "disc_b/b_track01.bin",
    )
    kept = set(filter_conversion_candidates(entries))
    assert kept == {"disc_a/a.cue", "disc_b/b.cue"}


def test_empty_input():
    assert filter_conversion_candidates([]) == []


def test_only_tracks_no_index_keeps_everything():
    """Pile of loose bins with no index: defer to the user."""
    entries = _paths("loose/a.bin", "loose/b.bin")
    assert set(filter_conversion_candidates(entries)) == set(entries)


def test_toc_also_suppresses_sibling_tracks():
    entries = _paths("x/game.toc", "x/game.bin", "x/game.sub")
    assert filter_conversion_candidates(entries) == ["x/game.toc"]


def test_ccd_keeps_only_index_not_img_sub():
    entries = _paths("y/game.ccd", "y/game.img", "y/game.sub")
    assert filter_conversion_candidates(entries) == ["y/game.ccd"]
