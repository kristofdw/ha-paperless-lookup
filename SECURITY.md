# Security policy

Paperless Lookup gives Home Assistant users access to documents such as receipts and invoices, so
security reports are welcome and handled with priority.

## Supported versions

Only the latest release gets security fixes.

## Reporting a vulnerability

Please do **not** open a public issue. Report it privately through GitHub instead:
[Report a vulnerability](https://github.com/kristofdw/ha-paperless-lookup/security/advisories/new)
(tab *Security* of this repository).

Include the version, what an attacker needs (for example a Home Assistant user without access to a
category), and the steps to reproduce. Use synthetic documents only: never attach real documents, tokens
or addresses of your own servers.

You get a first answer within a week. A fix is released as soon as possible, and the advisory is published
after the release, crediting you unless you prefer otherwise.

## Scope

In scope, for example:

- a Home Assistant user who can see, search, open or download a document of a category they may not see,
  or a document without the access tag;
- the Paperless API token reaching the browser, logs, diagnostics or another place outside the config
  entry;
- signed file links that can be reused for another document or user, or after they expire.

Out of scope: vulnerabilities in Home Assistant or Paperless-ngx themselves (report those to those
projects), and an administrator who sees all categories while *Administrators see all categories* is on
(that is by design).

The security model is described in the [README](README.md#security-model).
