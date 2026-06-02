# EvokerAug Audit

This is the durable backlog for the Midnight revival of EvokerAug. Keep entries
evidence-backed and actionable; do not add session notes, commit hashes, or
speculative cleanup ideas without a concrete failure path.

## Coverage Map

- Core runtime: secure party frames, aura tracking, buff timers, group updates,
  visibility lifecycle, combat lockdown paths, and menu hooks.
- Persistence/config: AceDB defaults, profile callbacks, favorites, custom
  spell state, OmniCD support state, and saved frame position.
- UI/options: frame visibility controls, minimap/compartment actions, buff icon
  layout, Prescience bar behavior, spell dropdown labels, and public copy.
- Release/config/docs: GitHub tag workflow, BigWigs packager metadata, local
  zip/junction scripts, README, TOC notes, changelog, and package contents.
- Tests: current static regression checks, Lua syntax checks, and gaps where
  behavior needs a harness or in-game verification.

## T1 Critical

### EVA-T1-001: Gate public tag releases before BigWigs Packager uploads

- Evidence: `.github/workflows/build.yml` publishes on `v*` tags through
  BigWigs Packager; `tests/test_midnight_port_static.py` and `luac5.1` checks
  exist locally but are not required by the workflow.
- Current behavior: pushing a tag can package and upload to GitHub/CurseForge/
  Wago/WoWInterface before static regressions, Lua syntax, or package-surface
  checks run.
- Impact: a broken Midnight port or dirty artifact can become a public release.
- Suggested fix direction: add a pre-packager CI job for `python -m pytest`,
  `luac5.1 -p Core\Config.lua Core\EvokerAug.lua Core\SpellList.lua`, and zip
  surface checks; make the packager job depend on it.
- Tests/verification: fail the workflow intentionally with a broken static
  invariant and confirm no packager/upload step runs; then confirm a clean tag
  reaches the packager.

## T2 High

### EVA-T2-001: Replace `buffList` default toggles with stable persisted state

- Evidence: `Core\Config.lua::addon.DefaultProfile.profile.buffList` stores
  default tracked spells; `Core\EvokerAug.lua::GetOptions` disables them by
  writing `nil`; AceDB restores missing default keys from defaults; custom
  spell rows are only rebuilt from `AllSpellList` unless `SpellListAdd` runs.
- Current behavior: disabling a default tracked buff can come back after
  reload/profile-default reapplication, while saved custom spell IDs can remain
  enabled in `buffList` but disappear from the options UI and become hard to
  remove.
- Impact: user spell tracking preferences are not reliable.
- Suggested fix direction: model tracking explicitly, for example
  `trackedSpells[spellID] = true/false` plus a saved custom-spell metadata set,
  or separate `disabledDefaultSpells` and `customSpells`; render saved custom
  IDs during options construction.
- Tests/verification: disable a default spell, reload, and confirm it stays
  disabled; add a custom spell, reload, and confirm it appears checked and can
  be removed.

### EVA-T2-002: Use stable player identity keys instead of short display names

- Evidence: `Core\EvokerAug.lua::GetCharacterName`, `AddHomePartyInfo`,
  `CreateSelectedPlayerFrame`, `GetPlayerFrameIndexByName`,
  `IsPlayerFrameByName`, `checkboxStates`, `RightMenu`, and favorites use short
  character names as state keys.
- Current behavior: realm is stripped or ignored for frame lookup, menu checked
  state, deletion, and favorite matching; `DeleteSelectedPlayerFrame` also
  leaves `false` tombstones in `checkboxStates`.
- Impact: same-name cross-realm party/raid members can collapse into one UI
  entry or secure frame, and stale checkbox keys can accumulate in clear/exit
  loops.
- Suggested fix direction: store an `identityKey` such as `Name-Realm` or
  `UnitGUID` separately from display text; key `selectedPlayerFrames`,
  `checkboxStates`, and favorites by identity; delete state entries with `nil`.
- Tests/verification: simulate or join a group with two same-name different-
  realm members and confirm both can be shown, removed, sorted, and clicked
  independently.

### EVA-T2-003: Keep favorite lists compact and normalized

- Evidence: `Core\EvokerAug.lua::MenuHandler` removes favorites with
  `table.remove`, while the options favorite-list setter writes
  `favoriPlayer[k] = nil`; `IsFavorite` and sort helpers read with `ipairs`.
- Current behavior: removing the first favorite from the options page can make
  later favorites invisible to `ipairs` and break auto-add/sort priority.
- Impact: favorites stop working for remaining entries after ordinary UI use.
- Suggested fix direction: use one representation everywhere: either a compact
  array with `table.remove`/dedupe normalization, or a keyed set by full player
  identity.
- Tests/verification: create two favorites, remove the first from options,
  reload, and confirm the second still auto-adds and sorts as a favorite.

### EVA-T2-004: Centralize profile apply/reset/switch lifecycle

