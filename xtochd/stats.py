"""Typed conversion stats, accumulated by ConversionWorker and rendered by its summary."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SuccessfulFile:
    """One entry in the "SUCCESSFULLY CONVERTED" section of the summary."""
    name: str
    original_size_mb: float
    compressed_size_mb: float


@dataclass
class ConversionStats:
    """Mutable per-run counters. Owned by a single ConversionWorker instance."""

    total_files: int = 0
    successful_conversions: int = 0
    failed_conversions: int = 0
    skipped_files: int = 0

    original_size: int = 0  # bytes
    compressed_size: int = 0  # bytes

    successful_files: list[SuccessfulFile] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    skipped_files_list: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.successful_conversions + self.failed_conversions + self.skipped_files

    @property
    def success_rate(self) -> float | None:
        """Percentage of processed files that converted successfully, or None if nothing ran."""
        if self.total_processed == 0:
            return None
        return self.successful_conversions / self.total_processed * 100

    @property
    def compression_ratio(self) -> float | None:
        """Bytes saved as a percentage of the original, or None if nothing was measured."""
        if self.original_size == 0:
            return None
        return (1 - self.compressed_size / self.original_size) * 100
