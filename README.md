# my-guard

[![CI](https://github.com/MyThingsLab/my-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-guard/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-guard/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-guard) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The **rule engine** for [MyThingsLab](../my-things-core). Core defines the
vocabulary — `Action`, `Decision` (allow / ask / deny), and the `Policy`
protocol; `my-guard` supplies the implementation that turns a proposed `Action`
into a `PolicyResult`.

Every other `My[X]` tool asks a `Guard` before it does anything with side
effects, so the rules about what a worker may do live in one place instead of
being re-invented per tool.

## How it works

`Guard.evaluate(action)` walks an ordered list of `Rule`s and returns the first
match; anything unmatched falls through to a configurable default (`ALLOW` for a
supervised run, `DENY` to lock a runner down). The default rule set encodes the
harness's non-negotiables:

| Rule | Decision | Why |
|---|---|---|
| `no_merge` | deny | a worker opens PRs; merge authority stays with a human or App |
| `no_force_push` | deny | force-push rewrites shared history |
| `protect_main` | deny | no direct push to a protected branch |
| `confirm_destructive` | ask | irreversible fs/history changes need a human |

An `ASK` result collapses to `DENY` under an unattended runner via
`PolicyResult.under(unattended=True)`, so nothing proceeds on a would-ask action
when no human is watching.

## Project rules

Those rules are fleet-wide and command-shaped. A *specific* project also has its
own protected paths — a generated file that should never be hand-edited, a
schema, CI config — and those are path-shaped. A project declares them in
`.my-guard/rules.json` at its root, discovered by walking up from the working
directory:

```json
{
  "deny_edit": ["db/schema.sql", "docs/api/generated/*"],
  "ask_edit":  ["*.toml", ".github/workflows/*"]
}
```

Globs are `fnmatch`, so `*` crosses path separators (`build/*` covers
`build/a/b.js`), and match against both the repo-relative and the caller-supplied
spelling of a path. The file is data only — globs and a severity, no executable
predicates — so it can be authored and reviewed without touching this package.

Two properties make this safe to layer under the fleet rules:

- **Project rules only ever tighten.** The two rule sets combine by severity, not
  by ordering: the stricter of the two wins. A project `deny_edit` can override
  the fleet's routine `ALLOW`, but no project rule can turn a fleet `DENY` into
  an `ASK`. A path matching nothing returns *no opinion*, not `ALLOW`.
- **A malformed rule file raises.** Degrading to "no rules" would leave a project
  believing it is protected when it is not, and a broken deny is indistinguishable
  from an allow.

An action is path-checked only when it carries an explicit `path` or `paths`
payload key. Paths are deliberately not scraped out of a `command` string: a
wrong extraction is a wrong `DENY` on an unrelated file, and a rule set that
cries wolf gets switched off.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../my-things-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
