/** Typed access to the Paperless Lookup websocket API (see websocket_api.py). */

export interface HomeAssistant {
  callWS<T>(msg: Record<string, unknown>): Promise<T>;
  hassUrl(path?: string): string;
  language: string;
  locale?: { language: string };
  user?: { id: string; is_admin: boolean; name: string };
  entities?: Record<string, { device_id?: string | null }>;
}

export interface Named {
  id: number;
  name: string;
}

export interface Access {
  allowed: boolean;
  is_admin: boolean;
  categories: Named[];
  device_categories: Named[];
  zigbee2mqtt_fallback: boolean;
}

export interface Filters {
  categories: Named[];
  correspondents: Named[];
  date_min: string | null;
  date_max: string | null;
}

export interface HighlightSegment {
  text: string;
  match: boolean;
}

export interface PaperlessDocument {
  id: number;
  title: string;
  category: number;
  category_name: string | null;
  correspondent: number | null;
  correspondent_name: string | null;
  created: string | null;
  mime_type: string | null;
  models: string[];
  highlights?: HighlightSegment[];
}

export interface SearchResult {
  count: number;
  results: PaperlessDocument[];
}

export interface DeviceDocuments {
  device_id: string;
  name: string;
  documents: PaperlessDocument[];
  zigbee2mqtt_url: string | null;
}

export interface DeviceWithoutManual {
  device_id: string;
  name: string;
  manufacturer: string | null;
  model: string | null;
  model_id: string | null;
  zigbee2mqtt_url: string | null;
}

export type FileKind = "preview" | "thumb" | "download";

export interface SearchRequest {
  query: string;
  categories?: number[];
  correspondents?: number[];
  date_from?: string;
  date_to?: string;
  page: number;
  page_size: number;
}

const DOMAIN = "paperless_lookup";

export const getAccess = (hass: HomeAssistant): Promise<Access> =>
  hass.callWS({ type: `${DOMAIN}/access` });

export const getFilters = (hass: HomeAssistant): Promise<Filters> =>
  hass.callWS({ type: `${DOMAIN}/filters` });

export const search = (hass: HomeAssistant, request: SearchRequest): Promise<SearchResult> =>
  hass.callWS({ type: `${DOMAIN}/search`, ...request });

export const getDeviceDocuments = (
  hass: HomeAssistant,
  deviceId: string,
): Promise<DeviceDocuments> =>
  hass.callWS({ type: `${DOMAIN}/device_documents`, device_id: deviceId });

export const getAreaDocuments = (
  hass: HomeAssistant,
  areaId: string,
): Promise<{ devices: DeviceDocuments[] }> =>
  hass.callWS({ type: `${DOMAIN}/area_documents`, area_id: areaId });

export const getDevicesWithoutManual = (
  hass: HomeAssistant,
): Promise<{ devices: DeviceWithoutManual[] }> =>
  hass.callWS({ type: `${DOMAIN}/devices_without_manual` });

export const linkDocument = (
  hass: HomeAssistant,
  deviceId: string,
  documentId: number,
): Promise<DeviceDocuments> =>
  hass.callWS({ type: `${DOMAIN}/link`, device_id: deviceId, document_id: documentId });

export const unlinkDocument = (
  hass: HomeAssistant,
  deviceId: string,
  documentId: number,
): Promise<DeviceDocuments> =>
  hass.callWS({ type: `${DOMAIN}/unlink`, device_id: deviceId, document_id: documentId });

export const ignoreDevice = (
  hass: HomeAssistant,
  deviceId: string,
  ignored: boolean,
): Promise<{ device_id: string; ignored: boolean }> =>
  hass.callWS({ type: `${DOMAIN}/ignore`, device_id: deviceId, ignored });

/** Return signed, short-lived paths (only for documents the user may see). */
export const signDocuments = async (
  hass: HomeAssistant,
  documentIds: number[],
  kind: FileKind,
): Promise<Record<number, string>> => {
  if (documentIds.length === 0) return {};
  const result = await hass.callWS<{ paths: Record<string, string> }>({
    type: `${DOMAIN}/sign_documents`,
    document_ids: documentIds,
    kind,
  });
  const paths: Record<number, string> = {};
  for (const [id, path] of Object.entries(result.paths)) paths[Number(id)] = path;
  return paths;
};

/** Return the websocket error code of a failed call, if any. */
export const errorCode = (err: unknown): string | undefined =>
  typeof err === "object" && err !== null && "code" in err
    ? String((err as { code: unknown }).code)
    : undefined;
