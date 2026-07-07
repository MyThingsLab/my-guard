# my-guard — agent instructions

You are developing **my-guard**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `mythings-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** the rule engine — evaluates an `Action` to allow / ask / deny,
  implementing mythings-core's `Policy` contract.
- **The single Engine call:** optional, opt-in via `Guard(engine=...)` (defaults
  to `None` — fully deterministic, zero behavior change). Fires only when no
  explicit rule matches: classifies the action as `ALLOW`/`ASK`/`DENY` in one
  word. Never second-guesses an explicit rule match — deny/ask rules are always
  final. An unparseable/empty reply (including a misconfigured or failing
  engine) fails safe to `ASK`, never to the permissive default.
- **Invariants:** rules are ordered, first-match-wins, with a configurable
  default; an `ASK` collapses to `DENY` under an unattended runner. A `deny` rule
  must never silently pass. Default rules deny merge / force-push / protected-branch
  push and ask on destructive commands.
- **Backlog label:** `my-guard` (TBD).
