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

## T3 Medium / Low

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

## Parking

### EVA-P-001: Cache Ebon Might progress data if aura polling becomes measurable

- Evidence: `CreateProgressBar` `OnUpdate` scans player auras for both Ebon
  Might spell IDs every frame.
- Promote when: profiling or in-game reports show measurable CPU cost during
  combat.
- Potential direction: cache expiration/duration from `UNIT_AURA` and let
  `OnUpdate` only update progress arithmetic/rendering.
- Verification: compare aura API call counts and frame time before/after.
