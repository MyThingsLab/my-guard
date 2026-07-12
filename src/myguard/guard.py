from __future__ import annotations

from typing import Any

from mythings.engine import Engine, EngineRequest
from mythings.policy import Action, Decision, PolicyResult

from myguard.ask import AskChannel, ask_channel_from_env
from myguard.rules import Rule, default_rules

# `ask=None` has to mean "explicitly no channel, never escalate", not "unspecified".
# Without a distinct sentinel the two collapse, and the caller who most needs to opt
# out cannot: MyTelegramBot's daemon *is* the ask channel, so a Guard that escalates
# inside it deadlocks the daemon against itself. Defaulting on the value None would
# have made that opt-out silently a no-op.
_UNSET: Any = object()

_JUDGE_SYSTEM = (
    "You are a safety gate for an autonomous coding agent's shell/git/gh side "
    "effects. Classify the given action as exactly one word: ALLOW (routine, "
    "safe), ASK (a human should confirm before it runs), or DENY (should be "
    "blocked outright). Reply with only that one word, nothing else."
)
_DECISIONS_BY_WORD = {d.name: d for d in Decision}


def _judge_prompt(action: Action) -> str:
    lines = [f"Action kind: {action.kind}"]
    lines += [f"{k}: {v}" for k, v in sorted(action.payload.items())]
    return "\n".join(lines)


class Guard:
    def __init__(
        self,
        rules: list[Rule] | None = None,
        *,
        default: Decision = Decision.ALLOW,
        engine: Engine | None = None,
        ask: AskChannel | None = _UNSET,
    ) -> None:
        self.rules = default_rules() if rules is None else list(rules)
        self.default = default
        self.engine = engine
        # Defaults to whatever MYTHINGS_ASK_CMD names, so the ~15 `policy or
        # Guard()` sites across the fleet pick it up without threading an argument
        # through any of them. Pass a channel to override it, or `ask=None` to
        # disable escalation outright -- which the bot's daemon must, since it is
        # itself the channel and would otherwise deadlock waiting on its own reply.
        self.ask = ask_channel_from_env() if ask is _UNSET else ask

    def evaluate(self, action: Action) -> PolicyResult:
        return self._escalate(self._decide(action), action)

    def _decide(self, action: Action) -> PolicyResult:
        for rule in self.rules:
            if rule.applies(action):
                return PolicyResult(rule.decision, reason=rule.reason, rule=rule.name)
        if self.engine is None:
            return PolicyResult(self.default, rule="default")
        return self._judge(action)

    def _escalate(self, result: PolicyResult, action: Action) -> PolicyResult:
        # ASK is the only decision a human can change. An ALLOW or a DENY is the
        # rule engine having already made up its mind, and routing those past a
        # human would let a channel *widen* the policy -- an ask channel may only
        # ever resolve an open question, never reopen a settled one.
        if result.decision is not Decision.ASK or self.ask is None:
            return result
        decided = self.ask(action)
        return PolicyResult(
            decided,
            reason=f"{result.reason} -> human said {decided.value}".strip(" ->"),
            rule=f"{result.rule}+ask" if result.rule else "ask",
        )

    def _judge(self, action: Action) -> PolicyResult:
        reply = (
            self.engine.run(EngineRequest(prompt=_judge_prompt(action), system=_JUDGE_SYSTEM))
            .text.strip()
            .upper()
        )
        decision = _DECISIONS_BY_WORD.get(reply)
        if decision is None:
            # An engine was explicitly wired in but gave no usable answer —
            # fail safe to a human confirming, not to the permissive default.
            return PolicyResult(
                Decision.ASK,
                reason="engine judgment unavailable — failing safe",
                rule="engine_judgment_failed",
            )
        return PolicyResult(decision, reason=f"engine judgment: {reply}", rule="engine_judgment")
