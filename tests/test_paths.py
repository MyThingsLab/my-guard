import json
from pathlib import Path

import pytest
from mythings.policy import Action, Decision
from mythings.testing import ScriptedEngine

from myguard import Guard, ProjectRules, Rule, action_paths, find_root
from myguard.paths import RULES_FILE


def write_rules(root: Path, **lists: list[str]) -> Path:
    path = root / RULES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lists))
    return path


def edit(*paths: str) -> Action:
    return Action(kind="fs-write", payload={"paths": list(paths)})


# ------------------------------------------------------------------- discovery


def test_rules_are_found_from_a_subdirectory(tmp_path: Path) -> None:
    write_rules(tmp_path, deny_edit=["schema.sql"])
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)

    assert find_root(nested) == tmp_path
    assert ProjectRules.load(nested).deny_edit == ("schema.sql",)


def test_no_rule_file_anywhere_means_no_project_rules(tmp_path: Path) -> None:
    assert find_root(tmp_path) is None
    assert ProjectRules.load(tmp_path) is None


def test_a_malformed_rule_file_raises_rather_than_degrading_to_no_rules(tmp_path: Path) -> None:
    # The dangerous direction: swallowing this leaves a project believing it is
    # protected when it is not, and a broken deny is indistinguishable from an allow.
    (tmp_path / ".my-guard").mkdir()
    (tmp_path / RULES_FILE).write_text("{not json")

    with pytest.raises(json.JSONDecodeError):
        ProjectRules.load(tmp_path)


def test_a_rule_file_with_the_wrong_shape_raises(tmp_path: Path) -> None:
    write_rules(tmp_path)
    (tmp_path / RULES_FILE).write_text(json.dumps({"deny_edit": "schema.sql"}))

    with pytest.raises(ValueError, match="must be a list of glob strings"):
        ProjectRules.load(tmp_path)


# ----------------------------------------------------------------- path matching


def test_action_paths_reads_both_the_list_and_the_scalar_spelling() -> None:
    assert action_paths(Action("fs-write", {"paths": ["a", "b"]})) == ["a", "b"]
    assert action_paths(Action("fs-write", {"path": "a"})) == ["a"]
    assert action_paths(Action("fs-write", {"command": "rm a"})) == []


def test_deny_edit_blocks_a_protected_path(tmp_path: Path) -> None:
    write_rules(tmp_path, deny_edit=["db/schema.sql"])
    rules = ProjectRules.load(tmp_path)

    result = rules.evaluate(edit("db/schema.sql"))

    assert result.decision is Decision.DENY
    assert result.rule == "project_deny_edit"
    assert "db/schema.sql" in result.reason


def test_ask_edit_downgrades_to_ask(tmp_path: Path) -> None:
    write_rules(tmp_path, ask_edit=["*.toml"])

    result = ProjectRules.load(tmp_path).evaluate(edit("pyproject.toml"))

    assert result.decision is Decision.ASK
    assert result.rule == "project_ask_edit"


def test_an_unprotected_path_gets_no_opinion_rather_than_an_allow(tmp_path: Path) -> None:
    # None, not ALLOW. Voting ALLOW here would let a project rule set loosen a
    # fleet-wide DENY, which is precisely what "tighten only" forbids.
    write_rules(tmp_path, deny_edit=["schema.sql"])

    assert ProjectRules.load(tmp_path).evaluate(edit("src/main.py")) is None


def test_deny_wins_over_ask_when_a_path_matches_both(tmp_path: Path) -> None:
    write_rules(tmp_path, deny_edit=["build/*"], ask_edit=["*"])

    assert ProjectRules.load(tmp_path).evaluate(edit("build/out.js")).decision is Decision.DENY


def test_one_protected_path_taints_a_multi_path_edit(tmp_path: Path) -> None:
    # A diff touching ten innocent files and one generated one is still an edit to
    # the generated one.
    write_rules(tmp_path, deny_edit=["build/*"])

    result = ProjectRules.load(tmp_path).evaluate(edit("a.py", "b.py", "build/out.js"))

    assert result.decision is Decision.DENY


def test_a_deny_on_any_path_beats_an_ask_on_an_earlier_one(tmp_path: Path) -> None:
    write_rules(tmp_path, deny_edit=["build/*"], ask_edit=["*.toml"])

    result = ProjectRules.load(tmp_path).evaluate(edit("pyproject.toml", "build/out.js"))

    assert result.decision is Decision.DENY


