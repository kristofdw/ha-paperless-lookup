/** Entry point: registers the preview dialog, the panel, the card and its editor. */

import { CARD_TYPE, PaperlessLookupCard, PaperlessLookupCardEditor } from "./card";
import { PaperlessLookupPreview } from "./components";
import { PaperlessLookupPanel } from "./panel";

export const ELEMENTS: [string, CustomElementConstructor][] = [
  ["paperless-lookup-preview", PaperlessLookupPreview],
  ["paperless-lookup-panel", PaperlessLookupPanel],
  [CARD_TYPE, PaperlessLookupCard],
  ["paperless-lookup-card-editor", PaperlessLookupCardEditor],
];

/** Define the elements in the current registry (once). */
export const registerElements = (): void => {
  for (const [tag, element] of ELEMENTS) {
    if (!customElements.get(tag)) customElements.define(tag, element);
  }
};

/**
 * Wait until Home Assistant's frontend is ready, then register.
 *
 * Home Assistant imports this bundle (as an extra module) in parallel with its own code, which
 * replaces ``window.customElements`` with its own registry. Elements defined before that are
 * lost, so on a Home Assistant page we wait until ``home-assistant`` exists in the current
 * registry. ``customElements`` is looked up again on every check on purpose.
 */
export const registerWhenReady = (
  doc: Document = document,
  interval = 50,
  register: () => void = registerElements,
): void => {
  if (!doc.querySelector("home-assistant") || window.customElements.get("home-assistant")) {
    register();
    return;
  }
  const check = (): void => {
    if (window.customElements.get("home-assistant")) register();
    else setTimeout(check, interval);
  };
  setTimeout(check, interval);
};

registerWhenReady();
