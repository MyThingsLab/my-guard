from __future__ import annotations

from mythings.policy import Action, Decision, PolicyResult

from myguard.rules import Rule, default_rules


class Guard:
    def __init__(
        self, rules: list[Rule] | None = None, *, default: Decision = Decision.ALLOW
    ) -> None:
        self.rules = default_rules() if rules is None else list(rules)
        self.default = default

    def evaluate(self, action: Action) -> PolicyResult:
        for rule in self.rules:
            if rule.applies(action):
                return PolicyResult(rule.decision, reason=rule.reason, rule=rule.name)
        return PolicyResult(self.default, rule="default")