def test_globs_cross_path_separators(tmp_path: Path) -> None:
    write_rules(tmp_path, deny_edit=["build/*"])

    assert ProjectRules.load(tmp_path).evaluate(edit("build/a/b/c.js")).decision is Decision.DENY


def test_an_absolute_path_matches_a_repo_relative_glob(tmp_path: Path) -> None:
    # The rule file is written in the natural repo-relative form; callers hand over
    # whatever they happen to have.
    write_rules(tmp_path, deny_edit=["db/schema.sql"])
    absolute = str(tmp_path / "db" / "schema.sql")

    assert ProjectRules.load(tmp_path).evaluate(edit(absolute)).decision is Decision.DENY


def test_a_path_outside_the_project_does_not_match_a_relative_glob(tmp_path: Path) -> None:
    write_rules(tmp_path, deny_edit=["db/schema.sql"])

    assert ProjectRules.load(tmp_path).evaluate(edit("/elsewhere/db/schema.sql")) is None


# --------------------------------------------------------- layering over the fleet


def project(tmp_path: Path, **lists: list[str]) -> ProjectRules:
    write_rules(tmp_path, **lists)
    return ProjectRules.load(tmp_path)


def test_a_project_deny_overrides_a_fleet_allow(tmp_path: Path) -> None:
    # `routine_fs-write` ALLOWs every fs-write action fleet-wide. This is the whole
    # point of the feature: a project gets to carve its own files out of that.
    guard = Guard(project=project(tmp_path, deny_edit=["build/*"]))

    assert guard.evaluate(edit("src/main.py")).rule == "routine_fs-write"
    assert guard.evaluate(edit("build/out.js")).decision is Decision.DENY


def test_a_project_ask_cannot_downgrade_a_fleet_deny(tmp_path: Path) -> None:
    # The tighten-only invariant, in the direction that matters. `ask_edit: ["*"]`
    # is the most permissive thing a project can write, and a fleet DENY survives it.
    guard = Guard(
        rules=[Rule("never", Decision.DENY, "fleet says no", kind="fs-write")],
        project=project(tmp_path, ask_edit=["*"]),
        ask=None,
    )

    result = guard.evaluate(edit("anything.py"))

    assert result.decision is Decision.DENY
    assert result.rule == "never"


def test_a_project_deny_can_tighten_a_fleet_ask(tmp_path: Path) -> None:
    guard = Guard(
        rules=[Rule("confirm", Decision.ASK, "fleet asks", kind="fs-write")],
        project=project(tmp_path, deny_edit=["*"]),
        ask=lambda action: Decision.ALLOW,
    )

    # A DENY is never routed past the ask channel, so the human is never consulted.
    assert guard.evaluate(edit("anything.py")).decision is Decision.DENY


def test_a_project_ask_is_resolvable_on_the_ask_channel(tmp_path: Path) -> None:
    rules = project(tmp_path, ask_edit=["*.toml"])

    approved = Guard(project=rules, ask=lambda action: Decision.ALLOW)
    refused = Guard(project=rules, ask=lambda action: Decision.DENY)

    assert approved.evaluate(edit("pyproject.toml")).under(unattended=True) is Decision.ALLOW
    assert refused.evaluate(edit("pyproject.toml")).under(unattended=True) is Decision.DENY


def test_a_project_deny_short_circuits_the_engine(tmp_path: Path) -> None:
    # Nothing the judge could answer makes a project DENY less than a DENY, so the
    # call is not worth paying for.
    engine = ScriptedEngine(reply="ALLOW")
    guard = Guard(project=project(tmp_path, deny_edit=["*"]), engine=engine)

    assert guard.evaluate(Action(kind="brand-new-kind", payload={"path": "x"})).blocked
    assert engine.calls == []


def test_no_project_rules_is_byte_for_byte_the_previous_behavior(tmp_path: Path) -> None:
    # The rollback path: no rule file, no behavior change anywhere.
    bash = Action(kind="bash", payload={"command": "ls -la"})

    assert Guard(project=None).evaluate(bash).rule == "default"
    assert Guard(project=None).evaluate(edit("build/out.js")).rule == "routine_fs-write"


def test_guard_discovers_a_rule_file_from_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The `policy or Guard()` sites never pass a rule set, so discovery is the only
    # way a project's rules ever reach them.
    write_rules(tmp_path, deny_edit=["build/*"])
    monkeypatch.chdir(tmp_path)

    assert Guard().evaluate(edit("build/out.js")).decision is Decision.DENY
