# EvokerAug Changelog

## v1.0.24-midnight.1 - 02-Jun-2026

### Fixed

- Updated Retail metadata for Midnight 12.0.5/12.0.7 clients.
- Switched tracked buff detection from localized aura names to spell IDs.
- Guarded aura timer math against Midnight secret-tagged numeric values.
- Deferred protected party frame creation, deletion, sorting, visibility, and spell attribute updates while in combat.
- Fixed class-token handling for non-English clients.
- Removed LFG context-menu hooks from the local Midnight port to reduce taint risk.
- Fixed modified click casting by pairing secure spell attributes with secure type attributes.
- Fixed party, favorite, and right-click menu unit mapping so party members keep their real `partyN`, `raidN`, or `player` unit tokens.
- Fixed frame reset/deletion cleanup so buff timers and icon regions are cleared instead of surviving detached frames.
- Fixed custom spell option icons, class-colour fallback, OmniCD reload handling, and combat-gated frame-height/progress-bar settings.
- Fixed local package output so backup folders are excluded from manual test zips.
- Changed the default frame state to unlocked so new profiles can position the frame immediately, then lock it from the right-click menu.

### Added

- Added static regression checks for Midnight compatibility invariants.
- Added local packaging support for reproducible manual test zips.

### Known limitations

- This build still needs in-game `/reload`, group, combat, and Augmentation buff-click verification before public release.

## v1.0.23 - 25-Sep-2024

### Fixed

- Fixed a case where frames could appear only in grey.
