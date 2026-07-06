from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from mythings.policy import Action, Decision


def _always(_: Action) -> bool:
    return True


@dataclass(frozen=True)
class Rule:
    name: str
    decision: Decision
    reason: str
    kind: str = "*"
    match: Callable[[Action], bool] = field(default=_always)

    def applies(self, action: Action) -> bool:
        return self.kind in ("*", action.kind) and self.match(action)


def _command(action: Action) -> str:
    return str(action.payload.get("command", ""))


def _matches(pattern: re.Pattern[str]) -> Callable[[Action], bool]:
    return lambda action: pattern.search(_command(action)) is not None


_MERGE = re.compile(r"\b(git\s+merge\b|gh\s+pr\s+merge\b)")
_FORCE_PUSH = re.compile(r"\bgit\s+push\b.*(--force(-with-lease)?\b|\s-f\b)")
_PUSH_PROTECTED = re.compile(r"\bgit\s+push\b.*\b(main|master)\b")
_DESTRUCTIVE = re.compile(
    r"\b(rm\s+-rf?|git\s+reset\s+--hard|git\s+branch\s+-D|git\s+clean\s+-\w*f)"
)


def default_rules() -> list[Rule]:
    # First match wins; anything unmatched falls through to the engine's default.
    return [
        Rule(
            "no_merge",
            Decision.DENY,
            "a worker opens PRs; it never merges — merge authority stays with a human or App",
            kind="bash",
            match=_matches(_MERGE),
        ),
        Rule(
            "no_force_push",
            Decision.DENY,
            "force-push rewrites shared history",
            kind="bash",
            match=_matches(_FORCE_PUSH),
        ),
        Rule(
            "protect_main",
            Decision.DENY,
            "direct push to a protected branch",
            kind="bash",
            match=_matches(_PUSH_PROTECTED),
        ),
        Rule(
            "confirm_destructive",
            Decision.ASK,
            "irreversible filesystem/history change — a human must confirm",
            kind="bash",
            match=_matches(_DESTRUCTIVE),
        ),
    ]
