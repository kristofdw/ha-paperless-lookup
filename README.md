# Paperless Lookup for Home Assistant

> **Work in progress.** Not ready for use yet.

A [HACS](https://hacs.xyz/) integration that makes selected [Paperless-ngx](https://docs.paperless-ngx.com/)
documents searchable in [Home Assistant](https://www.home-assistant.io/):

- **Manuals linked to devices:** see the manual of a device right in Home Assistant.
- **Look things up on the go:** search receipts, invoices and warranty documents from your phone
  (Home Assistant Companion app), filtered by category, store and date.
- **Opt-in:** only documents with an access tag (default `HA`) are visible in Home Assistant.
- **Access per category per Home Assistant user:** for example manuals for everyone, receipts only for adults.
- Home Assistant talks to Paperless over your local network. Browsers and phones never need a Paperless token.

Requires Home Assistant 2026.10.4 or newer.

## Development

See [`dev/README.md`](dev/README.md) for the local test environment (Home Assistant + Paperless-ngx with
synthetic data). Python tests run in Linux/WSL with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy
```

## License

[Apache-2.0](LICENSE)
