from mythings.policy import Action, Decision, Policy, PolicyResult

from myguard import Guard, Rule


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
