"use client";

import { useQuery } from "@tanstack/react-query";
import maplibregl, { Map as MLMap, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bike, ParkingCircle, X } from "lucide-react";

import { api, type Station } from "@/lib/api";

const PARIS_CENTER: [number, number] = [2.3522, 48.8566];
const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

type Mode = "bike" | "dock";

function colorForRatio(bikes: number | null, docks: number | null, mode: Mode): string {
  if (bikes === null || docks === null) return "#94a3b8";
  const total = bikes + docks;
  if (total === 0) return "#94a3b8";
  const supply = mode === "bike" ? bikes : docks;
  if (supply === 0) return "#dc2626";
  const ratio = supply / total;
  if (ratio < 0.15) return "#f59e0b";
  return "#16a34a";
}

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [mode, setMode] = useState<Mode>("bike");
  const [selected, setSelected] = useState<Station | null>(null);

  const { data: stations = [] } = useQuery({
    queryKey: ["stations"],
    queryFn: api.stations,
    refetchInterval: 60_000,
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: PARIS_CENTER,
      zoom: 11.5,
      attributionControl: { compact: true },
    });
    mapRef.current.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || stations.length === 0) return;

    const fc = {
      type: "FeatureCollection" as const,
      features: stations.map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: {
          station_id: s.station_id,
          color: colorForRatio(s.bikes, s.docks, mode),
        },
      })),
    };

    const apply = () => {
      const src = map.getSource("stations") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(fc);
        return;
      }
      map.addSource("stations", { type: "geojson", data: fc });
      map.addLayer({
        id: "stations-dots",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 2.5, 14, 6, 17, 10],
          "circle-color": ["get", "color"],
          "circle-stroke-width": 1,
          "circle-stroke-color": "#0b1220",
          "circle-opacity": 0.95,
        },
      });
      const onClick = (e: MapMouseEvent) => {
        const features = map.queryRenderedFeatures(e.point, { layers: ["stations-dots"] });
        const f = features[0];
        if (!f) return;
        const id = f.properties?.station_id as string;
        const found = stations.find((s) => s.station_id === id) ?? null;
        setSelected(found);
      };
      map.on("click", "stations-dots", onClick);
      map.on("mouseenter", "stations-dots", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "stations-dots", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [stations, mode]);

  return (
    <div className="relative flex-1 min-h-0">
      <div ref={containerRef} className="absolute inset-0" />

      <div className="absolute top-3 left-3 z-10 bg-white/90 dark:bg-zinc-900/90 backdrop-blur rounded-lg shadow-sm border border-zinc-200 dark:border-zinc-800 p-1 flex gap-1 text-xs">
        <button
          onClick={() => setMode("bike")}
          className={`px-2 py-1 rounded-md flex items-center gap-1 ${
            mode === "bike" ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <Bike size={14} /> Bikes
        </button>
        <button
          onClick={() => setMode("dock")}
          className={`px-2 py-1 rounded-md flex items-center gap-1 ${
            mode === "dock" ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <ParkingCircle size={14} /> Docks
        </button>
      </div>

      <div className="absolute top-3 right-14 z-10 bg-white/90 dark:bg-zinc-900/90 backdrop-blur rounded-lg shadow-sm border border-zinc-200 dark:border-zinc-800 px-3 py-1.5 text-xs">
        {stations.length.toLocaleString()} stations
      </div>

      {selected && <StationPanel station={selected} onClose={() => setSelected(null)} mode={mode} />}
    </div>
  );
}

function StationPanel({ station, onClose, mode }: { station: Station; onClose: () => void; mode: Mode }) {
  const supply = mode === "bike" ? station.bikes : station.docks;
  const supplyLabel = mode === "bike" ? "bikes" : "docks";
  return (
    <aside className="absolute right-3 top-3 bottom-3 w-80 max-w-[calc(100%-1.5rem)] z-10 bg-white dark:bg-zinc-900 rounded-xl shadow-lg border border-zinc-200 dark:border-zinc-800 p-4 flex flex-col gap-3 overflow-y-auto">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold leading-snug">{station.name}</h2>
        <button onClick={onClose} className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
          <X size={16} />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <Stat label="Bikes" value={station.bikes ?? "—"} />
        <Stat label="Docks" value={station.docks ?? "—"} />
        <Stat label="Capacity" value={station.capacity} />
        <Stat label={supplyLabel} value={supply ?? "—"} highlight />
      </div>
      <Link
        href={`/station/${station.station_id}`}
        className="text-xs font-medium text-zinc-900 dark:text-zinc-100 underline underline-offset-4 hover:no-underline"
      >
        View 24h history →
      </Link>
    </aside>
  );
}

function Stat({ label, value, highlight = false }: { label: string; value: number | string; highlight?: boolean }) {
  return (
    <div
      className={`rounded-md border px-2 py-1.5 ${
        highlight
          ? "border-zinc-900 dark:border-zinc-100 bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
          : "border-zinc-200 dark:border-zinc-800"
      }`}
    >
      <div className="text-[10px] uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
