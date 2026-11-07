import type { HomeAssistant, PaperlessDocument } from "../src/api";

export type Handler = (msg: Record<string, unknown>) => unknown;

/** A fake hass whose callWS answers from handlers per command type. */
export const fakeHass = (
  handlers: Record<string, Handler>,
  extra: Partial<HomeAssistant> = {},
): HomeAssistant & { calls: Record<string, unknown>[] } => {
  const calls: Record<string, unknown>[] = [];
  return {
    calls,
    language: "en",
    hassUrl: (path = "") => `http://ha.test${path}`,
    user: { id: "u1", is_admin: false, name: "User" },
    callWS: async <T>(msg: Record<string, unknown>): Promise<T> => {
      calls.push(msg);
      const type = String(msg.type).replace("paperless_lookup/", "");
      const handler = handlers[type];
      if (!handler) throw { code: "unknown_command", message: type };
      return (await handler(msg)) as T;
    },
    ...extra,
  };
};

export const doc = (id: number, extra: Partial<PaperlessDocument> = {}): PaperlessDocument => ({
  id,
  title: `Document ${id}`,
  category: 1,
  category_name: "Manual",
  correspondent: 1,
  correspondent_name: "IKEA",
  created: "2024-03-02",
  mime_type: "application/pdf",
  models: [],
  ...extra,
});

/** Wait until Lit has rendered and pending promises settled. */
export const settle = async (element: HTMLElement & { updateComplete?: Promise<unknown> }) => {
  for (let i = 0; i < 5; i++) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await element.updateComplete;
  }
};

export const text = (element: Element): string =>
  (element.shadowRoot?.textContent ?? "").replace(/\s+/g, " ").trim();
