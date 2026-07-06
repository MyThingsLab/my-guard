# my-guard — agent instructions

You are developing **my-guard**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `mythings-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** the rule engine — evaluates an `Action` to allow / ask / deny,
  implementing mythings-core's `Policy` contract.
- **The single Engine call:** none yet — MyGuard is deterministic. If a future
  rule needs judgment (e.g. "is this diff risky?"), that becomes its one Engine
  seam; keep everything else rule-based.
- **Invariants:** rules are ordered, first-match-wins, with a configurable
  default; an `ASK` collapses to `DENY` under an unattended runner. A `deny` rule
  must never silently pass. Default rules deny merge / force-push / protected-branch
  push and ask on destructive commands.
- **Backlog label:** `my-guard` (TBD).
