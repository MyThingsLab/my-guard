# my-guard — agent instructions

You are developing **my-guard**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** the rule engine — evaluates an `Action` to allow / ask / deny,
  implementing my-things-core's `Policy` contract.
- **The single Engine call:** optional, opt-in via `Guard(engine=...)` (defaults
  to `None` — fully deterministic, zero behavior change). Fires only when no
  explicit rule matches: classifies the action as `ALLOW`/`ASK`/`DENY` in one
  word. Never second-guesses an explicit rule match — deny/ask rules are always
  final. An unparseable/empty reply (including a misconfigured or failing
  engine) fails safe to `ASK`, never to the permissive default.
- **Invariants:** rules are ordered, first-match-wins, with a configurable
  default; an unanswered `ASK` collapses to `DENY` under an unattended runner. A
  `deny` rule must never silently pass. Default rules deny merge / force-push /
  protected-branch push and ask on destructive commands.
- **The ask channel — how a human answers an `ASK`.** An `ASK` means "a human
  should confirm this", but under an unattended runner there was nobody to ask, so
  every caller's `PolicyResult.under(unattended=True)` collapsed it to `DENY` and
  the human was *never actually asked*. `myguard.ask` is the seam that closes that
  loop: `Guard` runs a configured command and reads its **exit code — 0 is the
  human's ALLOW, anything else is a DENY**.

  `Guard` deliberately knows nothing about *how* the human is reached. MyTelegramBot's
  `mytelegrambot ask` already speaks exactly this contract, but so would a mail
  script or a terminal prompt. That keeps this a **CLI hand-off**, the fleet's normal
  cross-tool relationship — not a package dependency from the rule engine onto a
  comms tool, which would invert the direction (MyTelegramBot imports MyGuard, never
  the reverse).

  Configured by **environment, not argument** (`MYTHINGS_ASK_CMD`, and
  `MYTHINGS_ASK_TIMEOUT`), because the ~15 places across the fleet that build a
  policy do so as `policy or Guard()` — a default with nowhere to thread a channel
  through. One variable wires every one of them; unsetting it is a complete
  rollback to the previous behavior, byte for byte.

  Two rules this must never break:
  - **Fail closed, always.** A missing binary, a crash, a timeout, a non-zero exit
    — every one is a `DENY`. The *only* path to `ALLOW` is the command exiting 0.
  - **A channel may resolve an open question, never reopen a settled one.** Only
    `ASK` is escalated. An `ALLOW` or a `DENY` is the rule engine having already
    made up its mind, and routing those past a channel would let a buggy or
    compromised one *widen* the policy — turning a `deny` rule into an allow.
- **Backlog label:** `my-guard` (TBD).