- Evidence: `Core\EvokerAug.lua::OnInitialize` registers only `OnProfileReset`;
  AceDB fires `OnProfileChanged` and `OnProfileCopied`; AceDBOptions exposes
  set/copy/delete/reset profile controls; `addon:Reconfigure` mutates secure
  frames and positions without the same combat gate used by frame helpers.
- Current behavior: profile switches/copies can leave empty `charSpell` values,
  stale macro attributes, old frame layout/events, and old OmniCD state until
  reload; profile reset can run protected frame mutations from an options panel
  during combat.
- Impact: profile operations can break click macros, visible frames, and combat
  lockdown safety.
- Suggested fix direction: create one `ApplyActiveProfile` path for reset,
  copy, and switch callbacks; populate `charSpell`, refresh options, reapply
  frame/event/OmniCD state, and defer protected mutations until
  `PLAYER_REGEN_ENABLED`.
- Tests/verification: switch to a fresh profile and confirm macro dropdowns are
  populated immediately; copy a profile and confirm visible frame state updates;
  attempt reset in combat and confirm work is queued rather than forbidden.

### EVA-T2-009: Make the settings Hide Frame control a real visibility toggle

- Evidence: `frameHide` getter returns whether the container is shown, but its
  setter always calls `HideAllSubFrames`.
- Current behavior: the Hide Frame option is an inverted one-way toggle.
- Impact: users can get confusing options UI and cannot use the setting itself
  to show the frame again.
- Suggested fix direction: make the option either an execute action or a real
  show/hide toggle using `value`.
- Tests/verification: `/aug` toggle off/on should hide/show predictably.

### EVA-T2-010: Apply buff icon layout settings coherently to existing frames

- Evidence: `AddBuffIcon`/`RepositionBuffIcons` advance icon offsets by
  `buttonHeight` while icon textures use `spellIconSize`; icon-size changes
  resize existing icons but do not reposition them.
- Current behavior: icon size/frame height combinations can cause overlap or
  large gaps, and resizing active icons can leave old spacing until buffs are
  removed/re-added.
- Impact: visible buff icons can become misleading or visually broken after
  settings changes.
- Suggested fix direction: add a combat-aware apply helper for icon size, icon
  text size, and icon spacing; space icons by `spellIconSize` or an explicit
  spacing setting and call `RepositionBuffIcons` after icon-size changes.
- Tests/verification: vary frame height/icon size with multiple buffs active
  and confirm icons remain evenly spaced.

### EVA-T2-012: Wire curated changelog into release packaging

- Evidence: `CHANGELOG.md` contains user-facing Midnight notes and known
  limitations; `.pkgmeta` has `manual-changelog` commented out.
- Current behavior: the packager may publish commit-derived or incomplete
  release notes instead of the curated changelog.
- Impact: public release surfaces may omit the Midnight caveats and verification
  expectations.
- Suggested fix direction: enable `.pkgmeta` `manual-changelog` for
  `CHANGELOG.md`, or add an explicit release-note generation step.
- Tests/verification: dry-run or tag-test packaging and confirm release notes
  come from the curated changelog.

## T3 Medium / Low

### EVA-T3-002: Harden saved frame position loading and saving

- Evidence: `profile.positions` is loaded directly into `SetPoint`; drag-stop
  writes raw `GetPoint()` returns; no defensive `PLAYER_LOGOUT` save exists.
- Current behavior: corrupted or migrated SavedVariables with invalid point or
  nil offsets can error during load/reset and strand the UI.
- Impact: addon frame can become inaccessible after bad SavedVariables.
- Suggested fix direction: add `LoadPosition`/`SavePosition` helpers with
  allowed-point validation, numeric offset fallback, `GetPoint()` nil guard,
  and logout save.
- Tests/verification: corrupt `EvokerAugDB.profile.positions`, `/reload`, and
  confirm fallback to defaults.

### EVA-T3-003: Localize core spell dropdown labels and fix hardcoded typo

- Evidence: `Core\SpellList.lua::spell_list` hardcodes English macro labels and
  contains `Sourceof Magic`; custom spell options already use
  `C_Spell.GetSpellInfo`.
- Current behavior: localized clients see English core spell labels, and
  English clients see a typo in keybinding choices.
- Impact: settings UI is less trustworthy and less usable on non-English
  clients.
- Suggested fix direction: populate `charSpell` labels from
  `C_Spell.GetSpellInfo(spellID).name`, with corrected hardcoded fallback.
- Tests/verification: static test that core labels use spell info; in-game check
  keybinding dropdown labels on an English and non-English client if available.

### EVA-T3-004: Update README, TOC notes, and in-game changelog copy

- Evidence: `EvokerAug.toc` notes describe counting evokers in the zone; README
  is generic and does not describe the Midnight revival or current buff-click
  party-frame behavior; `Core\Config.lua` changelog is shorter than
  `CHANGELOG.md`.
