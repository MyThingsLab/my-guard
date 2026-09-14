# Changelog

All notable changes to `my-guard` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semver](https://semver.org/), per the rules in `RELEASE.md`.

## [Unreleased]

### Added

- Per-project protected-path rules (#14). A project may ship a data-only
  `.my-guard/rules.json` at its root declaring `deny_edit` / `ask_edit` globs,
  discovered by walking up from the working directory. The fleet-wide rules stay
  command-shaped; this covers the path-shaped protections specific to one repo
  (generated files, schemas, CI config). Project rules combine with the fleet
  rules by severity, so they may only ever *tighten* — no project rule can turn a
  fleet `DENY` into an `ASK`. Additive and off by default: with no rule file
  present, behavior is unchanged.

## [1.0.0] - 2026-07-20

First stable release. Baseline of the rule engine as it already existed:
`Action` evaluation to allow/ask/deny, the ASK channel, and the fail-safe
default for unrecognised action kinds (#12/#15/#16). No behavior changes in
this release — it exists to establish the tag `my-dashboard` and `my-fleet`
pin against. Adopts the v1 release contract (`RELEASE.md`) and pins its own
`my-things-core` dependency to `@v1.0.0` instead of floating on `@main`.
