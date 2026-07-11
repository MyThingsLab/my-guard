from __future__ import annotations

import os
import shlex
import subprocess
from typing import Protocol

from mythings.policy import Action, Decision

# The escalation seam.
#
# A rule (or the engine judge) answering ASK means "a human should confirm this".
# Under an unattended runner there was nobody to confirm, so every caller's
# `PolicyResult.under(unattended=True)` collapsed ASK to DENY -- correct, but it
# meant the fleet could never do anything that needed a human's blessing, and the
# human was never actually asked. An ask channel is what a human answers through.
#
# Guard deliberately knows nothing about *how* the human is reached. It runs a
# command and reads its exit code. MyTelegramBot's `mytelegrambot ask` already
# speaks exactly this contract (exit 0 = allow, non-zero = deny/timeout), but so
# would a mail script, an SMS gateway, or `read -p` in a terminal. That keeps this
# a CLI hand-off -- the fleet's normal cross-tool relationship -- rather than a
# package dependency from the rule engine onto a comms tool, which would invert
# the dependency direction (MyTelegramBot imports MyGuard, never the reverse).
#
# Configured by environment, not by argument, because the ~15 places across the
# fleet that construct a Guard all do so as `policy or Guard()` -- a default with
# nowhere to thread a channel through. The env var is read once, where the Guard
# is built, and an absent one means the previous behavior exactly.
ASK_COMMAND_ENV = "MYTHINGS_ASK_CMD"
ASK_TIMEOUT_ENV = "MYTHINGS_ASK_TIMEOUT"

# Long enough for a human to see a phone notification and answer; short enough
# that an unattended worker cannot be wedged by one indefinitely. The command is
# itself expected to bound its own wait (`mytelegrambot ask --timeout`); this is
# the backstop for one that does not.
DEFAULT_ASK_TIMEOUT = 330.0


class AskChannel(Protocol):
    # Returns the human's decision. Must never return ASK: an ask channel that
    # cannot resolve an ASK has failed, and a failure is a DENY.
    def __call__(self, action: Action) -> Decision: ...


class SubprocessAsk:
    # Fail-closed is the whole contract. A missing command, a non-zero exit, a
    # timeout, a crash, an un-launchable binary: every one of them is a DENY. The
    # only path to ALLOW is the command exiting 0, which is a human having said so.
    def __init__(self, command: str, *, timeout: float = DEFAULT_ASK_TIMEOUT) -> None:
        self.command = command
        self.timeout = timeout

    def __call__(self, action: Action) -> Decision:
        import json

        argv = [
            *shlex.split(self.command),
            "--action-kind",
            action.kind,
            "--payload-json",
            json.dumps(action.payload),
        ]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            # Includes TimeoutExpired and a command that does not exist. Never let
            # a broken ask channel become an ALLOW.
            print(f"myguard: ask channel failed, denying: {type(exc).__name__}")
            return Decision.DENY
        if proc.returncode != 0:
            return Decision.DENY
        return Decision.ALLOW


def ask_channel_from_env(env: dict[str, str] | None = None) -> AskChannel | None:
    # No command configured -> no channel -> Guard keeps returning ASK and every
    # caller collapses it to DENY exactly as before. Wiring the fleet's human back
    # into the loop is therefore one environment variable, and unsetting it is a
    # complete rollback.
    env = os.environ if env is None else env
    command = env.get(ASK_COMMAND_ENV, "").strip()
    if not command:
        return None
    try:
        timeout = float(env.get(ASK_TIMEOUT_ENV, "") or DEFAULT_ASK_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_ASK_TIMEOUT
    return SubprocessAsk(command, timeout=timeout)
