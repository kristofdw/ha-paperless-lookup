# Paperless Lookup for Home Assistant: instructions for AI agents

> The single source of project instructions for any AI agent (Claude Code, Continue, Codex, …) and a quick
> start for human contributors. `CLAUDE.md` only imports this file.

Custom integration `paperless_lookup` for the Home Assistant Marketplace (formerly HACS): makes
Paperless-ngx documents that carry an access tag (default `HA`) searchable in Home Assistant. Manuals are
linked to devices, receipts/invoices can be searched from a phone, and access is granted per category
(Paperless document type) per Home Assistant user. Apache-2.0.

## Layout
- `custom_components/paperless_lookup/`: the integration (manifest, config flow, translations en/nl).
- `tests/`: pytest with `pytest-homeassistant` (from Home Assistant core). HTTP is mocked with `aioclient_mock`;
  `tests/fixtures/` holds responses captured from the dev Paperless by `dev/capture_fixtures.py`.
- `custom_components/paperless_lookup/api.py`: read-only Paperless client (API version 10, Paperless-ngx
  3.0.0 or newer). Never request document content or `/api/profile/` (it returns the token).
- `frontend/`: TypeScript + Lit source of the sidebar panel and the dashboard card (`custom:paperless-lookup-card`),
  tested with vitest. Vite builds one ES module to `custom_components/paperless_lookup/frontend/paperless-lookup.js`,
  which is committed (the Marketplace does not build); CI fails when it does not match the sources.
- `dev/`: Docker Compose with Home Assistant + Paperless-ngx + Redis and a seed script with synthetic
  documents (see `dev/README.md`).
- `script/uv`: uv wrapper; `script/git-hooks/`: git hooks.
- `.github/workflows/`: lint (pre-commit), tests (minimum and latest Home Assistant), frontend (typecheck,
  vitest, build check), hassfest, HACS action (the Marketplace's validation action).

## Build and test
- Python tooling runs on **Linux/WSL** only (Home Assistant does not run on Windows). Frontend tooling
  (node/npm) may run on Windows.
- Use `script/uv` instead of `uv`: it keeps the virtualenv in `~/.venvs/ha-paperless-lookup` (a WSL checkout
  on `/mnt/c` is slow otherwise). From the repo root:
  - `bash script/uv sync`
  - `bash script/uv run pytest` (coverage gate 95 %)
  - `bash script/uv run pre-commit run --all-files` (ruff, ruff format, mypy strict, gitleaks, …)
  - From Windows PowerShell: `wsl -d Ubuntu --cd <repo> -- bash -lc "bash script/uv run pytest"`.
- Frontend (node 24, Windows or Linux): `cd frontend && npm ci && npm run check` (typecheck, tests, build), then
  commit the rebuilt bundle together with the sources.
- Enable the hook once per clone: `git config core.hooksPath script/git-hooks`. Commits from Windows Git
  forward the hook to WSL. `.gitattributes` forces LF so Windows Git and WSL Git agree.
- Minimum supported Home Assistant is pinned via `pytest-homeassistant` (the test package from Home
  Assistant core) in `pyproject.toml` and must match `hacs.json`. Pin `home-assistant-frontend` to the
  version that Home Assistant release requires. Do not install `pytest-homeassistant-custom-component`
  (discontinued, overlapping fixtures).

## Conventions
- Code, docstrings, README, commit messages and this file in **English**.
- Follow the Home Assistant custom integration guidelines and the Integration Quality Scale (Silver or
  better): `runtime_data`, config flow tests, reauth, reconfigure, diagnostics, repair issues. Keep the
  self-assessment in `custom_components/paperless_lookup/quality_scale.yaml` up to date; hassfest does not
  check it for custom integrations, and no tier is claimed in `manifest.json`.
- No extra Python dependencies. Use `async_get_clientsession` for HTTP.
- Keep project instructions in this file. Do not add agent-specific instruction files.

## Security and privacy (hard rules)
- Never put tokens, passwords, hostnames or IP addresses of real servers in code, tests, fixtures, logs or
  commits. Test tokens are obviously fake (`fake-test-token-…`).
- Develop and test only against the dev Paperless in `dev/` with synthetic data. Never read, download or
  display documents from a real Paperless server; at most check counts. Screenshots only with synthetic data.
- The dev API token is written to `dev/data/ha-lookup.token` (git-ignored). Never print or log it.
- Access control is enforced in the backend: every websocket command and HTTP view goes through one central
  access check; documents without the access tag or in a category the user may not see return 404.
- Diagnostics never contain tokens, URLs, user names or document titles/content.
