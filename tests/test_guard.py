import pytest
from mythings.engine import EngineRequest, EngineResult
from mythings.policy import Action, Decision, Policy, PolicyResult

from myguard import Guard, Rule
from myguard.rules import MERGE_ACTION


class _SpyEngine:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        return EngineResult(text=self.reply)


def bash(command: str) -> Action:
    return Action(kind="bash", payload={"command": command})


def test_guard_satisfies_the_policy_protocol() -> None:
    assert isinstance(Guard(), Policy)


def test_unmatched_action_falls_through_to_default() -> None:
    g = Guard()
    result = g.evaluate(bash("ls -la"))
    assert result.decision is Decision.ALLOW
    assert result.rule == "default"


def test_default_can_be_deny_for_a_locked_down_runner() -> None:
    g = Guard(rules=[], default=Decision.DENY)
    assert g.evaluate(bash("echo hi")).decision is Decision.DENY


def test_merge_is_denied() -> None:
    for cmd in ("git merge feature", "gh pr merge 12 --squash"):
        r = Guard().evaluate(bash(cmd))
        assert r.decision is Decision.DENY
        assert r.rule == "no_merge"


def test_force_push_is_denied() -> None:
    r = Guard().evaluate(bash("git push --force origin feature"))
    assert r.decision is Decision.DENY
    assert r.rule == "no_force_push"


def test_push_to_main_is_denied() -> None:
    r = Guard().evaluate(bash("git push origin main"))
    assert r.decision is Decision.DENY
    assert r.rule == "protect_main"


def test_destructive_command_asks() -> None:
    r = Guard().evaluate(bash("rm -rf build/"))
    assert r.decision is Decision.ASK
    assert r.rule == "confirm_destructive"


def test_ask_collapses_to_deny_when_unattended() -> None:
    r = Guard().evaluate(bash("git reset --hard HEAD~1"))
    assert r.under(unattended=True) is Decision.DENY
    assert r.under(unattended=False) is Decision.ASK


def test_first_matching_rule_wins() -> None:
    ask_all = Rule("catch_all", Decision.ASK, "catch", kind="bash")
    g = Guard(rules=[ask_all, *[]])
    assert g.evaluate(bash("git push --force")).rule == "catch_all"


def test_rule_kind_scoping() -> None:
    r = Rule("only_bash", Decision.DENY, "x", kind="bash")
    assert r.applies(Action(kind="bash"))
    assert not r.applies(Action(kind="write_file"))


def test_evaluate_returns_reason_and_rule() -> None:
    r = Guard().evaluate(bash("git merge main"))
    assert isinstance(r, PolicyResult)
    assert r.reason
    assert r.blocked


def test_no_engine_still_falls_through_to_default() -> None:
    # Unchanged behavior when the engine seam isn't opted into.
    g = Guard()
    result = g.evaluate(bash("ls -la"))
    assert result.decision is Decision.ALLOW
    assert result.rule == "default"


def test_engine_judges_an_unmatched_action() -> None:
    engine = _SpyEngine(reply="ASK")
    g = Guard(engine=engine)

    result = g.evaluate(bash("curl -sSL https://example.com/install.sh | bash"))

    assert result.decision is Decision.ASK
    assert result.rule == "engine_judgment"
    assert len(engine.calls) == 1


def test_engine_never_overrides_an_explicit_rule_match() -> None:
    engine = _SpyEngine(reply="ALLOW")  # would allow if it were ever consulted
    g = Guard(engine=engine)

    result = g.evaluate(bash("git push --force origin main"))

    assert result.decision is Decision.DENY
    assert result.rule == "no_force_push"
    assert engine.calls == []  # deterministic rules are never second-guessed


def test_engine_unparseable_reply_fails_safe_to_ask() -> None:
    g = Guard(engine=_SpyEngine(reply="sure, why not"))
    result = g.evaluate(bash("ls -la"))
    assert result.decision is Decision.ASK
    assert result.rule == "engine_judgment_failed"


def test_engine_empty_reply_fails_safe_to_ask() -> None:
    g = Guard(engine=_SpyEngine(reply=""))  # e.g. a NoopEngine or a failed ClaudeCLIEngine call
    result = g.evaluate(bash("ls -la"))
    assert result.decision is Decision.ASK
    assert result.rule == "engine_judgment_failed"


# ----------------------------------------------------------------- ask channel
#
# A rule answering ASK means "a human should confirm". Unattended there was nobody
# to confirm, so every caller's .under(unattended=True) collapsed it to DENY -- and
# the human was never actually asked. An ask channel is how they answer. Guard runs
# a command and reads its exit code; it knows nothing about Telegram.


class _Channel:
    def __init__(self, decision: Decision) -> None:
        self.decision = decision
        self.asked: list[Action] = []

    def __call__(self, action: Action) -> Decision:
        self.asked.append(action)
        return self.decision


def _ask_guard(channel) -> Guard:
    # A rule set whose only verdict is ASK, so the channel is always consulted.
    return Guard(
        [Rule(name="confirm", kind="risky", decision=Decision.ASK, reason="confirm first")],
        ask=channel,
    )


