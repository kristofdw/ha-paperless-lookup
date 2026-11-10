# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Until 1.0.0, a minor version may contain
breaking changes; they are listed under **Changed**.

## [Unreleased]

## [0.1.0] - 2026-11-11

First release.

### Added

- Connection to Paperless-ngx 3.0.0 or newer (REST API version 10) through one read-only Paperless user,
  with checks of the version and permissions, warnings for `http://` and for a user that can do more
  than read, re-authentication and reconfiguration.
- Opt-in with an access tag (default `HA`): only documents with that tag in an enabled category are
  visible in Home Assistant.
- Categories are Paperless document types, with access per category per Home Assistant user.
  Administrators see all categories unless switched off.
- Options as a menu: access tag and visibility, categories, users per category, devices, and following
  who opens documents. Changes are stored with *Save and close*.
- Sidebar panel for phones: search in titles and content, filters per category, store and date, preview,
  open and download. Choose which users get the sidebar item.
- Dashboard card `custom:paperless-lookup-card` for a device, an entity or an area, with a visual editor.
- Automatic links between manuals and devices through the custom field `HA model`, manual links, ignored
  devices, removed automatic links that stay removed, and an optional link to the Zigbee2MQTT page.
- Panel tab *Devices without manual* for administrators.
- Logbook entries for opened and downloaded documents, per user and category, in the language of Home
  Assistant (English and Dutch).
- Files are streamed through Home Assistant with signed links that expire after 60 seconds, after a live
  check in Paperless; only PDF, common image types and plain text, with a size limit.
- Diagnostics without tokens, URLs, user names or document titles, and repair issues for an unsupported
  Paperless version, missing permissions and a missing access tag.
- Translations in English and Dutch.

[Unreleased]: https://github.com/kristofdw/ha-paperless-lookup/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kristofdw/ha-paperless-lookup/releases/tag/v0.1.0
