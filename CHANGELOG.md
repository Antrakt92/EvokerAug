# EvokerAug Changelog

## v1.0.24-midnight.1 - 02-Jun-2026

### Fixed

- Updated Retail metadata for Midnight 12.0.5/12.0.7 clients.
- Switched tracked buff detection from localized aura names to spell IDs.
- Guarded aura timer math against Midnight secret-tagged numeric values.
- Deferred protected party frame creation, deletion, sorting, visibility, and spell attribute updates while in combat.
- Fixed class-token handling for non-English clients.
- Removed LFG context-menu hooks from the local Midnight port to reduce taint risk.

### Added

- Added static regression checks for Midnight compatibility invariants.
- Added local packaging support for reproducible manual test zips.

### Known limitations

- This build still needs in-game `/reload`, group, combat, and Augmentation buff-click verification before public release.

## v1.0.23 - 25-Sep-2024

### Fixed

- Fixed a case where frames could appear only in grey.
