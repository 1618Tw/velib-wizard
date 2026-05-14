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

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { ...init });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  stations: () => getJSON<Station[]>("/api/stations"),
  station: (id: string) => getJSON<StationDetail>(`/api/stations/${id}`),
  history: (id: string, hours = 24) =>
    getJSON<HistoryPoint[]>(`/api/stations/${id}/history?hours=${hours}`),
  networkSummary: () => getJSON<NetworkSummary>("/api/network/summary"),
};
