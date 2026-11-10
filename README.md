# Paperless Lookup for Home Assistant

*[Nederlands](docs/README.nl.md)*

A custom integration, installed through the [Marketplace](https://www.home-assistant.io/integrations/marketplace/)
(formerly HACS), that makes selected [Paperless-ngx](https://docs.paperless-ngx.com/)
documents searchable in [Home Assistant](https://www.home-assistant.io/):

- **Manuals linked to devices:** see the manual of a device in Home Assistant, on a dashboard card or in
  the sidebar panel.
- **Look things up on the go:** search receipts, invoices and warranty documents from your phone
  (Home Assistant Companion app), filtered by category, store and date, including the text in the
  documents (OCR).
- **Opt-in:** only documents with an access tag (default `HA`) are visible in Home Assistant.
- **Access per category per Home Assistant user:** for example manuals for everyone, receipts only for
  some users.
- **Read-only and private:** Home Assistant talks to Paperless over your local network. Browsers and
  phones never get a Paperless token, and nothing is stored in Home Assistant except links and settings.

## Contents

1. [Requirements](#requirements)
2. [Prepare Paperless-ngx](#1-prepare-paperless-ngx)
3. [Install the integration](#2-install-the-integration)
4. [Add the integration](#3-add-the-integration)
5. [Choose who sees what (options)](#4-choose-who-sees-what-options)
6. [Use it](#5-use-it)
7. [Link manuals to devices](#6-link-manuals-to-devices)
8. [How data is updated](#how-data-is-updated)
9. [Security model](#security-model)
10. [Known limitations](#known-limitations)
11. [Troubleshooting](#troubleshooting)
12. [Update and remove](#update-and-remove)
13. [Development](#development)

## Requirements

| What | Version |
|---|---|
| Home Assistant | 2026.11.0 or newer (includes the Marketplace) |
| Paperless-ngx | 3.0.0 or newer (REST API version 10) |

Home Assistant must be able to reach Paperless over the network (for example `http://paperless.local:8000`).
Your phone only needs to reach Home Assistant.

## 1. Prepare Paperless-ngx

Do this in the Paperless web interface as an administrator. Menu names below are those of Paperless-ngx 3
(English interface).

### 1.1 The access tag

Create a tag **`HA`** (*Attributes → Tags → Create*). Only documents with this tag can ever be shown in
Home Assistant; everything else stays invisible, also for Home Assistant administrators. You can use
another name and choose it later in the options.

Add the tag to the documents you want to see in Home Assistant. A document can have several tags, so
this does not interfere with your other tags.

> **Tip: tag automatically.** Create a workflow (*Workflows → Create*) with the triggers *Document added*
> and *Document updated*, a filter on the document types you want in Home Assistant, and an assignment
> action that adds the tag `HA`. Every receipt or manual then gets the tag automatically.

### 1.2 Categories (document types)

A **category** in Home Assistant is a Paperless **document type**: for example *Manual*, *Receipt*,
*Invoice*, *Warranty*. Access is granted per category, so give every document you release a document
type (*Attributes → Document Types*). Documents without a document type are never shown.

### 1.3 Custom field for device models (for manuals)

To link manuals to devices automatically, create a custom field **`HA model`** of type **Text**
(*Attributes → Custom Fields*). Fill it in on each manual with the device model, or several models
separated by `;`, for example `E1524/E1810` or `RTCGQ11LM; MCCGQ11LM`. See
[Link manuals to devices](#6-link-manuals-to-devices) for which model to use.

### 1.4 A dedicated Paperless user for Home Assistant

Create a user, for example `ha-lookup` (*Users & Groups → Add User*):

- *Active* on, *Admin* and *Superuser* **off**.
- Permissions: only **View** on the rows *Document*, *Tag*, *Correspondent*, *DocumentType*,
  *CustomField* and *UISettings*. No *Add*, *Change* or *Delete* anywhere: the integration never writes
  to Paperless. *UISettings* lets the integration see which user the token belongs to.

**Object permissions (important).** In Paperless, a document, tag, document type or correspondent with an
**owner** is only visible to other users when it is shared with them. Objects without an owner are
visible to every user with the view permission. Make sure the `ha-lookup` user can see:

- the tag `HA`,
- the document types you want as categories,
- the correspondents (stores) of those documents,
- the documents themselves.

Open the object (*Edit*), go to *Permissions* and add the user under *View*. To do many at once, use
*Select* and then *Permissions* on the lists under *Attributes*, or select documents in the document
list and set their permissions in bulk. A quick check: log in to Paperless
as `ha-lookup` and look at the documents with the `HA` tag. What you see there is the most Home Assistant
can ever show.

### 1.5 API token

Log in to Paperless as `ha-lookup`, open *My Profile* (user menu at the top right) and generate an
**API Auth Token**. Copy it; you enter it in Home Assistant in step 3. Treat it like a password.

## 2. Install the integration

### With the Marketplace (recommended)

Home Assistant 2026.11 replaced HACS with the built-in Marketplace. This integration is not in the
Marketplace catalog yet, so add it from its GitHub link:

1. Go to *Settings →* **Marketplace**.
2. Select **Add from link** (top right). Under **GitHub link**, enter
   `https://github.com/kristofdw/ha-paperless-lookup` (or `kristofdw/ha-paperless-lookup`) → **Add**.
   The Marketplace asks you to connect GitHub first if you have not done that yet. If it asks for the
   type, choose **Integration**.
3. Open **Paperless Lookup for Home Assistant** and install it. The Marketplace warns that it is made and
   supported by its author, not by the Home Assistant project. The Marketplace installs the latest
   release; see the [changelog](CHANGELOG.md) for what changed.
4. **Restart Home Assistant** when the Marketplace asks for it (a repair offers the restart), or via
   *Settings → System → ⏻ → Restart Home Assistant*.

Already installed with HACS? Nothing to do: Home Assistant 2026.11 moves your repositories and updates
to the Marketplace.

### Manually

Copy the folder `custom_components/paperless_lookup` of this repository to the `custom_components`
folder of your Home Assistant configuration (create it if needed), so you get
`<config>/custom_components/paperless_lookup/manifest.json`. Restart Home Assistant.

## 3. Add the integration

[![Open your Home Assistant instance and start setting up Paperless Lookup.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=paperless_lookup)

Or: *Settings → Devices & services → Add integration →* **Paperless Lookup**.

| Field | What to enter |
|---|---|
| URL | The address of Paperless as Home Assistant reaches it, for example `http://192.168.1.10:8000` or `https://paperless.example.org`. Include a sub-path if Paperless runs under one (`https://example.org/paperless`). Use the final address: redirects are not followed. |
| API token | The token of `ha-lookup` from step 1.5. |
| Verify SSL certificate | Leave on. Only switch off for a self-signed certificate on your own network. |

The integration then checks the connection, the Paperless version and the permissions of the user.
Two warnings may follow; you can continue after each:

- **Unencrypted connection**: the address starts with `http://`. Fine on a trusted home network; use
  `https://` when Paperless sits behind a reverse proxy.
- **Paperless user can do more than read**: the token belongs to a superuser or to a user with add,
  change or delete permissions. A user with view permissions only (step 1.4) is safer.

The entry is named after the Paperless user (for example `ha-lookup`). Only one Paperless connection is
supported.

**What you get right away (defaults):**

- access tag: the tag named `HA` (if it exists),
- every document type is a category, but **without users**: only Home Assistant administrators see
  documents until you grant access in the options,
- device category: the document type named *Manual* (or *Handleiding*), model field: the text field
  `HA model`,
- a sidebar item **Paperless Lookup** and the dashboard card `custom:paperless-lookup-card`,
- the list of documents is refreshed every 60 minutes.

## 4. Choose who sees what (options)

*Settings → Devices & services → Paperless Lookup →* **Configure**. The options are a menu; every choice
in the lists comes live from Paperless. After each step you return to the menu. Changes are only stored
with **Save and close**; closing the dialog with ✕ discards them.

- **Access tag and visibility**
  - *Access tag*: the tag that releases documents (without one, nothing is visible).
  - *Administrators see all categories*: on by default. Switch it off to give administrators access per
    category too.
  - *Users who see Paperless Lookup in the sidebar*: choose who gets the menu item. With nobody chosen,
    everyone gets it. This only concerns the menu item: which documents someone may see (also on
    dashboard cards) is set under *Users per category*. A user with the menu item but without any
    category sees an empty panel.
- **Categories**: choose which document types are categories in Home Assistant. Documents of other
  types are not visible. Afterwards the dialog continues with *Users per category*.
- **Users per category**: choose, per category, the Home Assistant users that may see it. Example:
  *Manual* for everyone, *Receipt* and *Invoice* only for two users, nothing for a wall tablet's user.
  Administrators see every category while *Administrators see all categories* is on, so they need not
  be chosen.
- **Devices**
  - *Device categories*: the categories that are linked to devices by model (usually *Manual*; a
    *Warranty* category works too).
  - *Model field*: the text custom field with the models (`HA model`).
  - *Zigbee2MQTT link as fallback*: for a Zigbee2MQTT device without manual, link to its page on
    zigbee2mqtt.io.
- **Follow who opens documents**: choose, per user, the categories whose opened and downloaded
  documents are written to the Home Assistant logbook (see
  [Follow who opens what](#follow-who-opens-what)). Off by default.

Only Home Assistant administrators can open these options. The integration reloads after Save and close.

### Follow who opens what

Paperless cannot tell which Home Assistant user opened a document: every request comes from the one
Paperless user of the integration, and Paperless' audit log only records changes. The integration can
write reads to the Home Assistant **logbook** instead, for example to follow *Invoice* for some users
and ignore *Manual*:

1. *Configure →* **Follow who opens documents**.
2. Per user, tick the categories to follow. Each user only gets the categories they may see; users who
   may not see any category are named below the form instead (there is nothing they can open).

Each preview or download of a followed category then gives a logbook entry such as *"Alex opened
Paperless document 5 (Receipt)"*: the user, the time, the document number and the category, never the
title (the logbook is stored in the Home Assistant database). Thumbnails are not logged, and opening the
same file again within a minute counts once. A file that the browser still has in its cache (up to 5
minutes) does not reach Home Assistant again, so it is not logged again either. The text is in the
language of Home Assistant (*Settings → System → General*), not in each user's own language.

To see only these entries, open *Settings → Devices & services → Paperless Lookup →* the device
**Paperless Lookup** (its logbook card), or filter the logbook on that device. The document number is
the id in Paperless (`/documents/<number>/details`).

## 5. Use it

### The sidebar panel

**Paperless Lookup** in the sidebar (or `/paperless-lookup`) is made for the phone:

- search in titles and content,
- filter chips per category and a date range,
- a store filter that only lists stores with documents in the selected categories, and becomes a search
  field when there are many stores,
- results with a thumbnail, date, store, category and the matched words,
- tap a result for a preview with **Open** and **Download**,
- for administrators: a tab **Devices without manual** (see section 6).

Users without access to any category see a "no access" message. To remove the menu item for some users,
use *Users who see Paperless Lookup in the sidebar* in the options; it is applied through each user's
sidebar settings, so a user can bring it back under *Profile*. The documents stay protected in the
backend either way: opening the panel by its address only shows the categories that user has access to.

> On Android, the Companion app cannot show PDF files inline. The preview then shows the first page;
> use **Open** or **Download** for the full document.

### The dashboard card

Add a card with *Edit dashboard → Add card →* **Paperless Lookup**; the visual editor lets you pick a
device, an entity (its device is used) or an area. In YAML:

```yaml
# The manuals (and other linked documents) of a device
type: custom:paperless-lookup-card
device_id: 0123456789abcdef0123456789abcdef
title: Manual
```

```yaml
# The device of an entity
type: custom:paperless-lookup-card
entity: sensor.washing_machine_power
```

```yaml
# All devices with documents in an area, without thumbnails
type: custom:paperless-lookup-card
area: kitchen
show_thumbnails: false
```

The device ID, entity and area (an area ID) above are examples: replace them with your own, or let the
visual editor fill them in. The card only shows documents of categories the viewing user may see.
Administrators can remove a link with ✕.

## 6. Link manuals to devices

A document of a device category is linked to every device whose model matches one of the models in its
`HA model` field. Matching ignores upper/lower case, spaces and the characters `-`, `_`, `/`, `(` and `)`.
The models of a device are compared, with and without the manufacturer in front:

- the **model ID** of the device (Zigbee2MQTT: the Zigbee model, for example `E1524/E1810`),
- the **model** (for example `TRADFRI remote control`),
- a part in parentheses of the model (older Zigbee2MQTT versions: `TRADFRI remote control (E1524/E1810)`).

You find these on the device page in Home Assistant (*Settings → Devices & services → Devices →* the
device: the line under the name shows the model and manufacturer; *Model ID* is in the device info).
Models of fewer than three characters are ignored to avoid accidental matches.

The panel tab **Devices without manual** (administrators) lists enabled devices that have a model but no
document of a device category. Per device you can:

- **Link document**: search a document and link it by hand (any category, for example an invoice),
- **Ignore**: hide the device from this list (for devices that never get a manual),
- open the **Zigbee2MQTT page** when the fallback is on.

Removing an automatic link (✕ on the card) is remembered: the document stays unlinked from that device.

## How data is updated

- **Search** always asks Paperless directly, and a new document that a search finds is added to the list
  at once.
- **Files** are fetched from Paperless when someone opens them; Home Assistant keeps no copy.
- **The list of released documents** (filter lists, device links, *Devices without manual*) is read from
  Paperless every 60 minutes. To update it sooner, reload the integration (*⋮ → Reload*).

## Security model

- **Opt-in in Paperless**: only documents with the access tag in an enabled category are reachable.
  Everything else answers "not found", also for administrators, so not even the existence of a document
  leaks.
- **Access is checked in the backend** for every request: every websocket command and every file request
  goes through one central check of the Home Assistant user and the category. Search requests to
  Paperless are always limited to the access tag and the allowed categories, and the results are checked
  again in Home Assistant. Hiding a card is not used as protection.
- **Files** (preview, thumbnail, download) are streamed through Home Assistant with signed links that
  expire after 60 seconds. Before streaming, the document is checked live in Paperless (tag and category),
  so removing the tag takes effect immediately. Only PDF, common image types and plain text are passed
  on, with a size limit. A file a browser already loaded may stay in its cache for up to 5 minutes.
- **The API token** is stored in the Home Assistant config entry, like other integrations do. It is not
  encrypted on disk, but it is part of encrypted Home Assistant backups. It is never logged, never sent to
  the browser and redacted in diagnostics. Diagnostics contain no URLs, user names or document titles.
- **Read-only**: the integration never changes anything in Paperless. Paperless' audit log records
  changes, not reads; to follow which Home Assistant user opens what, use the
  option [Follow who opens documents](#follow-who-opens-what).

To report a security problem, see [SECURITY.md](SECURITY.md).

## Known limitations

- **One Paperless connection**, through one Paperless user.
- **Read-only**: documents, tags and notes cannot be changed from Home Assistant.
- **No entities or actions**: the integration offers a panel and a card, so there is nothing to use in
  automations.
- **No access rights per sidebar item in Home Assistant**: *Users who see Paperless Lookup in the sidebar*
  only hides the menu item. Access to documents is set per category.
- **Administrators see every category** while *Administrators see all categories* is on, so don't use an
  administrator account on a shared device such as a wall tablet.
- **File types**: only PDF, common image types and plain text can be opened. An Office document can be
  opened only when Paperless has a PDF version of it.
- **File size**: at most 100 MiB per document and 5 MiB per thumbnail.
- **Search** matches whole words. The advanced query syntax of Paperless is not supported.
- **Child devices** are not linked to manuals. Models of fewer than three characters are ignored.
- **Android**: the Companion app cannot show PDF files inline (see [the panel](#the-sidebar-panel)).

## Troubleshooting

**Errors when adding the integration**

| Message | Cause and fix |
|---|---|
| Failed to connect to Paperless | Home Assistant cannot reach the URL, or Paperless answered with a redirect or a server error. Check the address from the Home Assistant host (not from your PC) and use the final URL. |
| No Paperless-ngx API found at this address | The URL does not point at Paperless. Check the port and a sub-path. |
| The API token was rejected | Wrong or regenerated token. Generate a new one (step 1.5). |
| The Paperless user lacks these permissions: … | Give the user the listed view permissions (step 1.4). `view_uisettings` is the one most often missing. |
| This Paperless version is not supported | Update Paperless-ngx to 3.0.0 or newer. |

**I see no documents (or not all)**

1. Do the documents have the access tag, and is that tag chosen in *Options → Access tag*?
2. Is their document type a category (*Options → Categories*), and does your user have access to it
   under *Options → Users per category* (or are you an administrator with *Administrators see all
   categories* on)? Being chosen for the sidebar item is not enough.
3. Can the Paperless user see them? Log in to Paperless as that user (step 1.4, object permissions).
   A tag or document type it cannot see does not appear in the options lists either.
4. New or changed documents appear in search right away. For device links and the filter lists, wait
   for the next refresh (at most 60 minutes) or reload the integration (*⋮ → Reload*).

**Messages under *Settings → System → Repairs***

| Message | Cause and fix |
|---|---|
| Paperless-ngx version not supported | Update Paperless-ngx to 3.0.0 or newer, then reload the integration. |
| Paperless user lacks permissions | Give the user the listed view permissions (step 1.4), then reload the integration. |
| Paperless access tag not available | No tag is chosen, or the Paperless user cannot see it, so no documents are visible. Create or share the tag (steps 1.1 and 1.4), or choose another one in the options. |

**A manual does not appear on a device**: compare the `HA model` value with the model and model ID on the
device page (section 6), and check that its document type is a device category. You can always link it
by hand from *Devices without manual*.

**The card says "Custom element doesn't exist"**: refresh the browser page (clear the cache of the
Companion app if needed) after installing or updating.

**Token changed or user deleted**: Home Assistant shows a re-authentication request; enter a token of
the **same** Paperless user. To change the address or the certificate check, use *⋮ → Reconfigure*.
Switching to another Paperless user requires removing and adding the integration (the options refer to
that user's view of Paperless).

**Diagnostics**: *Settings → Devices & services → Paperless Lookup → ⋮ → Download diagnostics* gives
versions, permissions and counts, without token, URL, names or titles. Attach it to an issue.

## Update and remove

- **Update**: updates appear under *Settings → Updates*, like other Home Assistant updates. Install,
  restart Home Assistant (a repair offers the restart), then refresh the browser.
- **Remove**: *Settings → Devices & services → Paperless Lookup → ⋮ → Delete*. The stored manual links
  are deleted with it. Then remove the repository under *Settings → Marketplace* (or delete the folder) and restart. Delete the
  `ha-lookup` user or its token in Paperless if you no longer need it.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for issues and pull requests, [`AGENTS.md`](AGENTS.md) for the
build and test commands and [`dev/README.md`](dev/README.md) for the local test environment (Home
Assistant + Paperless-ngx with synthetic data). In short (Python in Linux/WSL, frontend with node 24):

```bash
bash script/uv sync
bash script/uv run pytest
bash script/uv run pre-commit run --all-files
cd frontend && npm ci && npm run check
```

## License

[Apache-2.0](LICENSE)
