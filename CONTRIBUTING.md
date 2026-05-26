# Contributing

## Python version

This integration targets **Python 3.14+** (see `pyproject.toml` and
`.github/workflows/ci.yml`).  Home Assistant 2026.1.0 and later ship
with Python 3.14.

## Code style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting,
configured via `pyproject.toml`.  `ruff format` is the source of truth
for code style — run it (or the `format` task in the devcontainer)
before committing.  Pre-commit hooks run Ruff with `--fix` automatically;
see `.pre-commit-config.yaml`.

### `except` clauses without parentheses

[PEP 758](https://peps.python.org/pep-0758/), accepted for Python 3.14,
allows the unparenthesized form for catching multiple exception types:

```python
try:
    ...
except ValueError, TypeError:   # PEP 758, Python 3.14+
    ...
```

`ruff format` with `target-version = "py314"` actively rewrites the
older parenthesized form to this style.  **Do not "fix" these clauses
back to `except (ValueError, TypeError):`** — the unparenthesized form
is deliberate and required to satisfy the formatter.

Side effects worth knowing about:

- The code will not parse on Python < 3.14.  Don't try to run the
  integration or its tests on an older interpreter; use the
  devcontainer or a 3.14 environment.
- Some tools (e.g. older `mypy` versions) may not yet implement
  PEP 758 and will report a spurious syntax error.  CI pins versions
  that handle it; if you see this locally, upgrade the tool rather
  than edit the source.
