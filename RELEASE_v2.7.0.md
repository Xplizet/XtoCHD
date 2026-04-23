# What's New in v2.7.0

This release is a mix of real bug fixes that prevented conversions from completing, a tightening of what XtoCHD claims to support, and a ground-up redesign of the main window.

## chdman hang fix for latest MAME builds

Recent MAME chdman releases (0.28x and up) broke the existing subprocess handling in XtoCHD. The reported symptom: the file unzipped to temp, a 0 KB `.chd` appeared, chdman sat at a low CPU percentage, and after 10+ minutes nothing completed.

- The conversion path now uses `subprocess.Popen` with `stdin=DEVNULL` and drains stdout/stderr on background threads. Newer chdman emits progress on stderr continuously and would fill a Windows pipe buffer, deadlocking the old `subprocess.run(capture_output=True)` call.
- `stdin=DEVNULL` also guarantees chdman never blocks on an interactive prompt that has no one to answer it.
- The Stop Conversion button now actually stops chdman. The worker holds a reference to the running subprocess and kills its full process tree on cancel (`taskkill /F /T` on Windows, `terminate()` then `kill()` elsewhere).

## Supported input formats, honestly this time

XtoCHD historically listed seventeen accepted extensions. After audit, eight of them were never actually handled by the conversion pipeline and would silently fail. The file dialog, drag-drop, and folder scanner now only accept formats that `chdman createcd` genuinely supports:

- **Kept**: `.cue`, `.bin`, `.iso`, `.img`, `.gdi`, `.toc`, `.ccd`, plus `.zip` / `.rar` / `.7z` archives containing any of the above.
- **Removed**: `.chd` (would spin up a conversion on an already-converted file), `.nrg`, `.vcd`, `.cdr` (chdman has no parser), `.hdi`, `.vhd`, `.vmdk`, `.dsk` (hard-disk formats; need `createhd`, not `createcd`).

If support for hard-disk images is added later, the conversion dispatch will need to pick between `createcd`, `createhd`, `createdvd`, and `createld` based on the input. For now, the supported set is narrow but every listed format actually works.

## Real validators for every accepted format

Previously only `.iso`, `.cue`, `.bin`, `.img`, and `.zip` had validators. `.rar`, `.7z`, `.gdi`, `.toc`, `.ccd` fell through to a default "File appears valid" branch, meaning the Fast / Thorough toggle was a no-op for those formats and broken archives sailed straight through to chdman.

New validators:

- `.rar`: both legacy (`Rar!\x1a\x07\x00`) and RAR5 (`Rar!\x1a\x07\x01\x00`) magic signatures.
- `.7z`: 7-Zip magic (`7z\xbc\xaf\x27\x1c`).
- `.gdi`: sniffs the first line for the track count that every valid GDI starts with.
- `.toc`: looks for CDRDAO session/track keywords (`CD_DA`, `CD_ROM_XA`, `TRACK`, etc.).
- `.ccd`: looks for the `[CloneCD]` or `[Disc]` INI section header.

A regression test (`test_every_compatible_ext_has_a_validator`) now fails loudly if anyone adds a format to `COMPATIBLE_EXTS` without also registering a validator.

## `.rar` and `.7z` archive support

In addition to `.zip`, XtoCHD now accepts `.rar` and `.7z` as input. Extraction uses the `bsdtar` (libarchive) binary that Windows 10 1803 and later include at `C:\Windows\System32\tar.exe`. No extra binary is bundled; nothing is installed.

## Sibling-index filter (fixes the old "hang" case)

A single disc image is often shipped with more than one manifest (a `.cue` plus a `.gdi`, for example). Previous versions tried to convert both and triggered chdman's spin-forever behaviour on the redundant one. The new filter keeps exactly one index per directory, in this order of preference: `.cue`, `.gdi`, `.toc`, `.ccd`. Raw track files (`.bin`, `.img`, `.sub`, `.raw`) that sit alongside a chosen index are dropped, because chdman reads them through the index itself.

## Summary fixes

- The "Original total size" and per-file size figures were previously measured from the `.cue` or `.gdi` text manifest (a few hundred bytes), producing a meaningless compression ratio. The summary now sums every non-`.chd` file in the disc directory, so numbers reflect the actual disc size.
- The per-file `SUCCESSFULLY CONVERTED` / `SKIPPED` / `FAILED` blocks appear at the top of the summary, before the aggregate counts and size statistics.

