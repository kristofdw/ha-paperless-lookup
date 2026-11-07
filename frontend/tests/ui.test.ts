import { afterEach, describe, expect, it, vi } from "vitest";
import { registerWhenReady } from "../src/main";
import type { PaperlessLookupCard } from "../src/card";
import type { PaperlessLookupPanel } from "../src/panel";
import { doc, fakeHass, settle, text } from "./helpers";

const access = (allowed = true, is_admin = false) => ({
  allowed,
  is_admin,
  categories: allowed ? [{ id: 1, name: "Manual" }, { id: 2, name: "Receipt" }] : [],
  device_categories: allowed ? [{ id: 1, name: "Manual" }] : [],
  zigbee2mqtt_fallback: true,
});

const filters = () => ({
  categories: [
    { id: 1, name: "Manual" },
    { id: 2, name: "Receipt" },
  ],
  correspondents: [{ id: 1, name: "IKEA" }],
  date_min: "2022-08-14",
  date_max: "2026-10-30",
});

afterEach(() => {
  document.body.innerHTML = "";
});

const mountPanel = async (hass: ReturnType<typeof fakeHass>) => {
  const panel = document.createElement("paperless-lookup-panel") as PaperlessLookupPanel;
  panel.hass = hass;
  document.body.append(panel);
  await settle(panel);
  return panel;
};