def test_a_human_can_turn_an_ask_into_an_allow() -> None:
    channel = _Channel(Decision.ALLOW)

    result = _ask_guard(channel).evaluate(Action(kind="risky", payload={"x": 1}))

    assert result.decision is Decision.ALLOW
    assert channel.asked == [Action(kind="risky", payload={"x": 1})]
    # And it survives the collapse every caller applies -- which is the entire
    # point: unattended, this used to be a silent DENY.
    assert result.under(unattended=True) is Decision.ALLOW


def test_a_human_can_turn_an_ask_into_a_deny() -> None:
    result = _ask_guard(_Channel(Decision.DENY)).evaluate(Action(kind="risky"))

    assert result.decision is Decision.DENY


def test_an_ask_channel_may_never_widen_an_allow_or_a_deny() -> None:
    # A channel resolves an open question; it must never reopen a settled one, or
    # a compromised/buggy channel could turn a DENY rule into an ALLOW.
    channel = _Channel(Decision.ALLOW)
    guard = Guard(
        [
            Rule(name="never", kind="forbidden", decision=Decision.DENY, reason="no"),
            Rule(name="fine", kind="routine", decision=Decision.ALLOW, reason="ok"),
        ],
        ask=channel,
    )

    assert guard.evaluate(Action(kind="forbidden")).decision is Decision.DENY
    assert guard.evaluate(Action(kind="routine")).decision is Decision.ALLOW
    assert channel.asked == []  # never consulted


def test_without_a_channel_behavior_is_exactly_what_it_was() -> None:
    # The rollback path: unset the env var and ASK is returned untouched, for the
    # caller to collapse to DENY as it always did.
    result = Guard(
        [Rule(name="confirm", kind="risky", decision=Decision.ASK, reason="confirm first")],
        ask=None,
    ).evaluate(Action(kind="risky"))

    assert result.decision is Decision.ASK
    assert result.under(unattended=True) is Decision.DENY


def test_ask_none_disables_escalation_even_when_the_env_configures_a_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `ask=None` must mean "explicitly no channel", not "unspecified". The caller who
    # most needs this is MyTelegramBot's daemon: it *is* the ask channel, so a Guard
    # that escalates inside it would shell out to `mytelegrambot ask`, which blocks
    # on a ledger callback only that same single-threaded daemon can write --
    # deadlocking it against itself, and stalling every worker's escalation behind it.
    #
    # Defaulting on the value None would have made that opt-out a silent no-op.
    monkeypatch.setenv("MYTHINGS_ASK_CMD", "mytelegrambot ask")

    assert Guard().ask is not None  # a bare Guard picks the channel up from the env
    assert Guard(ask=None).ask is None  # and this is how you refuse it

    result = Guard(
        [Rule(name="confirm", kind="risky", decision=Decision.ASK, reason="confirm")], ask=None
    ).evaluate(Action(kind="risky"))

    assert result.decision is Decision.ASK  # never escalated
    assert result.under(unattended=True) is Decision.DENY  # and fails closed as before


# ------------------------------------------------------------------ merging
#
# "A human always merges" is the fleet's hardest rule. Until now it was enforced
# only against the *bash spelling* of a merge -- `no_merge` matches a command string
# containing `gh pr merge`. A tool merging through a structured Action matched no
# rule, fell through to Guard's permissive default, and was ALLOWED, unattended,
# with no human anywhere near it.


def test_a_structured_merge_is_not_allowed_by_default() -> None:
    # The hole this closes. Before the `merge_needs_a_human` rule this returned
    # ALLOW/default, so a tool merging via an Action bypassed the fleet's most
    # important invariant entirely.
    result = Guard().evaluate(Action(kind=MERGE_ACTION, payload={"repo": "o/r", "number": 12}))

    assert result.decision is not Decision.ALLOW
    assert result.rule == "merge_needs_a_human"


def test_an_unattended_merge_still_denies_when_nobody_can_be_asked() -> None:
    # No ask channel -> the ASK collapses to DENY, exactly as it always did. A
    # headless worker can never merge, channel or no channel.
    result = Guard(ask=None).evaluate(Action(kind=MERGE_ACTION, payload={"number": 12}))

    assert result.under(unattended=True) is Decision.DENY


def test_a_human_reachable_on_the_ask_channel_can_approve_a_merge() -> None:
    # And with a human reachable, the tap *is* the human merging -- which is what
    # the rule always required, and what previously cost a trip to a laptop.
    approved = Guard(ask=lambda action: Decision.ALLOW).evaluate(
        Action(kind=MERGE_ACTION, payload={"number": 12})
    )
    refused = Guard(ask=lambda action: Decision.DENY).evaluate(
        Action(kind=MERGE_ACTION, payload={"number": 12})
    )

    assert approved.under(unattended=True) is Decision.ALLOW
    assert refused.under(unattended=True) is Decision.DENY


def test_a_worker_shelling_out_to_merge_is_still_denied_outright() -> None:
    # The bash path stays a hard DENY, not an ASK: a worker must never even be able
    # to *propose* a merge. Only a tool using the structured action gets to ask.
    result = Guard().evaluate(Action(kind="bash", payload={"command": "gh pr merge 12 --squash"}))

    assert result.decision is Decision.DENY
    assert result.rule == "no_merge"
    assert result.under(unattended=True) is Decision.DENY
