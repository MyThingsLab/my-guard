# my-guard

[![CI](https://github.com/MyThingsLab/my-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-guard/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-guard/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-guard) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The **rule engine** for [MyThingsLab](../mythings-core). Core defines the
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

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../mythings-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
