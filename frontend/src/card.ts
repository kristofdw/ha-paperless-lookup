/** Dashboard card: the documents of a device (directly or through an entity) or an area. */

import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import {
  errorCode,
  getAreaDocuments,
  getDeviceDocuments,
  signDocuments,
  unlinkDocument,
  type DeviceDocuments,
  type HomeAssistant,
  type PaperlessDocument,
} from "./api";
import { documentRow, sharedStyles } from "./components";
import { cardTarget, type CardConfig, type CardTarget } from "./format";
import { localize, type LocalizeKey } from "./localize";

export const CARD_TYPE = "paperless-lookup-card";

export class PaperlessLookupCard extends LitElement {
  declare hass?: HomeAssistant;
  declare private _config?: CardConfig;
  declare private _devices?: DeviceDocuments[];
  declare private _error?: LocalizeKey;
  declare private _thumbs: Record<number, string>;
  declare private _open?: PaperlessDocument;

  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
    _devices: { state: true },
    _error: { state: true },
    _thumbs: { state: true },
    _open: { state: true },
  };

  private _loadedFor?: string;

  constructor() {
    super();
    this._thumbs = {};
  }

  static getConfigElement(): HTMLElement {
    return document.createElement("paperless-lookup-card-editor");
  }

  static getStubConfig(): CardConfig {
    return { type: `custom:${CARD_TYPE}` };
  }

  setConfig(config: CardConfig): void {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    this._config = { show_thumbnails: true, ...config };
    this._loadedFor = undefined;
  }

  getCardSize(): number {
    const count = this._devices?.reduce((sum, device) => sum + device.documents.length, 0) ?? 1;
    return 1 + Math.min(count, 6);
  }

  private _t(key: LocalizeKey): string {
    return localize(this.hass?.language, key);
  }

  protected override updated(): void {
    if (!this.hass || !this._config) return;
    const target = cardTarget(this._config, this.hass);
    const key = target ? `${target.kind}:${target.id}` : "none";
    if (key !== this._loadedFor) {
      this._loadedFor = key;
      void this._load(target);
    }
  }

  private async _load(target: CardTarget): Promise<void> {
    if (!this.hass || !target) {
      this._devices = undefined;
      this._error = target ? undefined : "card.no_target";
      return;
    }
    try {
      this._devices =
        target.kind === "device"
          ? [await getDeviceDocuments(this.hass, target.id)]
          : (await getAreaDocuments(this.hass, target.id)).devices;
      this._error = undefined;
      if (this._config?.show_thumbnails) {
        const ids = this._devices.flatMap((device) => device.documents.map((doc) => doc.id));
        this._thumbs = await signDocuments(this.hass, ids, "thumb");
      }
    } catch (err) {
      this._devices = undefined;
      this._error = errorCode(err) === "not_loaded" ? "panel.not_loaded" : "panel.error";
    }
  }

  private async _unlink(deviceId: string, doc: PaperlessDocument): Promise<void> {
    if (!this.hass) return;
    const updated = await unlinkDocument(this.hass, deviceId, doc.id);
    this._devices = this._devices?.map((device) =>
      device.device_id === deviceId ? updated : device,
    );
  }

  private _device(device: DeviceDocuments, showName: boolean): TemplateResult {
    const lang = this.hass?.language ?? "en";
    const isAdmin = this.hass?.user?.is_admin ?? false;
    return html`
      ${showName ? html`<div class="device">${device.name}</div>` : nothing}
      ${device.documents.map((doc) =>
        documentRow(
          doc,
          lang,
          (item) => (this._open = item),
          this._config?.show_thumbnails ? (this._thumbs[doc.id] ?? "") : undefined,
          isAdmin
            ? html`<button
                class="unlink"
                title=${this._t("card.unlink")}
                aria-label=${this._t("card.unlink")}
                @click=${() => this._unlink(device.device_id, doc)}
              >
                ✕
              </button>`
            : nothing,
        ),
      )}
      ${device.zigbee2mqtt_url
        ? html`<div class="fallback">
            <a class="link" href=${device.zigbee2mqtt_url} target="_blank" rel="noreferrer"
              >${this._t("devices.zigbee2mqtt")}</a
            >
          </div>`
        : nothing}
    `;
  }

  protected override render(): TemplateResult {
    const config = this._config;
    if (!config) return html``;
    const devices = this._devices ?? [];
    const empty = devices.every((device) => !device.documents.length && !device.zigbee2mqtt_url);
    return html`
      <ha-card .header=${config.title ?? nothing}>
        ${this._error
          ? html`<div class="message ${this._error === "card.no_target" ? "" : "error"}">
              ${this._t(this._error)}
            </div>`
          : this._devices === undefined
            ? html`<div class="message">…</div>`
            : empty
              ? html`<div class="message">${this._t("card.no_documents")}</div>`
              : devices.map((device) => this._device(device, devices.length > 1 || !!config.area))}
      </ha-card>
      ${this._open && this.hass
        ? html`<paperless-lookup-preview
            .hass=${this.hass}
            .document=${this._open}
            @closed=${() => (this._open = undefined)}
          ></paperless-lookup-preview>`
        : nothing}
    `;
  }

  static override styles = [
    sharedStyles,
    css`
      .device {
        padding: 12px 12px 4px;
        font-weight: 500;
        color: var(--secondary-text-color);
      }
      .row {
        display: flex;
        align-items: center;
      }
      .unlink {
        border: none;
        background: none;
        color: var(--secondary-text-color);
        padding: 12px;
      }
      .fallback {
        padding: 10px 12px;
      }
    `,
  ];
}

/** Visual editor of the card, built on Home Assistant's own ha-form and selectors. */
export class PaperlessLookupCardEditor extends LitElement {
  declare hass?: HomeAssistant;
  declare private _config?: CardConfig;

  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  setConfig(config: CardConfig): void {
    this._config = config;
  }

  private _schema = [
    { name: "device_id", selector: { device: {} } },
    { name: "entity", selector: { entity: {} } },
    { name: "area", selector: { area: {} } },
    { name: "title", selector: { text: {} } },
    { name: "show_thumbnails", selector: { boolean: {} } },
  ];

  private _label = (schema: { name: string }): string =>
    localize(this.hass?.language, `editor.${schema.name === "device_id" ? "device" : schema.name}` as LocalizeKey);

  private _changed(event: CustomEvent<{ value: CardConfig }>): void {
    const config: CardConfig = { ...event.detail.value, type: `custom:${CARD_TYPE}` };
    for (const key of ["device_id", "entity", "area", "title"] as const) {
      if (!config[key]) delete config[key];
    }
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
    );
  }

  protected override render(): TemplateResult {
    if (!this.hass || !this._config) return html``;
    return html`<ha-form
      .hass=${this.hass}
      .data=${{ show_thumbnails: true, ...this._config }}
      .schema=${this._schema}
      .computeLabel=${this._label}
      @value-changed=${this._changed}
    ></ha-form>`;
  }
}

declare global {
  interface Window {
    customCards?: { type: string; name: string; description: string; preview?: boolean }[];
  }
}

window.customCards = window.customCards ?? [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Paperless Lookup",
    description: "Documents (manuals, receipts, …) of a device or an area.",
  });
}
