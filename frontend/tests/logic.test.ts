import { describe, expect, it, vi } from "vitest";
import { errorCode, signDocuments } from "../src/api";
import {
  buildSearchRequest,
  cardTarget,
  debounce,
  emptySearchState,
  formatDate,
  previewType,
  toggleCategory,
} from "../src/format";
import { localize, pickLanguage } from "../src/localize";
import { fakeHass } from "./helpers";

describe("buildSearchRequest", () => {
  it("leaves out empty filters", () => {
    expect(buildSearchRequest(emptySearchState())).toEqual({ query: "", page: 1, page_size: 25 });
  });

  it("includes filters, sorts categories, trims and limits the query", () => {
    const request = buildSearchRequest({
      query: `  ${"x".repeat(250)}  `,
      categories: [4, 2],
      correspondent: 7,
      dateFrom: "2025-01-01",
      dateTo: "2025-12-31",
      page: 3,
    });
    expect(request).toEqual({
      query: "x".repeat(200),
      categories: [2, 4],
      correspondents: [7],
      date_from: "2025-01-01",
      date_to: "2025-12-31",
      page: 3,
      page_size: 25,
    });
  });

  it("ignores incomplete dates", () => {
    const request = buildSearchRequest({ ...emptySearchState(), dateFrom: "2025-1-1" });
    expect(request.date_from).toBeUndefined();
  });
});

describe("helpers", () => {
  it("toggles categories", () => {
    expect(toggleCategory([1, 2], 2)).toEqual([1]);
    expect(toggleCategory([1], 3)).toEqual([1, 3]);
  });

  it("formats dates without time zone shifts", () => {
    expect(formatDate("2024-03-02", "en")).toBe("Mar 2, 2024");
    expect(formatDate("2024-03-02", "nl")).toContain("2024");
    expect(formatDate(null, "en")).toBe("");
    expect(formatDate("garbage", "en")).toBe("");
  });

  it("knows which files have a preview", () => {
    expect(previewType("application/pdf")).toBe("pdf");
    expect(previewType("image/webp")).toBe("image");
    expect(previewType("text/plain")).toBe("text");
    expect(previewType("application/zip")).toBe("none");
    expect(previewType(null)).toBe("none");
  });

  it("resolves the card target", () => {
    const hass = fakeHass({}, { entities: { "sensor.door": { device_id: "dev-1" } } });
    expect(cardTarget({ type: "x", device_id: "d" }, hass)).toEqual({ kind: "device", id: "d" });
    expect(cardTarget({ type: "x", entity: "sensor.door" }, hass)).toEqual({
      kind: "device",
      id: "dev-1",
    });
    expect(cardTarget({ type: "x", entity: "sensor.unknown" }, hass)).toBeNull();
    expect(cardTarget({ type: "x", area: "kitchen" }, hass)).toEqual({ kind: "area", id: "kitchen" });
    expect(cardTarget({ type: "x" }, hass)).toBeNull();
  });

  it("debounces", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced(1);
    debounced(2);
    vi.advanceTimersByTime(99);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledExactlyOnceWith(2);
    vi.useRealTimers();
  });
});

describe("localize", () => {
  it("picks Dutch or falls back to English", () => {
    expect(pickLanguage("nl-BE")).toBe("nl");
    expect(pickLanguage("fr")).toBe("en");
    expect(pickLanguage(undefined)).toBe("en");
    expect(localize("nl", "search.results", { count: 3 })).toBe("3 documenten");
    expect(localize("de", "search.results", { count: 3 })).toBe("3 documents");
  });
});

describe("api", () => {
  it("signs documents and maps ids", async () => {
    const hass = fakeHass({
      sign_documents: () => ({ paths: { "1": "/api/x/1?authSig=a" } }),
    });
    expect(await signDocuments(hass, [1, 2], "thumb")).toEqual({ 1: "/api/x/1?authSig=a" });
    expect(hass.calls).toEqual([
      { type: "paperless_lookup/sign_documents", document_ids: [1, 2], kind: "thumb" },
    ]);
    expect(await signDocuments(hass, [], "thumb")).toEqual({});
    expect(hass.calls).toHaveLength(1);
  });

  it("reads websocket error codes", () => {
    expect(errorCode({ code: "not_loaded" })).toBe("not_loaded");
    expect(errorCode(new Error("x"))).toBeUndefined();
    expect(errorCode(null)).toBeUndefined();
  });
});
