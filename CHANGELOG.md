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
