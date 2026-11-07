/** English and Dutch strings of the panel and the card. */

const en = {
  "panel.title": "Documents",
  "panel.tab_search": "Search",
  "panel.tab_devices": "Devices without manual",
  "panel.no_access": "You have no access to documents. Ask an administrator for access.",
  "panel.not_loaded": "Paperless Lookup is not loaded. Check the integration.",
  "panel.error": "Paperless cannot be reached right now.",
  "search.placeholder": "Search title and content",
  "search.all_stores": "All stores",
  "search.from": "From",
  "search.to": "To",
  "search.clear": "Clear filters",
  "search.results": "{count} documents",
  "search.no_results": "No documents found.",
  "search.more": "Show more",
  "document.open": "Open",
  "document.download": "Download",
  "document.close": "Close",
  "document.no_preview": "No preview available for this file type.",
  "document.no_pdf_viewer": "This app cannot show PDFs. Use Open or Download for the full document.",
  "devices.none": "Every device has a manual.",
  "devices.link": "Link document",
  "devices.ignore": "Ignore",
  "devices.zigbee2mqtt": "Zigbee2MQTT page",
  "devices.search_manual": "Search a document to link",
  "card.no_target": "Choose a device, entity or area in the card editor.",
  "card.no_documents": "No documents.",
  "card.unlink": "Remove link",
  "editor.device": "Device",
  "editor.entity": "Entity (uses its device)",
  "editor.area": "Area",
  "editor.title": "Title",
  "editor.show_thumbnails": "Show thumbnails",
} as const;

type Key = keyof typeof en;

const nl: Record<Key, string> = {
  "panel.title": "Documenten",
  "panel.tab_search": "Zoeken",
  "panel.tab_devices": "Toestellen zonder handleiding",
  "panel.no_access": "Je hebt geen toegang tot documenten. Vraag toegang aan een beheerder.",
  "panel.not_loaded": "Paperless Lookup is niet geladen. Controleer de integratie.",
  "panel.error": "Paperless is nu niet bereikbaar.",
  "search.placeholder": "Zoek in titel en inhoud",
  "search.all_stores": "Alle winkels",
  "search.from": "Van",
  "search.to": "Tot",
  "search.clear": "Filters wissen",
  "search.results": "{count} documenten",
  "search.no_results": "Geen documenten gevonden.",
  "search.more": "Meer tonen",
  "document.open": "Openen",
  "document.download": "Downloaden",
  "document.close": "Sluiten",
  "document.no_preview": "Geen voorbeeld beschikbaar voor dit bestandstype.",
  "document.no_pdf_viewer": "Deze app kan geen pdf tonen. Gebruik Openen of Downloaden voor het volledige document.",
  "devices.none": "Elk toestel heeft een handleiding.",
  "devices.link": "Document koppelen",
  "devices.ignore": "Negeren",
  "devices.zigbee2mqtt": "Zigbee2MQTT-pagina",
  "devices.search_manual": "Zoek een document om te koppelen",
  "card.no_target": "Kies een toestel, entiteit of ruimte in de kaarteditor.",
  "card.no_documents": "Geen documenten.",
  "card.unlink": "Koppeling verwijderen",
  "editor.device": "Toestel",
  "editor.entity": "Entiteit (gebruikt het toestel ervan)",
  "editor.area": "Ruimte",
  "editor.title": "Titel",
  "editor.show_thumbnails": "Miniaturen tonen",
};

const STRINGS: Record<string, Record<Key, string>> = { en, nl };

export type LocalizeKey = Key;

/** Return the language to use: the HA language when translated, else English. */
export const pickLanguage = (language: string | undefined): string => {
  const base = (language ?? "en").toLowerCase().split(/[-_]/)[0];
  return base in STRINGS ? base : "en";
};

export const localize = (
  language: string | undefined,
  key: Key,
  vars: Record<string, string | number> = {},
): string => {
  let text = STRINGS[pickLanguage(language)][key];
  for (const [name, value] of Object.entries(vars)) text = text.replace(`{${name}}`, String(value));
  return text;
};
