/** Sidebar panel: mobile-first document search and, for admins, devices without manual. */

import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import {
  errorCode,
  getAccess,
  getDevicesWithoutManual,
  getFilters,
  ignoreDevice,
  linkDocument,
  search,
  signDocuments,
  type Access,
  type DeviceWithoutManual,
  type Filters,
  type HomeAssistant,
  type PaperlessDocument,
  type Store,
} from "./api";
import { documentRow, sharedStyles } from "./components";
import {
  PAGE_SIZE,
  STORE_SEARCH_THRESHOLD,
  buildSearchRequest,
  debounce,
  emptySearchState,
  matchStores,
  storesForCategories,
  toggleCategory,
  type SearchState,
} from "./format";
import { localize, type LocalizeKey } from "./localize";

type Tab = "search" | "devices";
type Status = "loading" | "ready" | "no_access" | "not_loaded" | "error";

export class PaperlessLookupPanel extends LitElement {
  declare hass: HomeAssistant;
  declare narrow: boolean;
  declare private _status: Status;
  declare private _access?: Access;
  declare private _filters?: Filters;
  declare private _state: SearchState;
  declare private _results: PaperlessDocument[];
  declare private _count: number;
  declare private _searching: boolean;
  declare private _searchError: boolean;
  declare private _thumbs: Record<number, string>;
  declare private _open?: PaperlessDocument;
  declare private _tab: Tab;
  declare private _devices?: DeviceWithoutManual[];
  declare private _linking?: string;
  declare private _linkQuery: string;
  declare private _linkResults: PaperlessDocument[];
  declare private _storeQuery: string;
  declare private _storeOpen: boolean;
  declare private _storeActive: number;

