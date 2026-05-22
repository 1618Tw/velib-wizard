const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Station = {
  station_id: string;
  name: string;
  lat: number;
  lon: number;
  capacity: number;
  bikes: number | null;
  docks: number | null;
  last_ts: string | null;
};

export type StationDetail = Station & {
  poi_counts: Record<string, number> | null;
  cluster_id: number | null;
};

export type HistoryPoint = {
  ts: string;
  bikes: number;
  docks: number;
};

export type NetworkSummary = {
  total: number;
  empty: number;
  full: number;
  last_ts: string | null;
};

export type ForecastStation = {
  station_id: string;
  name: string;
  lat: number;
  lon: number;
  capacity: number;
  risk_bike: number;
  risk_dock: number;
  predicted_pct: number | null;
  model_version: string;
  computed_at: string;
};

export type ForecastsRisk = {
  horizon_minutes: number;
  n_stations: number;
  stations: ForecastStation[];
};

export type StatusOverview = {
  ok: boolean;
  checked_at: string;
  process_started_at: string;
  uptime_seconds: number;
  gbfs_reachable: boolean;
  data: {
    stations: number;
    forecasts: number;
    snapshots_total: number;
    snapshots_last_hour: number;
    snapshots_last_24h: number;
    last_snapshot_ts: string | null;
    first_snapshot_ts: string | null;
    minutes_since_last_snapshot: number | null;
    database_bytes: number;
  };
  sparkline: { bucket: string; n: number }[];
};

function assertJSON(res: Response, path: string) {
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) {
    throw new Error(`API asleep or unreachable (got HTML instead of JSON) on ${path}`);
  }
}

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { ...init });
  assertJSON(res, path);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return res.json() as Promise<T>;
}

/** Like getJSON but doesn't throw on non-2xx — the /api/status endpoint
 *  intentionally returns 503 with a valid payload when data is stale. */
async function getJSONLenient<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  assertJSON(res, path);
  return res.json() as Promise<T>;
}

export const api = {
  stations: () => getJSON<Station[]>("/api/stations"),
  station: (id: string) => getJSON<StationDetail>(`/api/stations/${id}`),
  history: (id: string, hours = 24) =>
    getJSON<HistoryPoint[]>(`/api/stations/${id}/history?hours=${hours}`),
  networkSummary: () => getJSON<NetworkSummary>("/api/network/summary"),
  status: () => getJSONLenient<StatusOverview>("/api/status"),
  forecastsRisk: (horizon: number) =>
    getJSON<ForecastsRisk>(`/api/forecasts/risk?horizon=${horizon}`),
};
