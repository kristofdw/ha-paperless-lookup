/** Pure helpers shared by the panel and the card (unit tested). */

import type { HomeAssistant, SearchRequest } from "./api";

export interface SearchState {
  query: string;
  categories: number[];
  correspondent: number | null;
  dateFrom: string;
  dateTo: string;
  page: number;
}

export const PAGE_SIZE = 25;

export const emptySearchState = (): SearchState => ({
  query: "",
  categories: [],
  correspondent: null,
  dateFrom: "",
  dateTo: "",
  page: 1,
});

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Build the websocket request for a search state; empty filters are left out. */
export const buildSearchRequest = (state: SearchState): SearchRequest => {
  const request: SearchRequest = {
    query: state.query.trim().slice(0, 200),
    page: state.page,
    page_size: PAGE_SIZE,
  };
  if (state.categories.length) request.categories = [...state.categories].sort((a, b) => a - b);
  if (state.correspondent !== null) request.correspondents = [state.correspondent];
  if (ISO_DATE.test(state.dateFrom)) request.date_from = state.dateFrom;
  if (ISO_DATE.test(state.dateTo)) request.date_to = state.dateTo;
  return request;
};

/** Toggle a category chip. */
export const toggleCategory = (categories: number[], id: number): number[] =>
  categories.includes(id) ? categories.filter((item) => item !== id) : [...categories, id];

/** Format an ISO date (YYYY-MM-DD) for the user's language, without time zone shifts. */
export const formatDate = (iso: string | null, language: string): string => {
  if (!iso || !ISO_DATE.test(iso)) return "";
  const [year, month, day] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat(language, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
};

export type PreviewType = "pdf" | "image" | "text" | "none";

/** How a file can be shown inline. */
export const previewType = (mime: string | null): PreviewType => {
  if (!mime) return "none";
  if (mime === "application/pdf") return "pdf";
  if (["image/jpeg", "image/png", "image/webp", "image/gif"].includes(mime)) return "image";
  if (mime === "text/plain") return "text";
  return "none";
};

export interface CardConfig {
  type: string;
  device_id?: string;
  entity?: string;
  area?: string;
  title?: string;
  show_thumbnails?: boolean;
}

export type CardTarget = { kind: "device"; id: string } | { kind: "area"; id: string } | null;

/** Resolve what a card shows: a device (directly or through an entity) or an area. */
export const cardTarget = (config: CardConfig, hass: HomeAssistant | undefined): CardTarget => {
  if (config.device_id) return { kind: "device", id: config.device_id };
  if (config.entity) {
    const deviceId = hass?.entities?.[config.entity]?.device_id;
    return deviceId ? { kind: "device", id: deviceId } : null;
  }
  if (config.area) return { kind: "area", id: config.area };
  return null;
};

/** Return a debounced version of a function. */
export const debounce = <A extends unknown[]>(fn: (...args: A) => void, wait: number) => {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return (...args: A): void => {
    if (timer !== undefined) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
};
