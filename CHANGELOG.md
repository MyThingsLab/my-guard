# Changelog

## [Unreleased]
### Shipped
- pushed private to github.com/lorenzoliuzzo/my-guard; CI green incl. cross-repo install of public core
### Added/Changed
- Guard rule engine implementing Core's Policy; default rules deny merge/force/protected push, ask on destructive
- harden CI (mirror core): concurrency-cancel, paths-ignore, draft-skip, timeout
- vendor HARNESS.md + thin CLAUDE.md; drift-check test enforces it matches core's canonical harness.md
- local-first gate: pre-commit (ruff + pytest-fast) + slow marker
- added Guard(engine=...) judgment seam: on fall-through, asks the Engine to classify an unmatched Action as ALLOW/ASK/DENY in one word. Live-verified against the real claude CLI: curl-pipe-to-bash -> DENY, ls -la -> ALLOW, npm install left-pad -> ASK. 17 tests green (5 new), ruff clean
- Mechanical migration to mythings.testing: inline engine spy replaced by the shared ScriptedEngine (attribute/counter shims folded into the assertions or a local scripted() payload factory).

All notable changes to `my-guard` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semver](https://semver.org/), per the rules in `RELEASE.md`.

## [1.0.0] - 2026-07-20

First stable release. Baseline of the rule engine as it already existed:
`Action` evaluation to allow/ask/deny, the ASK channel, and the fail-safe
default for unrecognised action kinds (#12/#15/#16). No behavior changes in
this release — it exists to establish the tag `my-dashboard` and `my-fleet`
pin against. Adopts the v1 release contract (`RELEASE.md`) and pins its own
`my-things-core` dependency to `@v1.0.0` instead of floating on `@main`.