## Main window redesigned

- **Top toolbar** for primary actions: `Add File`, `Add Folder`, `Fast Validation` toggle, chdman status badge (green `chdman: ✓ Ready` / red `chdman: ✗ Missing`), and a `Log` toggle that hides or shows the right pane.
- **Path rows** now have inline trailing actions in the QLineEdit itself (Browse, Open Folder) instead of external buttons; the field takes all the horizontal space.
- **Custom file-list rows**: coloured format badge (indigo for archives, amber for disc-index, teal for disc data), filename, right-aligned size. Colour encodes format family, not validation state — so the file list reads well for colour-blind users too.
- **"Absence is good" status**: valid files show nothing on the right of the row. A red `INVALID` pill or grey `validating...` label only appears when the file needs attention, so a healthy list reads as a calm column of colourful badges.
- **Live list summary** replaces the old "Files to Convert:" label: `2/2 selected · 416 MB · All valid`, updated as checks change and validation completes.
- **Collapsible File Information panel** hidden until a row is selected; remembers its collapsed/expanded state across runs.
- **Single morphing action button**: one full-width green `Start Conversion` button when idle; swaps to a red `Stop Conversion` during a run.
- **Draggable splitter** between the controls and the log pane, with the position persisted across runs. Default is roughly 73/27 so the log doesn't dominate at idle.

## "Re-validate on toggle" actually re-validates now

Previously, flipping the Fast / Thorough toggle emitted a "Rescanning files..." log line and then silently did nothing, because the cached validation results from the previous mode were never cleared. The cache is now cleared on mode change, every row visually resets to a pending state, and a closing log line (`Re-validation complete (Thorough mode): 4 valid, 1 invalid.`) tells you when the background worker is done.

## "Clean Temp Directory" actually cleans

The Tools menu action was wired to the same "orphan sweep" the startup path uses, which only removes subdirectories older than one hour. Clicking the menu item right after a crashed conversion correctly said "nothing to clean up" while half a gigabyte of extracted files sat in `temp/`. It now removes every subdirectory under `temp/` regardless of age (guarded against running while a conversion is in flight).

## chdman update

Bundled `chdman.exe` is now from the MAME 0.287 release. `MAME-LICENSE.txt` ships next to it in the release ZIP for GPL compliance, and the README points at the upstream source.

## Project layout

The old 2469-line `main.py` has been reorganised into a small `xtochd/` package:

- `xtochd/constants.py`: extension sets and format-priority tables
- `xtochd/stats.py`: `ConversionStats` dataclass
- `xtochd/temp_manager.py`: crash-proof temp-directory management
- `xtochd/theme.py`: light / dark Qt stylesheets
- `xtochd/validators.py`: per-format validation and the conversion-candidate filter
- `xtochd/workers.py`: `ConversionWorker`, `ScanWorker`, `ValidationWorker`

`main.py` (about 1100 lines) contains only the `CHDConverterGUI` main window and the `if __name__ == "__main__"` bootstrap, so `build_exe.py` and `build.bat` still work without changes.

## Tests

A pytest suite covers the pure helpers: 50 tests across the conversion-candidate filter, every per-format validator, archive magic-byte sniffs, disc-index text sniffs, the `TempFileManager` lifecycle (including the new force-purge), and the `ConversionStats` math. Full suite runs in well under a second with no PyQt or chdman dependency.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Cleanup

- Removed the unused `InputSelectionDialog` class (it also contained a latent `NameError` that would have crashed it if anything had ever instantiated it).
- Removed the unused `SYSTEM_PATTERNS` table.
- Removed six redundant function-scope imports that shadowed the module-level ones.
- Removed the dead sibling-checkbox rendering the old delegate did (which produced double checkboxes per row on some systems).

## Installation

- Extract the ZIP file and run `XtoCHD.exe`.
- `chdman.exe` is included in the release, alongside `MAME-LICENSE.txt` covering its terms (MAME is GPL-2.0; source is at https://github.com/mamedev/mame).
- Windows 10 1803 or later is required for `.rar` and `.7z` extraction.

## Documentation

- [Full Changelog](CHANGELOG.md)
- [README](README.md)

---

Thank you for using XtoCHD.
