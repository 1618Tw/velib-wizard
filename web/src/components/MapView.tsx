"use client";

import { useQuery } from "@tanstack/react-query";
import maplibregl, { Map as MLMap, MapMouseEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";

import { api, type Station } from "@/lib/api";

const PARIS_CENTER: [number, number] = [2.3522, 48.8566];

const RASTER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    base: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OSM</a> · © <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [{ id: "base", type: "raster", source: "base" }],
};

/** Fill ratio: 0 = empty (no bikes), 1 = full (no docks). null if unknown. */
function fillRatio(bikes: number | null, docks: number | null): number | null {
  if (bikes === null || docks === null) return null;
  const total = bikes + docks;
  if (total === 0) return null;
  return bikes / total;
}

/** Bipolar palette: green when balanced (~50%), red at extremes (full or empty). */
function colorForFill(fill: number | null): string {
  if (fill === null) return "#94a3b8";
  const dist = Math.abs(fill - 0.5);
  if (dist < 0.2) return "#16a34a"; // 30%–70%
  if (dist < 0.4) return "#f59e0b"; // 10%–30% or 70%–90%
  return "#dc2626"; // extremes
}

function formatPct(fill: number | null): string {
  if (fill === null) return "—";
  return `${Math.round(fill * 100)}%`;
}

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [selected, setSelected] = useState<Station | null>(null);

  const { data: stations = [] } = useQuery({
    queryKey: ["stations"],
    queryFn: api.stations,
    refetchInterval: 60_000,
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const el = containerRef.current;
    if (el.offsetWidth === 0 || el.offsetHeight === 0) return;
    mapRef.current = new maplibregl.Map({
      container: el,
      style: RASTER_STYLE,
      center: PARIS_CENTER,
      zoom: 11.5,
      attributionControl: { compact: true },
    });
    mapRef.current.on("load", () => mapRef.current?.resize());
    mapRef.current.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");

    const ro = new ResizeObserver(() => mapRef.current?.resize());
    ro.observe(el);
    const onWinResize = () => mapRef.current?.resize();
    window.addEventListener("resize", onWinResize);

    return () => {
      ro.disconnect();
      window.removeEventListener("resize", onWinResize);
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
          color: colorForFill(fillRatio(s.bikes, s.docks)),
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
  }, [stations]);

  return (
    <div
      className="relative w-full"
      style={{ height: "calc(100svh - 3rem)", minHeight: "70vh" }}
    >
      <div ref={containerRef} className="w-full h-full" />

      <Legend />

      <div className="absolute top-3 right-14 z-10 bg-white/90 dark:bg-zinc-900/90 backdrop-blur rounded-lg shadow-sm border border-zinc-200 dark:border-zinc-800 px-3 py-1.5 text-xs">
        {stations.length.toLocaleString()} stations
      </div>

      {selected && <StationPanel station={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Legend() {
  return (
    <div className="absolute top-3 left-3 z-10 bg-white/90 dark:bg-zinc-900/90 backdrop-blur rounded-lg shadow-sm border border-zinc-200 dark:border-zinc-800 px-3 py-2 text-xs flex flex-col gap-1.5">
      <div className="font-medium">Station fullness</div>
      <div className="flex items-center gap-2">
        <Dot color="#dc2626" />
        <span className="text-zinc-600 dark:text-zinc-400">Empty or full</span>
      </div>
      <div className="flex items-center gap-2">
        <Dot color="#f59e0b" />
        <span className="text-zinc-600 dark:text-zinc-400">Near a limit</span>
      </div>
      <div className="flex items-center gap-2">
        <Dot color="#16a34a" />
        <span className="text-zinc-600 dark:text-zinc-400">Balanced</span>
      </div>
    </div>
  );
}

function Dot({ color }: { color: string }) {
  return <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />;
}

function StationPanel({ station, onClose }: { station: Station; onClose: () => void }) {
  const fill = fillRatio(station.bikes, station.docks);
  return (
    <aside className="absolute right-3 top-3 bottom-3 w-80 max-w-[calc(100%-1.5rem)] z-10 bg-white dark:bg-zinc-900 rounded-xl shadow-lg border border-zinc-200 dark:border-zinc-800 p-4 flex flex-col gap-4 overflow-y-auto">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold leading-snug">{station.name}</h2>
        <button onClick={onClose} className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
          <X size={16} />
        </button>
      </div>

      <FullnessBar fill={fill} />

      <div className="grid grid-cols-3 gap-2 text-sm">
        <Stat label="Bikes" value={station.bikes ?? "—"} />
        <Stat label="Docks" value={station.docks ?? "—"} />
        <Stat label="Capacity" value={station.capacity} />
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

function FullnessBar({ fill }: { fill: number | null }) {
  const pct = fill === null ? 0 : Math.round(fill * 100);
  const color = colorForFill(fill);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] uppercase tracking-wide text-zinc-500">Fullness</span>
        <span className="text-lg font-semibold" style={{ color }}>
          {formatPct(fill)}
        </span>
      </div>
      <div className="h-2 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
        <div
          className="h-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-zinc-500">
        <span>No bikes</span>
        <span>No docks</span>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-zinc-200 dark:border-zinc-800 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
