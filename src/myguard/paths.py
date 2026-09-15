from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from mythings.policy import Action, Decision, PolicyResult

# Read from the project root, not passed as an argument, for the same reason the
# ask channel is configured by environment: the ~15 sites across the fleet that
# build a policy do so as `policy or Guard()`, with nowhere to thread a rule set
# through. A file the project ships is a rule set every one of them picks up.
RULES_FILE = PurePosixPath(".my-guard/rules.json")

_PATH_KEYS = ("paths", "path")


def action_paths(action: Action) -> list[str]:
    # Only explicit path keys. Deliberately *not* scraped out of a `command`
    # string: a wrong extraction here is a wrong DENY on an unrelated file, and a
    # rule set that cries wolf gets switched off. A caller that wants its writes
    # path-checked says which paths they are.
    for key in _PATH_KEYS:
        raw = action.payload.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            return [raw]
        return [str(p) for p in raw]
    return []


def find_root(start: Path | str | None = None) -> Path | None:
    current = Path(start if start is not None else Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / RULES_FILE).is_file():
            return candidate
    return None


@dataclass(frozen=True)
class ProjectRules:
    """A project's own protected paths, layered over the fleet-wide command rules.

    Data only -- globs and a severity, no executable predicates -- so the file can
    be authored and reviewed without touching my-guard's Python.
    """

    root: Path
    deny_edit: tuple[str, ...] = ()
    ask_edit: tuple[str, ...] = ()

    @classmethod
    def load(cls, start: Path | str | None = None) -> ProjectRules | None:
        root = find_root(start)
        if root is None:
            return None
        return cls.from_file(root / RULES_FILE, root=root)

    @classmethod
    def from_file(cls, path: Path, *, root: Path | None = None) -> ProjectRules:
        # A malformed rule file raises rather than degrading to "no rules". The
        # failure mode of swallowing it is a project that believes it is protected
        # and silently is not -- a broken deny is indistinguishable from an allow,
        # which is the one direction this must never fail in.
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a JSON object, got {type(data).__name__}")
        return cls(
            root=Path(root if root is not None else Path(path).parent.parent).resolve(),
            deny_edit=_globs(data, "deny_edit", path),
            ask_edit=_globs(data, "ask_edit", path),
        )

    def evaluate(self, action: Action) -> PolicyResult | None:
        """DENY / ASK if any of the action's paths is protected, else None (no opinion).

        None is not ALLOW. A project rule set may only ever *tighten* the fleet-wide
        rules, so "no match here" has to stay silent and let the fleet rules decide,
        rather than voting ALLOW and loosening a fleet DENY.
        """
        candidates = [self._match_forms(p) for p in action_paths(action)]
        for decision, globs, rule in (
            (Decision.DENY, self.deny_edit, "project_deny_edit"),
            (Decision.ASK, self.ask_edit, "project_ask_edit"),
        ):
            for forms in candidates:
                if (hit := _first_match(forms, globs)) is not None:
                    return PolicyResult(
                        decision,
                        reason=f"{forms[0]} is a protected path in this project ({hit})",
                        rule=rule,
                    )
        return None

    def _match_forms(self, path: str) -> tuple[str, ...]:
        # Match the repo-relative spelling and the one the caller passed, so a rule
        # file can be written in the natural `docs/generated/*` form regardless of
        # whether the caller hands over an absolute or a relative path.
        given = PurePosixPath(path)
        forms = [str(given)]
        try:
            relative = str(Path(path).resolve().relative_to(self.root))
        except (ValueError, OSError):
            return tuple(dict.fromkeys(forms))
        forms.append(relative)
        return tuple(dict.fromkeys(forms))


def _globs(data: dict, key: str, path: Path) -> tuple[str, ...]:
    raw = data.get(key, ())
    if isinstance(raw, str) or not all(isinstance(g, str) for g in raw):
        raise ValueError(f"{path}: '{key}' must be a list of glob strings")
    return tuple(raw)


def _first_match(forms: tuple[str, ...], globs: tuple[str, ...]) -> str | None:
    # fnmatch, so `*` crosses path separators: `build/*` covers `build/a/b.js`.
    return next(
        (glob for glob in globs for form in forms if fnmatch.fnmatch(form, glob)),
        None,
    )
