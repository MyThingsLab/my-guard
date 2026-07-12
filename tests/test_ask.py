from __future__ import annotations

import json

import pytest
from mythings.policy import Action, Decision

from myguard.ask import (
    ASK_COMMAND_ENV,
    ASK_TIMEOUT_ENV,
    DEFAULT_ASK_TIMEOUT,
    SubprocessAsk,
    ask_channel_from_env,
)

# Fail-closed is the whole contract of this module. The only path to ALLOW is a
# command exiting 0, which is a human having said so. Everything else -- a missing
# binary, a crash, a timeout, a non-zero exit -- is a DENY.

_ACTION = Action(kind="issue-close", payload={"issue": 12, "repo": "o/r"})


def test_exit_zero_is_the_humans_allow() -> None:
    assert SubprocessAsk("true")(_ACTION) is Decision.ALLOW


def test_exit_nonzero_is_a_deny() -> None:
    # `mytelegrambot ask` exits 1 for both a denial and a timeout.
    assert SubprocessAsk("false")(_ACTION) is Decision.DENY


def test_a_command_that_does_not_exist_denies_rather_than_raising() -> None:
    # A misconfigured channel must not crash the worker, and must certainly not
    # be mistaken for approval.
    assert SubprocessAsk("definitely-not-a-real-binary-xyz")(_ACTION) is Decision.DENY


def test_a_timeout_denies() -> None:
    assert SubprocessAsk("sleep 5", timeout=0.1)(_ACTION) is Decision.DENY


def test_the_action_is_passed_through_as_the_documented_cli_contract(
    tmp_path: object,
) -> None:
    # Guard hands the channel an Action; the channel must render it as the
    # --action-kind/--payload-json pair `mytelegrambot ask` declares.
    import sys

    script = (
        "import sys, json;"
        "kind = sys.argv[sys.argv.index('--action-kind') + 1];"
        "payload = json.loads(sys.argv[sys.argv.index('--payload-json') + 1]);"
        "sys.exit(0 if kind == 'issue-close' and payload['issue'] == 12 else 3)"
    )

    channel = SubprocessAsk(f"{sys.executable} -c {json.dumps(script)}")

    assert channel(_ACTION) is Decision.ALLOW


def test_no_env_var_means_no_channel_at_all() -> None:
    # The rollback path, and today's behavior: no channel, so Guard keeps returning
    # ASK and every caller collapses it to DENY exactly as before.
    assert ask_channel_from_env({}) is None
    assert ask_channel_from_env({ASK_COMMAND_ENV: "   "}) is None


def test_env_var_builds_a_channel() -> None:
    channel = ask_channel_from_env({ASK_COMMAND_ENV: "mytelegrambot ask"})

    assert isinstance(channel, SubprocessAsk)
    assert channel.command == "mytelegrambot ask"
    assert channel.timeout == DEFAULT_ASK_TIMEOUT


def test_the_timeout_is_configurable_and_a_bad_one_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = ask_channel_from_env({ASK_COMMAND_ENV: "x", ASK_TIMEOUT_ENV: "60"})
    assert good.timeout == 60.0

    # A typo in an env var must not take out the fleet: fall back, don't crash.
    bad = ask_channel_from_env({ASK_COMMAND_ENV: "x", ASK_TIMEOUT_ENV: "not-a-number"})
    assert bad.timeout == DEFAULT_ASK_TIMEOUT
