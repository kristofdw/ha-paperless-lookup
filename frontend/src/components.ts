/** Shared building blocks: document rows, the preview dialog and styles. */

import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import { signDocuments, type HomeAssistant, type PaperlessDocument } from "./api";
import { formatDate, previewType } from "./format";
import { localize } from "./localize";

export const sharedStyles = css`
  :host {
    color: var(--primary-text-color);
    font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, sans-serif));
  }
  button {
    font: inherit;
    cursor: pointer;
  }
  .doc {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    width: 100%;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid var(--divider-color);
    background: none;
    color: inherit;
    text-align: start;
    box-sizing: border-box;
  }
  .doc:hover,
  .doc:focus-visible {
    background: var(--secondary-background-color);
    outline: none;
  }
  .thumb {
    flex: 0 0 48px;
    width: 48px;
    height: 64px;
    object-fit: cover;
    border-radius: 4px;
    background: var(--secondary-background-color);
    border: 1px solid var(--divider-color);
  }
  .doc-body {
    min-width: 0;
    flex: 1;
  }
  .doc-title {
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .doc-meta {
    color: var(--secondary-text-color);
    font-size: 0.9em;
    margin-top: 2px;
  }
  .highlights {
    color: var(--secondary-text-color);
    font-size: 0.85em;
    margin-top: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .highlights mark {
    background: none;
    color: var(--primary-text-color);
    font-weight: 600;
  }
  .message {
    padding: 16px;
    color: var(--secondary-text-color);
  }
  .error {
    color: var(--error-color, #db4437);
  }
  .action {
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    padding: 6px 14px;
    background: var(--card-background-color);
    color: var(--primary-text-color);
  }
  .action.primary {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  a.link {
    color: var(--primary-color);
  }
`;

/** One document row; ``thumb``: signed path, "" for a placeholder, undefined for none. */
export const documentRow = (
  doc: PaperlessDocument,
  language: string,
  onOpen: (doc: PaperlessDocument) => void,
  thumb?: string,
  trailing: TemplateResult | typeof nothing = nothing,
): TemplateResult => {
  const meta = [formatDate(doc.created, language), doc.correspondent_name, doc.category_name]
    .filter(Boolean)
    .join(" · ");
  return html`
    <div class="row">
      <button class="doc" @click=${() => onOpen(doc)}>
        ${thumb === undefined
          ? nothing
          : thumb
            ? html`<img class="thumb" src=${thumb} alt="" loading="lazy" />`
            : html`<span class="thumb"></span>`}
        <span class="doc-body">
          <div class="doc-title">${doc.title}</div>
          <div class="doc-meta">${meta}</div>
          ${doc.highlights?.length
            ? html`<div class="highlights">
                ${doc.highlights.map((segment) =>
                  segment.match ? html`<mark>${segment.text}</mark>` : segment.text,
                )}
              </div>`
            : nothing}
        </span>
      </button>
      ${trailing}
    </div>
  `;
};

/** Whether the browser can show a PDF inline (false in e.g. Android WebView). */
export const canShowPdf = (): boolean => navigator.pdfViewerEnabled !== false;

/** Full-screen preview of a document with open and download actions. */
export class PaperlessLookupPreview extends LitElement {
  declare hass: HomeAssistant;
  declare document: PaperlessDocument;
  declare private _preview?: string;
  declare private _download?: string;
  declare private _thumb?: string;
  declare private _failed: boolean;

  static override properties = {
    hass: { attribute: false },
    document: { attribute: false },
    _preview: { state: true },
    _download: { state: true },
    _thumb: { state: true },
    _failed: { state: true },
  };

  constructor() {
    super();
    this._failed = false;
  }

  private _onKey = (event: KeyboardEvent): void => {
    if (event.key === "Escape") this._close();
  };

  override connectedCallback(): void {
    super.connectedCallback();
    window.addEventListener("keydown", this._onKey);
  }

  override disconnectedCallback(): void {
    window.removeEventListener("keydown", this._onKey);
    super.disconnectedCallback();
  }