describe("panel", () => {
  it("shows the no-access screen without searching", async () => {
    const hass = fakeHass({ access: () => access(false) });
    const panel = await mountPanel(hass);

    expect(text(panel)).toContain("You have no access to documents");
    expect(hass.calls.map((call) => call.type)).toEqual(["paperless_lookup/access"]);
  });

  it("shows not loaded and connection errors", async () => {
    const notLoaded = await mountPanel(
      fakeHass({
        access: () => {
          throw { code: "not_loaded" };
        },
      }),
    );
    expect(text(notLoaded)).toContain("not loaded");
    document.body.innerHTML = "";
    const failed = await mountPanel(
      fakeHass({
        access: () => {
          throw { code: "cannot_connect" };
        },
      }),
    );
    expect(text(failed)).toContain("cannot be reached");
  });

  it("searches, shows results with highlights and filters by category", async () => {
    const hass = fakeHass({
      access: () => access(),
      filters,
      search: (msg) => ({
        count: msg.categories ? 1 : 2,
        results: msg.categories
          ? [doc(5, { title: "Groceries receipt", category: 2, category_name: "Receipt" })]
          : [
              doc(1, {
                title: "TRADFRI remote control manual",
                highlights: [
                  { text: "TRADFRI ", match: false },
                  { text: "remote", match: true },
                  { text: "<b>not markup</b>", match: false },
                ],
              }),
              doc(5, { title: "Groceries receipt", category: 2, category_name: "Receipt" }),
            ],
      }),
      sign_documents: (msg) => ({
        paths: Object.fromEntries(
          (msg.document_ids as number[]).map((id) => [String(id), `/thumb/${id}?authSig=x`]),
        ),
      }),
    });
    const panel = await mountPanel(hass);
    const root = panel.shadowRoot!;

    expect(text(panel)).toContain("2 documents");
    expect(text(panel)).toContain("TRADFRI remote control manual");
    expect(root.querySelector("mark")?.textContent).toBe("remote");
    // Highlights are text, never HTML.
    expect(root.querySelector(".highlights b")).toBeNull();
    expect(root.querySelector("img.thumb")?.getAttribute("src")).toBe("/thumb/1?authSig=x");
    // No tabs for non-admins.
    expect(root.querySelector(".tabs")).toBeNull();

    const chip = [...root.querySelectorAll<HTMLButtonElement>(".chip")].find(
      (button) => button.textContent?.trim() === "Receipt",
    )!;
    chip.click();
    await settle(panel);

    const last = hass.calls.filter((call) => call.type === "paperless_lookup/search").at(-1);
    expect(last).toMatchObject({ categories: [2], page: 1 });
    expect(text(panel)).toContain("1 documents");
    expect(chip.getAttribute("aria-pressed")).toBe("true");
  });

  it("opens the preview with signed paths", async () => {
    const hass = fakeHass({
      access: () => access(),
      filters,
      search: () => ({ count: 1, results: [doc(1)] }),
      sign_documents: (msg) => ({
        paths: { "1": `/api/paperless_lookup/document/1/${String(msg.kind)}?authSig=x` },
      }),
    });
    const panel = await mountPanel(hass);
    panel.shadowRoot!.querySelector<HTMLButtonElement>("button.doc")!.click();
    await settle(panel);
    const preview = panel.shadowRoot!.querySelector("paperless-lookup-preview")!;
    await settle(preview as HTMLElement);

    expect(preview.shadowRoot!.querySelector("iframe")?.getAttribute("src")).toBe(
      "/api/paperless_lookup/document/1/preview?authSig=x",
    );
    expect(preview.shadowRoot!.querySelector("a[download]")?.getAttribute("href")).toBe(
      "/api/paperless_lookup/document/1/download?authSig=x",
    );
    preview.shadowRoot!.querySelector<HTMLButtonElement>("header button")!.click();
    await settle(panel);
    expect(panel.shadowRoot!.querySelector("paperless-lookup-preview")).toBeNull();
  });

  it("shows the first page when the app has no PDF viewer", async () => {
    Object.defineProperty(navigator, "pdfViewerEnabled", { value: false, configurable: true });
    try {
      const hass = fakeHass({
        access: () => access(),
        filters,
        search: () => ({ count: 1, results: [doc(1)] }),
        sign_documents: (msg) => ({ paths: { "1": `/${String(msg.kind)}/1?authSig=x` } }),
      });
      const panel = await mountPanel(hass);
      panel.shadowRoot!.querySelector<HTMLButtonElement>("button.doc")!.click();
      await settle(panel);
      const preview = panel.shadowRoot!.querySelector("paperless-lookup-preview")!;
      await settle(preview as HTMLElement);

      expect(preview.shadowRoot!.querySelector("iframe")).toBeNull();
      expect(preview.shadowRoot!.querySelector("img.page")?.getAttribute("src")).toBe(
        "/thumb/1?authSig=x",
      );
      expect(text(preview)).toContain("cannot show PDFs");
    } finally {
      Object.defineProperty(navigator, "pdfViewerEnabled", { value: true, configurable: true });
    }
  });

  it("lets admins link a document to a device without manual", async () => {
    let devices = [
      {
        device_id: "dev-1",
        name: "Coffee plug",
        manufacturer: "Example",
        model: "Smart plug",
        model_id: "PLUG-01",
        zigbee2mqtt_url: "https://www.zigbee2mqtt.io/devices/PLUG-01.html",
      },
    ];
    const hass = fakeHass({
      access: () => access(true, true),
      filters,
      search: () => ({ count: 1, results: [doc(4, { title: "Plug manual" })] }),
      sign_documents: () => ({ paths: {} }),
      devices_without_manual: () => ({ devices }),
      link: () => {
        devices = [];
        return {};
      },
      ignore: () => ({}),
    });
    const panel = await mountPanel(hass);
    const root = panel.shadowRoot!;
    root.querySelectorAll<HTMLButtonElement>(".tab")[1].click();
    await settle(panel);

    expect(text(panel)).toContain("Coffee plug");
    expect(root.querySelector("a.link")?.getAttribute("href")).toContain("PLUG-01");
    root.querySelector<HTMLButtonElement>(".device-actions .primary")!.click();
    await settle(panel);
    const linkSearch = hass.calls.filter((call) => call.type === "paperless_lookup/search").at(-1);
    expect(linkSearch).toMatchObject({ query: "PLUG-01", categories: [1] });

    root.querySelector<HTMLButtonElement>(".link-search button.doc")!.click();
    await settle(panel);
    expect(hass.calls.at(-2)).toEqual({
      type: "paperless_lookup/link",
      device_id: "dev-1",
      document_id: 4,
    });
    expect(text(panel)).toContain("Every device has a manual");
  });
});

const mountCard = async (hass: ReturnType<typeof fakeHass>, config: Record<string, unknown>) => {
  const card = document.createElement("paperless-lookup-card") as PaperlessLookupCard;
  card.setConfig({ type: "custom:paperless-lookup-card", ...config });
  card.hass = hass;
  document.body.append(card);
  await settle(card);
  return card;
};

