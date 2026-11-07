# Development environment

Home Assistant + Paperless-ngx + Redis in Docker, with **synthetic data only**.
Never point this environment (or the tests) at a Paperless server with real documents.

## Start

```bash
cd dev
cp .env.example .env          # then change the passwords; .env is git-ignored
docker compose up -d
docker compose --profile seed run --rm seed
```

| Service | URL |
|---|---|
| Paperless-ngx | http://localhost:8011 (user/password from `dev/.env`) |
| Home Assistant | http://localhost:8124 (create a user during onboarding) |

The seed script is idempotent. It creates:

- user `ha-lookup` with view permissions only; its API token is written to `dev/data/ha-lookup.token`,
- tags `HA` (access tag) and `Finance`,
- document types Manual, Receipt, Invoice, Warranty, Bank statement,
- custom field `HA model` (manuals list one or more models separated by `;`),
- generated PDFs: manuals, receipts, an invoice and a warranty with the `HA` tag, plus leak-test
  documents **without** the tag (one of them not even shared with `ha-lookup`). Their text contains
  `LEAKTEST-…` markers: these must never show up in Home Assistant.

## Use the integration

The integration is mounted read-only into Home Assistant at
`/config/custom_components/paperless_lookup`. After code changes: `docker compose restart homeassistant`.

Add it under *Settings → Devices & services → Add integration → Paperless Lookup* with URL
`http://paperless:8000` and the token from `dev/data/ha-lookup.token`.

## Versions

`HA_VERSION` (default `2026.6.0`, the minimum supported version) and `PAPERLESS_VERSION`
(default `3.3.4`) can be set in `dev/.env`.

## Reset

```bash
docker compose down -v        # removes all dev data (volumes)
```