  protected override async firstUpdated(): Promise<void> {
    try {
      const id = this.document.id;
      const [preview, download, thumb] = await Promise.all([
        signDocuments(this.hass, [id], "preview"),
        signDocuments(this.hass, [id], "download"),
        canShowPdf() ? Promise.resolve({} as Record<number, string>) : signDocuments(this.hass, [id], "thumb"),
      ]);
      this._preview = preview[id];
      this._download = download[id];
      this._thumb = thumb[id];
      this._failed = this._preview === undefined;
    } catch {
      this._failed = true;
    }
  }

  private _close(): void {
    this.dispatchEvent(new CustomEvent("closed", { bubbles: true, composed: true }));
  }

  private _open(): void {
    if (this._preview) window.open(this.hass.hassUrl(this._preview), "_blank", "noopener");
  }

  private _body(): TemplateResult {
    const lang = this.hass.language;
    if (this._failed) return html`<div class="message error">${localize(lang, "panel.error")}</div>`;
    if (!this._preview) return html`<div class="message">…</div>`;
    switch (previewType(this.document.mime_type)) {
      case "pdf":
        if (!canShowPdf()) {
          // E.g. the Android app (WebView): no PDF viewer. Show the first page and a note.
          return html`<div class="fallback">
            ${this._thumb
              ? html`<img class="page" src=${this._thumb} alt=${this.document.title} />`
              : nothing}
            <div class="message">${localize(lang, "document.no_pdf_viewer")}</div>
          </div>`;
        }
        return html`<iframe src=${this._preview} title=${this.document.title}></iframe>`;
      case "text":
        return html`<iframe src=${this._preview} title=${this.document.title}></iframe>`;
      case "image":
        return html`<img class="full" src=${this._preview} alt=${this.document.title} />`;
      default:
        return html`<div class="message">${localize(lang, "document.no_preview")}</div>`;
    }
  }

  protected override render(): TemplateResult {
    const lang = this.hass.language;
    return html`
      <div class="backdrop" @click=${this._close}></div>
      <section role="dialog" aria-modal="true" aria-label=${this.document.title}>
        <header>
          <h2>${this.document.title}</h2>
          <button class="action" @click=${this._close}>${localize(lang, "document.close")}</button>
        </header>
        <div class="body">${this._body()}</div>
        <footer>
          <button class="action" ?disabled=${!this._preview} @click=${this._open}>
            ${localize(lang, "document.open")}
          </button>
          ${this._download
            ? html`<a class="action primary" href=${this._download} download
                >${localize(lang, "document.download")}</a
              >`
            : nothing}
        </footer>
      </section>
    `;
  }

  static override styles = [
    sharedStyles,
    css`
      :host {
        position: fixed;
        inset: 0;
        z-index: 10;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .backdrop {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
      }
      section {
        position: relative;
        display: flex;
        flex-direction: column;
        width: min(960px, 100vw);
        height: min(92vh, 100dvh);
        background: var(--card-background-color, #fff);
        border-radius: var(--ha-card-border-radius, 12px);
        overflow: hidden;
      }
      header,
      footer {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
      }
      header h2 {
        flex: 1;
        margin: 0;
        font-size: 1.1em;
        overflow-wrap: anywhere;
      }
      footer {
        justify-content: flex-end;
        border-top: 1px solid var(--divider-color);
      }
      footer a {
        text-decoration: none;
      }
      .body {
        flex: 1;
        min-height: 0;
        display: flex;
        background: var(--secondary-background-color);
      }
      iframe {
        flex: 1;
        border: 0;
        background: #fff;
      }
      .fallback {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 16px;
        text-align: center;
      }
      img.page {
        max-width: min(100%, 420px);
        max-height: 70%;
        object-fit: contain;
        background: #fff;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
      }
      img.full {
        max-width: 100%;
        max-height: 100%;
        margin: auto;
        object-fit: contain;
      }
      @media (max-width: 600px) {
        section {
          width: 100vw;
          height: 100dvh;
          border-radius: 0;
        }
      }
    `,
  ];
}
