# Development

This repository is set up to develop the PoolCop custom component using a Home Assistant devcontainer.

## Quick start

1. Open in VS Code and run "Dev Containers: Reopen in Container".
2. After the container is ready:
   - Tests: `docker exec -w /workspaces/hass-poolcop <container> pytest tests/ -v --cov --cov-report=term-missing`
   - Lint/format: Run "ruff-lint" / "ruff-fix" / "format" tasks
   - Validate manifest: Run "hassfest"
   - Run Home Assistant: Run "run-home-assistant" (component is symlinked to `/config/custom_components/poolcop`)

## Local library development

If you also have `python-poolcop` checked out in `${HOME}/clones/python-poolcop`, it is mounted into the container and installed editable. Changes to the library are reflected immediately without rebuilding.

## Pre-commit

Pre-commit is installed and hooks are configured. It runs Ruff and Black with `--fix`.

## Coverage targets

- hass-poolcop custom components: 93%+
- python-poolcop library: 99%

Run the full suite with coverage:
```bash
docker exec -w /workspaces/hass-poolcop <container> pytest tests/ -v --cov --cov-report=term-missing
```

## Troubleshooting

- If pytest isn't found, ensure you're inside the devcontainer.
- If HA doesn't see the component, check the symlink at `/config/custom_components/poolcop`.