  static override properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    _status: { state: true },
    _access: { state: true },
    _filters: { state: true },
    _state: { state: true },
    _results: { state: true },
    _count: { state: true },
    _searching: { state: true },
    _searchError: { state: true },
    _thumbs: { state: true },
    _open: { state: true },
    _tab: { state: true },
    _devices: { state: true },
    _linking: { state: true },
    _linkQuery: { state: true },
    _linkResults: { state: true },
    _storeQuery: { state: true },
    _storeOpen: { state: true },
    _storeActive: { state: true },
  };

  private _searchSeq = 0;
  private _initialized = false;

  constructor() {
    super();
    this.narrow = false;
    this._status = "loading";
    this._state = emptySearchState();
    this._results = [];
    this._count = 0;
    this._searching = false;
    this._searchError = false;
    this._thumbs = {};
    this._tab = "search";
    this._linkQuery = "";
    this._linkResults = [];
    this._storeQuery = "";
    this._storeOpen = false;
    this._storeActive = 0;
  }

  private _t(key: LocalizeKey, vars?: Record<string, string | number>): string {
    return localize(this.hass?.language, key, vars);
  }

  protected override updated(): void {
    if (this.hass && !this._initialized) {
      this._initialized = true;
      void this._load();
    }
  }

  private async _load(): Promise<void> {
    try {
      this._access = await getAccess(this.hass);
      if (!this._access.allowed) {
        this._status = "no_access";
        return;
      }
      this._filters = await getFilters(this.hass);
      this._status = "ready";
      await this._search();
    } catch (err) {
      this._status = errorCode(err) === "not_loaded" ? "not_loaded" : "error";
    }
  }

  private async _search(append = false): Promise<void> {
    const seq = ++this._searchSeq;
    this._searching = true;
    this._searchError = false;
    try {
      const result = await search(this.hass, buildSearchRequest(this._state));
      if (seq !== this._searchSeq) return;
      this._results = append ? [...this._results, ...result.results] : result.results;
      this._count = result.count;
      const missing = result.results.map((doc) => doc.id).filter((id) => !(id in this._thumbs));
      const thumbs = await signDocuments(this.hass, missing, "thumb");
      if (seq === this._searchSeq) this._thumbs = { ...this._thumbs, ...thumbs };
    } catch {
      if (seq === this._searchSeq) this._searchError = true;
    } finally {
      if (seq === this._searchSeq) this._searching = false;
    }
  }

  private _debouncedSearch = debounce(() => void this._search(), 300);

  private _update(changes: Partial<SearchState>, debounced = false): void {
    this._state = { ...this._state, ...changes, page: changes.page ?? 1 };
    if (debounced) this._debouncedSearch();
    else void this._search(changes.page !== undefined && changes.page > 1);
  }

  /** Stores with documents in the selected categories. */
  private _stores(categories = this._state.categories): Store[] {
    return storesForCategories(this._filters?.correspondents ?? [], categories);
  }

  private _toggleCategory(id: number): void {
    const categories = toggleCategory(this._state.categories, id);
    const { correspondent } = this._state;
    const stillListed = this._stores(categories).some((store) => store.id === correspondent);
    this._update(stillListed ? { categories } : { categories, correspondent: null });
  }

  private _clearFilters = (): void => {
    this._storeQuery = "";
    this._storeOpen = false;
    this._update(emptySearchState());
  };

  private _pickStore(id: number | null): void {
    this._storeQuery = "";
    this._storeOpen = false;
    this._update({ correspondent: id });
  }

  private _onStoreKey(event: KeyboardEvent, matches: Store[]): void {
    if (event.key === "Escape") {
      this._storeOpen = false;
      return;
    }
    if (event.key === "Enter") {
      const match = matches[this._storeActive];
      if (this._storeOpen && match) this._pickStore(match.id);
      return;
    }
    if ((event.key !== "ArrowDown" && event.key !== "ArrowUp") || !matches.length) return;
    event.preventDefault();
    this._storeOpen = true;
    const step = event.key === "ArrowDown" ? 1 : -1;
    this._storeActive = (this._storeActive + step + matches.length) % matches.length;
    void this.updateComplete.then(() =>
      this.renderRoot.querySelector(".store-list .active")?.scrollIntoView?.({ block: "nearest" }),
    );
  }

  private _storeFilter(): TemplateResult | typeof nothing {
    const stores = this._stores();
    if (!stores.length) return nothing;
    return stores.length > STORE_SEARCH_THRESHOLD
      ? this._storePicker(stores)
      : this._storeSelect(stores);
  }

  private _storeSelect(stores: Store[]): TemplateResult {
    const selected = this._state.correspondent;
    return html`<select
      aria-label=${this._t("search.all_stores")}
      @change=${(event: Event) => {
        const value = (event.target as HTMLSelectElement).value;
        this._update({ correspondent: value ? Number(value) : null });
      }}
    >
      <option value="" ?selected=${selected === null}>${this._t("search.all_stores")}</option>
      ${stores.map(
        (store) =>
          html`<option value=${store.id} ?selected=${selected === store.id}>${store.name}</option>`,
      )}
    </select>`;
  }

  /** Search field with a suggestion list, for long store lists. */
  private _storePicker(stores: Store[]): TemplateResult {
    const selected = stores.find((store) => store.id === this._state.correspondent);
    const open = this._storeOpen;
    const matches = matchStores(stores, this._storeQuery);
    return html`<div class="store-picker">
      <input
        type="text"
        role="combobox"
        autocomplete="off"
        aria-autocomplete="list"
        aria-expanded=${open}
        aria-controls="store-list"
        aria-label=${this._t("search.find_store")}
        placeholder=${this._t("search.find_store")}
        .value=${open ? this._storeQuery : (selected?.name ?? "")}
        @focus=${() => {
          this._storeQuery = "";
          this._storeActive = 0;
          this._storeOpen = true;
        }}
        @blur=${() => (this._storeOpen = false)}
        @input=${(event: Event) => {
          this._storeQuery = (event.target as HTMLInputElement).value;
          this._storeActive = 0;
          this._storeOpen = true;
        }}
        @keydown=${(event: KeyboardEvent) => this._onStoreKey(event, matches)}
      />
      ${selected && !open
        ? html`<button
            class="store-clear"
            aria-label=${this._t("search.clear_store")}
            title=${this._t("search.clear_store")}
            @click=${() => this._pickStore(null)}
          >
            ✕
          </button>`
        : nothing}
      ${open
        ? html`<ul id="store-list" class="store-list" role="listbox">
            ${matches.length
              ? matches.map(
                  (store, index) =>
                    html`<li
                      role="option"
                      aria-selected=${store.id === selected?.id}
                      class=${index === this._storeActive ? "active" : ""}
                      @mousedown=${(event: Event) => {
                        // Keep the focus, so the blur does not close the list before the pick.
                        event.preventDefault();
                        this._pickStore(store.id);
                      }}
                    >
                      ${store.name}
                    </li>`,
                )
              : html`<li class="none">${this._t("search.no_stores")}</li>`}
          </ul>`
        : nothing}
    </div>`;
  }

  private async _loadDevices(): Promise<void> {
    try {
      this._devices = (await getDevicesWithoutManual(this.hass)).devices;
    } catch {
      this._devices = [];
    }
  }

  private _selectTab(tab: Tab): void {
    this._tab = tab;
    if (tab === "devices" && this._devices === undefined) void this._loadDevices();
  }

  private async _searchLink(query: string): Promise<void> {
    this._linkQuery = query;
    const categories = this._access?.device_categories.map((item) => item.id) ?? [];
    if (!categories.length) {
      this._linkResults = [];
      return;
    }
    const result = await search(this.hass, { query, categories, page: 1, page_size: 10 });
    this._linkResults = result.results;
  }

  private _debouncedLinkSearch = debounce((query: string) => void this._searchLink(query), 300);

  private async _link(deviceId: string, documentId: number): Promise<void> {
    await linkDocument(this.hass, deviceId, documentId);
    this._linking = undefined;
    await this._loadDevices();
  }

  private async _ignore(deviceId: string): Promise<void> {
    await ignoreDevice(this.hass, deviceId, true);
    await this._loadDevices();
  }

  // ---- Rendering ------------------------------------------------------------------------------

  protected override render(): TemplateResult {
    return html`
      <header class="toolbar">
        <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
        <h1>${this._t("panel.title")}</h1>
      </header>
      ${this._status === "ready" && this._access?.is_admin
        ? html`<nav class="tabs" role="tablist">
            ${(["search", "devices"] as Tab[]).map(
              (tab) => html`<button
                role="tab"
                aria-selected=${this._tab === tab}
                class=${this._tab === tab ? "tab active" : "tab"}
                @click=${() => this._selectTab(tab)}
              >
                ${this._t(tab === "search" ? "panel.tab_search" : "panel.tab_devices")}
              </button>`,
            )}
          </nav>`
        : nothing}
      <main>${this._content()}</main>
      ${this._open
        ? html`<paperless-lookup-preview
            .hass=${this.hass}
            .document=${this._open}
            @closed=${() => (this._open = undefined)}
          ></paperless-lookup-preview>`
        : nothing}
    `;
  }

  private _content(): TemplateResult {
    switch (this._status) {
      case "loading":
        return html`<div class="message">…</div>`;
      case "no_access":
        return html`<div class="message">${this._t("panel.no_access")}</div>`;
      case "not_loaded":
        return html`<div class="message">${this._t("panel.not_loaded")}</div>`;
      case "error":
        return html`<div class="message error">${this._t("panel.error")}</div>`;
      default:
        return this._tab === "devices" ? this._devicesTab() : this._searchTab();
    }
  }

  private _searchTab(): TemplateResult {
    const filters = this._filters;
    const lang = this.hass.language;
    const state = this._state;
    return html`
      <div class="search">
        <input
          type="search"
          enterkeyhint="search"
          .value=${state.query}
          placeholder=${this._t("search.placeholder")}
          aria-label=${this._t("search.placeholder")}
          @input=${(event: Event) =>
            this._update({ query: (event.target as HTMLInputElement).value }, true)}
        />
        <div class="chips" role="group">
          ${filters?.categories.map(
            (category) => html`<button
              class=${state.categories.includes(category.id) ? "chip selected" : "chip"}
              aria-pressed=${state.categories.includes(category.id)}
              @click=${() => this._toggleCategory(category.id)}
            >
              ${category.name}
            </button>`,
          )}
        </div>
        <div class="filters">
          ${this._storeFilter()}
          <label
            >${this._t("search.from")}
            <input
              type="date"
              .value=${state.dateFrom}
              min=${filters?.date_min ?? nothing}
              max=${filters?.date_max ?? nothing}
              @change=${(event: Event) =>
                this._update({ dateFrom: (event.target as HTMLInputElement).value })}
          /></label>
          <label
            >${this._t("search.to")}
            <input
              type="date"
              .value=${state.dateTo}
              min=${filters?.date_min ?? nothing}
              max=${filters?.date_max ?? nothing}
              @change=${(event: Event) =>
                this._update({ dateTo: (event.target as HTMLInputElement).value })}
          /></label>
          <button class="action" @click=${this._clearFilters}>
            ${this._t("search.clear")}
          </button>
        </div>
      </div>
      <div class="results" aria-live="polite" aria-busy=${this._searching}>
        ${this._searchError
          ? html`<div class="message error">${this._t("panel.error")}</div>`
          : !this._results.length && !this._searching
            ? html`<div class="message">${this._t("search.no_results")}</div>`
            : html`<div class="count">${this._t("search.results", { count: this._count })}</div>
                ${this._results.map((doc) =>
                  documentRow(doc, lang, (item) => (this._open = item), this._thumbs[doc.id] ?? ""),
                )}
                ${this._count > state.page * PAGE_SIZE
                  ? html`<button
                      class="action more"
                      ?disabled=${this._searching}
                      @click=${() => this._update({ page: state.page + 1 })}
                    >
                      ${this._t("search.more")}
                    </button>`
                  : nothing}`}
      </div>
    `;
  }

  private _devicesTab(): TemplateResult {
    if (this._devices === undefined) return html`<div class="message">…</div>`;
    if (!this._devices.length) return html`<div class="message">${this._t("devices.none")}</div>`;
    const lang = this.hass.language;
    return html`<ul class="devices">
      ${this._devices.map(
        (device) => html`<li>
          <div class="device-head">
            <div class="doc-body">
              <div class="doc-title">${device.name}</div>
              <div class="doc-meta">
                ${[device.manufacturer, device.model, device.model_id].filter(Boolean).join(" · ")}
              </div>
            </div>
            ${device.zigbee2mqtt_url
              ? html`<a class="link" href=${device.zigbee2mqtt_url} target="_blank" rel="noreferrer"
                  >${this._t("devices.zigbee2mqtt")}</a
                >`
              : nothing}
          </div>
          <div class="device-actions">
            <button
              class="action primary"
              @click=${() => {
                this._linking = this._linking === device.device_id ? undefined : device.device_id;
                if (this._linking) void this._searchLink(device.model_id ?? device.model ?? "");
              }}
            >
              ${this._t("devices.link")}
            </button>
            <button class="action" @click=${() => this._ignore(device.device_id)}>
              ${this._t("devices.ignore")}
            </button>
          </div>
          ${this._linking === device.device_id
            ? html`<div class="link-search">
                <input
                  type="search"
                  .value=${this._linkQuery}
                  placeholder=${this._t("devices.search_manual")}
                  aria-label=${this._t("devices.search_manual")}
                  @input=${(event: Event) =>
                    this._debouncedLinkSearch((event.target as HTMLInputElement).value)}
                />
                ${this._linkResults.map((doc) =>
                  documentRow(doc, lang, () => this._link(device.device_id, doc.id)),
                )}
              </div>`
            : nothing}
        </li>`,
      )}
    </ul>`;
  }

  static override styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        min-height: 100vh;
        background: var(--primary-background-color);
      }
      .toolbar {
        display: flex;
        align-items: center;
        gap: 4px;
        height: var(--header-height, 56px);
        padding: 0 12px;
        background: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        position: sticky;
        top: 0;
        z-index: 2;
      }
      h1 {
        margin: 0;
        font-size: 20px;
        font-weight: 400;
      }
      .tabs {
        display: flex;
        background: var(--card-background-color);
        border-bottom: 1px solid var(--divider-color);
      }
      .tab {
        flex: 1;
        padding: 12px;
        border: none;
        border-bottom: 2px solid transparent;
        background: none;
        color: var(--secondary-text-color);
      }
      .tab.active {
        color: var(--primary-color);
        border-bottom-color: var(--primary-color);
      }
      main {
        max-width: 900px;
        margin: 0 auto;
      }
      .search {
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      input,
      select {
        font: inherit;
        color: var(--primary-text-color);
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        padding: 10px 12px;
        box-sizing: border-box;
      }
      input[type="search"] {
        width: 100%;
        font-size: 16px; /* no zoom on iOS */
      }
      .chips {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 2px;
      }
      .chip {
        flex: none;
        border: 1px solid var(--divider-color);
        border-radius: 16px;
        padding: 6px 12px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
      }
      .chip.selected {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .filters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
      .store-picker {
        position: relative;
        flex: 1 1 220px;
        max-width: 340px;
      }
      .store-picker input {
        width: 100%;
        padding-right: 36px;
      }
      .store-clear {
        position: absolute;
        top: 0;
        right: 0;
        height: 100%;
        width: 36px;
        border: none;
        background: none;
        color: var(--secondary-text-color);
      }
      .store-list {
        position: absolute;
        z-index: 3;
        top: 100%;
        left: 0;
        right: 0;
        margin: 4px 0 0;
        padding: 4px 0;
        max-height: 260px;
        overflow-y: auto;
        list-style: none;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }
      .store-list li {
        padding: 10px 12px;
        cursor: pointer;
      }
      .store-list li.active,
      .store-list li:hover {
        background: var(--secondary-background-color);
      }
      .store-list li.none {
        color: var(--secondary-text-color);
        cursor: default;
      }
      .filters label {
        display: flex;
        align-items: center;
        gap: 6px;
        color: var(--secondary-text-color);
      }
      .results,
      .devices {
        background: var(--card-background-color);
        border-radius: var(--ha-card-border-radius, 12px);
        margin: 0 12px 24px;
        overflow: hidden;
      }
      .row {
        display: flex;
        align-items: center;
      }
      .count {
        padding: 10px 12px;
        color: var(--secondary-text-color);
        border-bottom: 1px solid var(--divider-color);
      }
      .more {
        display: block;
        margin: 12px auto;
      }
      .devices {
        list-style: none;
        padding: 0;
      }
      .devices li {
        padding: 12px;
        border-bottom: 1px solid var(--divider-color);
      }
      .device-head {
        display: flex;
        gap: 12px;
        align-items: center;
      }
      .device-actions {
        display: flex;
        gap: 8px;
        margin-top: 8px;
      }
      .link-search {
        margin-top: 8px;
      }
      .link-search input {
        width: 100%;
      }
    `,
  ];
}
