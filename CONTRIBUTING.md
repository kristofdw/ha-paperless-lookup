# Contributing

Thanks for helping! Bug reports, translations and pull requests are welcome.

## Issues

- **Bug:** open an [issue](https://github.com/kristofdw/ha-paperless-lookup/issues) with the versions of
  Home Assistant, Paperless-ngx and this integration, what you expected and what happened. Attach the
  diagnostics (*Settings → Devices & services → Paperless Lookup → ⋮ → Download diagnostics*): they
  contain no token, URL, user names or document titles.
- **Security problem:** do not open an issue, see [SECURITY.md](SECURITY.md).
- Never post real documents, tokens or addresses of your own servers. Screenshots only with test data.

## Development

The build and test commands, the conventions and the security rules are in [`AGENTS.md`](AGENTS.md)
(written for both people and AI agents). [`dev/README.md`](dev/README.md) explains the local test
environment: Home Assistant and Paperless-ngx in Docker with synthetic documents.

In short:

- Python tooling runs on Linux or WSL: `bash script/uv sync`, `bash script/uv run pytest` (coverage gate
  95 %) and `bash script/uv run pre-commit run --all-files`.
- The frontend (TypeScript and Lit) is in `frontend/`: `npm ci && npm run check`. Commit the rebuilt
  bundle `custom_components/paperless_lookup/frontend/paperless-lookup.js` together with the sources.
- Enable the git hook once per clone: `git config core.hooksPath script/git-hooks`.

## Pull requests

- One topic per pull request, with tests. CI (lint, tests on the minimum and latest Home Assistant,
  frontend, hassfest and the Marketplace validation) must pass.
- Code, comments, documentation and commit messages in English.
- Add a line under *Unreleased* in [CHANGELOG.md](CHANGELOG.md) for changes users notice.
- No new Python dependencies.
- Changes to access control (`access.py`, the websocket commands and the file view) need a test for every
  case a user may **not** see.

## Translations

Texts are in `custom_components/paperless_lookup/strings.json` (English) and `translations/<language>.json`.
Copy `translations/en.json` to a new language file and translate the values; keep the keys and the
`{placeholders}`. The panel and the card take their texts from `frontend/src/localize.ts`; add the language
there too and rebuild the bundle.

## License

By contributing you agree that your contribution is licensed under the [Apache-2.0](LICENSE) license.
