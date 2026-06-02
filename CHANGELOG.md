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
- Improved the Prescience Bar so party rows use a dark track with a class-coloured fill that shrinks as Prescience expires.
- Hardened combat aura updates by reconciling full `UNIT_AURA` refreshes and rejecting malformed timer payloads.
- Moved range dimming off secure unit-button alpha changes so combat tracking only updates child visuals.
- Guarded delayed instance auto-fill/clear callbacks so stale zone transitions cannot mutate fresh frames.
- Fixed raid/Mythic+ visibility checks so disabled instance types stay hidden even when multiple toggles are off.
- Refreshed selected frames when party role/class data changes, keeping click spells and sorting aligned with current roster state.
- Guarded Blizzard context-menu favorite hooks when a menu payload has no player name.
- Fixed the Show Frame option so it can both hide and restore the frame from settings.
- Fixed active buff icon spacing after icon-size changes so icons stay evenly laid out.
- Fixed favorite-list removals so remaining favorites keep working after settings changes.
- Fixed the OmniCD support option so the requested state is saved even when OmniCD is absent.
- Fixed release packaging so public release notes use the curated changelog.
- Fixed tracked-buff persistence so disabled default buffs and saved custom spell IDs survive reloads.
- Fixed incremental aura updates so disabled tracked buffs cannot reappear between full aura refreshes.
- Fixed party-frame identity so same-name players from different realms no longer collapse into one frame.
- Fixed profile reset, copy, and switch handling so active profiles apply through one combat-safe refresh path.
- Fixed saved frame positions so invalid values fall back safely and the current position is saved on logout.

### Added

- Added static regression checks for Midnight compatibility invariants.
- Added local packaging support for reproducible manual test zips.
- Added a release preflight CI gate before public packaging and uploads.

### Known limitations

- This build still needs in-game `/reload`, group, combat, and Augmentation buff-click verification before public release.

## v1.0.23 - 25-Sep-2024

### Fixed

- Fixed a case where frames could appear only in grey.
