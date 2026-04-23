"""Tests for the ConversionStats dataclass - derived-property math mostly."""

from __future__ import annotations

from xtochd.stats import ConversionStats, SuccessfulFile


def test_success_rate_none_when_nothing_processed():
    s = ConversionStats(total_files=5)
    assert s.success_rate is None


def test_success_rate_percentage():
    s = ConversionStats(
        successful_conversions=3,
        failed_conversions=1,
        skipped_files=0,
    )
    assert s.success_rate == 75.0


def test_total_processed_sums_the_three_counters():
    s = ConversionStats(
        successful_conversions=2,
        failed_conversions=1,
        skipped_files=4,
    )
    assert s.total_processed == 7


def test_compression_ratio_none_without_original_size():
    s = ConversionStats()
    assert s.compression_ratio is None


def test_compression_ratio_percentage():
    s = ConversionStats(original_size=1000, compressed_size=200)
    assert s.compression_ratio == 80.0


def test_successful_files_list_holds_dataclasses():
    s = ConversionStats()
    s.successful_files.append(
        SuccessfulFile(name="a.chd", original_size_mb=1000.0, compressed_size_mb=200.0)
    )
    assert s.successful_files[0].name == "a.chd"
    assert s.successful_files[0].original_size_mb == 1000.0