describe("card", () => {
  it("shows the documents of an entity's device", async () => {
    const hass = fakeHass(
      {
        device_documents: (msg) => ({
          device_id: msg.device_id,
          name: "Remote",
          documents: [doc(1, { title: "TRADFRI remote control manual" })],
          zigbee2mqtt_url: null,
        }),
        sign_documents: () => ({ paths: { "1": "/thumb/1" } }),
      },
      { entities: { "sensor.remote_battery": { device_id: "dev-remote" } } },
    );
    const card = await mountCard(hass, { entity: "sensor.remote_battery", title: "Manual" });

    expect(hass.calls[0]).toEqual({
      type: "paperless_lookup/device_documents",
      device_id: "dev-remote",
    });
    expect(text(card)).toContain("TRADFRI remote control manual");
    expect(card.shadowRoot!.querySelector("img.thumb")?.getAttribute("src")).toBe("/thumb/1");
    expect(card.shadowRoot!.querySelector(".unlink")).toBeNull(); // not an admin
    expect(card.getCardSize()).toBe(2);
  });

  it("shows the Zigbee2MQTT fallback and the empty state", async () => {
    const hass = fakeHass({
      device_documents: () => ({
        device_id: "d",
        name: "Plug",
        documents: [],
        zigbee2mqtt_url: "https://www.zigbee2mqtt.io/devices/PLUG-01.html",
      }),
      sign_documents: () => ({ paths: {} }),
    });
    const card = await mountCard(hass, { device_id: "d" });
    expect(card.shadowRoot!.querySelector("a.link")?.getAttribute("href")).toContain("PLUG-01");

    const empty = await mountCard(
      fakeHass({
        area_documents: () => ({ devices: [] }),
        sign_documents: () => ({ paths: {} }),
      }),
      { area: "kitchen", show_thumbnails: false },
    );
    expect(text(empty)).toContain("No documents.");
  });

  it("asks for a target and reports errors", async () => {
    const none = await mountCard(fakeHass({}), {});
    expect(text(none)).toContain("Choose a device");

    const failed = await mountCard(
      fakeHass({
        device_documents: () => {
          throw { code: "not_found" };
        },
      }),
      { device_id: "x" },
    );
    expect(text(failed)).toContain("cannot be reached");
  });

  it("lets admins remove a link", async () => {
    const hass = fakeHass(
      {
        device_documents: () => ({
          device_id: "d",
          name: "Washer",
          documents: [doc(8, { title: "Washing machine invoice" })],
          zigbee2mqtt_url: null,
        }),
        unlink: () => ({ device_id: "d", name: "Washer", documents: [], zigbee2mqtt_url: null }),
        sign_documents: () => ({ paths: {} }),
      },
      { user: { id: "a", is_admin: true, name: "Admin" } },
    );
    const card = await mountCard(hass, { device_id: "d" });
    card.shadowRoot!.querySelector<HTMLButtonElement>(".unlink")!.click();
    await settle(card);

    expect(hass.calls.at(-1)).toEqual({
      type: "paperless_lookup/unlink",
      device_id: "d",
      document_id: 8,
    });
    expect(text(card)).toContain("No documents.");
  });

  it("is registered for the card picker with a stub config and an editor", async () => {
    const card = customElements.get("paperless-lookup-card") as unknown as {
      getStubConfig(): unknown;
      getConfigElement(): HTMLElement;
    };
    expect(card.getStubConfig()).toEqual({ type: "custom:paperless-lookup-card" });
    expect(card.getConfigElement().tagName.toLowerCase()).toBe("paperless-lookup-card-editor");
    expect(window.customCards?.some((item) => item.type === "paperless-lookup-card")).toBe(true);
  });

  it("editor emits a clean config", async () => {
    const editor = document.createElement("paperless-lookup-card-editor") as HTMLElement & {
      hass: unknown;
      setConfig(config: unknown): void;
    };
    editor.hass = fakeHass({});
    editor.setConfig({ type: "custom:paperless-lookup-card" });
    document.body.append(editor);
    await settle(editor);
    const events: unknown[] = [];
    editor.addEventListener("config-changed", (event) =>
      events.push((event as CustomEvent).detail.config),
    );
    const form = editor.shadowRoot!.querySelector("ha-form")!;
    form.dispatchEvent(
      new CustomEvent("value-changed", {
        detail: { value: { device_id: "d", entity: "", title: "", show_thumbnails: false } },
      }),
    );

    expect(events).toEqual([
      { type: "custom:paperless-lookup-card", device_id: "d", show_thumbnails: false },
    ]);
  });
});

describe("registration", () => {
  it("registers at once outside Home Assistant", () => {
    const register = vi.fn();
    registerWhenReady(document.implementation.createHTMLDocument(), 1, register);
    expect(register).toHaveBeenCalledOnce();
  });

  it("waits until Home Assistant's registry has the app element", async () => {
    const doc = document.implementation.createHTMLDocument();
    doc.body.append(doc.createElement("home-assistant"));
    const register = vi.fn();
    registerWhenReady(doc, 1, register);
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(register).not.toHaveBeenCalled();

    customElements.define("home-assistant", class extends HTMLElement {});
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(register).toHaveBeenCalledOnce();
  });
});