- Current behavior: public/in-game copy does not match the current addon
  purpose or the pre-release Midnight state.
- Impact: user confusion and stale marketplace/GitHub presentation on first
  revival release.
- Suggested fix direction: align README, TOC Notes, in-game changelog, and
  marketplace-ready release copy around Augmentation buff management, Midnight
  compatibility, and required in-game verification.
- Tests/verification: grep public copy for stale "current number of evokers"
  wording and verify version/known-limitations consistency.

### EVA-T3-005: Clean local/package artifacts beyond root-level excludes

- Evidence: `scripts\package-local.ps1` excludes root repo-only directories,
  but the current zip includes nested vendored metadata such as
  `Libs/LibCustomGlow-1.0/.editorconfig`, `.luarc.json`, `.pkgmeta`, and
  `cspell.json`; nested duplicate libraries under SharedMediaWidgets are
  packaged but not loaded by its XML.
- Current behavior: manual test zips carry development metadata and unused
  nested library payloads.
- Impact: release artifacts are noisier, harder to inspect, and can grow stale
  if copied into public packaging.
- Suggested fix direction: add recursive metadata exclusions to local packaging
  and review whether nested unused library directories should be pruned or
  package-ignored.
- Tests/verification: rebuild the local zip and assert no nested repo metadata
  or unused nested library payload appears.

### EVA-T3-006: Reduce first-party global namespace leakage

- Evidence: `Core\SpellList.lua` assigns global `spell_list` and
  `AllSpellList`; `Core\EvokerAug.lua` exposes helpers such as
  `CreateProgressBar`, `RightMenu`, `MenuHandler`, and uses a generic named
  frame `MyProgressBar`.
- Current behavior: addon internals are mutable in WoW's shared global
  namespace and can collide with other addons or scripts.
- Impact: unrelated addons/scripts can overwrite EvokerAug internals or be
  overwritten by EvokerAug names.
- Suggested fix direction: localize helpers and data tables, or attach them to
  the addon namespace; use nil or namespaced frame names for internal frames.
- Tests/verification: add a static check for no bare global function/table
  assignments except intentional addon API.

### EVA-T3-007: Make OmniCD support setting persist even when OmniCD is absent

- Evidence: the OmniCD option setter writes `omniCDSupport` only when OmniCD is
  loaded or enabled; `OnEnable` reads the saved value to register frame data.
- Current behavior: if OmniCD is disabled/removed while the profile has support
  enabled, toggling EvokerAug OmniCD support off does not persist.
- Impact: stale SavedVariables and confusing UI state for users who uninstall
  OmniCD or share profiles between setups.
- Suggested fix direction: always persist the requested boolean; gate only
  reload/registration/status feedback on OmniCD availability.
- Tests/verification: simulate OmniCD unavailable, set the option false, reload,
  and confirm it remains false.

### EVA-T3-008: Add behavioral tests for stateful Lua flows

- Evidence: current `tests/test_midnight_port_static.py` is valuable but mostly
  text-search based; key risks now involve AceDB defaults, menu payloads,
  delayed callbacks, favorites, visibility truth tables, and aura update
  reconciliation.
- Current behavior: regressions in state transitions can pass syntax/static
  checks.
- Impact: future fixes can silently break user flows that static tests cannot
  execute.
- Suggested fix direction: add a lightweight Lua or Python harness that loads
  isolated Lua chunks with mocked WoW/Ace APIs for pure state transitions; keep
  in-game `/reload` verification for secure-frame behavior.
- Tests/verification: cover buff persistence, favorites, visibility truth
  table, nil menu payload, role change, nil `UNIT_AURA`, and stale callback
  generation.

### EVA-T3-009: Bound mutable paths in local PowerShell tooling

- Evidence: `scripts\package-local.ps1` accepts `OutputDirectory`, computes a
  staging path, and recursively deletes `_staging`; the install script accepts
  custom root/backup parameters for moving installed addon folders.
- Current behavior: default usage is safe, but unusual absolute or parent-path
  arguments are not explicitly constrained to the repo or intended AddOns root.
- Impact: local tooling is easier to misuse during manual packaging/install
  work.
- Suggested fix direction: resolve final paths and assert destructive
  staging/move targets stay under the intended repo output directory or WoW
  AddOns root before deleting/moving.
- Tests/verification: add script tests/dry-runs for default paths, absolute
  output paths, parent-directory traversal, existing junction, and existing
  folder backup.

## Parking

### EVA-P-001: Cache Ebon Might progress data if aura polling becomes measurable

- Evidence: `CreateProgressBar` `OnUpdate` scans player auras for both Ebon
  Might spell IDs every frame.
- Promote when: profiling or in-game reports show measurable CPU cost during
  combat.
- Potential direction: cache expiration/duration from `UNIT_AURA` and let
  `OnUpdate` only update progress arithmetic/rendering.
- Verification: compare aura API call counts and frame time before/after.
