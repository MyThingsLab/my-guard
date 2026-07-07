from __future__ import annotations

from mythings.engine import Engine, EngineRequest
from mythings.policy import Action, Decision, PolicyResult

from myguard.rules import Rule, default_rules

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
    ) -> None:
        self.rules = default_rules() if rules is None else list(rules)
        self.default = default
        self.engine = engine

    def evaluate(self, action: Action) -> PolicyResult:
        for rule in self.rules:
            if rule.applies(action):
                return PolicyResult(rule.decision, reason=rule.reason, rule=rule.name)
        if self.engine is None:
            return PolicyResult(self.default, rule="default")
        return self._judge(action)

    def _judge(self, action: Action) -> PolicyResult:
        reply = self.engine.run(
            EngineRequest(prompt=_judge_prompt(action), system=_JUDGE_SYSTEM)
        ).text.strip().upper()
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
