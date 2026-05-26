"use client";

import { useQuery } from "@tanstack/react-query";
import maplibregl, { Map as MLMap, MapMouseEvent } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";

import { api, type Station } from "@/lib/api";

const HORIZON_OPTIONS = [0, 15, 30, 45, 60, 90, 120] as const;
const DEFAULT_HORIZON = 120;

function horizonLabel(min: number): string {
  if (min === 0) return "Now";
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m === 0 ? `${h}h` : `${h}h${m}`;
}

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

/** Bipolar palette: green when balanced (~50%), red at extremes (full or empty).
 *  Used in the side panel — gives a "comfort score" for the current state. */
function colorForFill(fill: number | null): string {
  if (fill === null) return "#94a3b8";
  const dist = Math.abs(fill - 0.5);
  if (dist < 0.2) return "#16a34a"; // 30%–70%
  if (dist < 0.4) return "#f59e0b"; // 10%–30% or 70%–90%
  return "#dc2626"; // extremes
}

/** Sequential green → yellow → red ramp, smooth via HSL.
 *  Used to color station markers by the model's predicted fullness. */
function colorForPct(pct: number | null): string {
  if (pct === null || Number.isNaN(pct)) return "#cbd5e1";
  const clamped = Math.max(0, Math.min(1, pct));
  const hue = 120 * (1 - clamped); // 120 green, 60 yellow, 0 red
  return `hsl(${hue.toFixed(0)}, 70%, 45%)`;
}

function formatPct(fill: number | null): string {
  if (fill === null) return "—";
  return `${Math.round(fill * 100)}%`;
}

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [selected, setSelected] = useState<Station | null>(null);
  const [horizon, setHorizon] = useState<number>(DEFAULT_HORIZON);

  const { data: stations = [] } = useQuery({
    queryKey: ["stations"],
    queryFn: api.stations,
    refetchInterval: 60_000,
  });

  const { data: forecast } = useQuery({
    queryKey: ["forecasts", horizon],
    queryFn: () => api.forecastsRisk(horizon),
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
    enabled: horizon !== 0,
  });

  const pctByStation = useMemo(() => {
    const map = new Map<string, number | null>();
    if (horizon === 0) {
      stations.forEach((s) =>
        map.set(s.station_id, fillRatio(s.bikes, s.docks)),
      );
    } else {
      forecast?.stations.forEach((s) =>
        map.set(s.station_id, s.predicted_pct),
      );
    }
    return map;
  }, [horizon, stations, forecast]);

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
      features: stations.map((s) => {
        const pct = pctByStation.get(s.station_id) ?? null;
        return {
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
          properties: {
            station_id: s.station_id,
            color: colorForPct(pct),
          },
        };
      }),
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
  }, [stations, pctByStation]);

  return (
    <div
      className="relative w-full"
      style={{ height: "calc(100svh - 3rem)", minHeight: "70vh" }}
    >
      <div ref={containerRef} className="w-full h-full" />

      <Legend isLive={horizon === 0} />

      <div className="absolute top-3 right-14 z-10 bg-white/90 backdrop-blur rounded-lg shadow-sm border border-[var(--color-brand-border)] px-3 py-1.5 text-xs text-[var(--color-brand-dark)] font-medium">
        {stations.length.toLocaleString()} stations
      </div>

      <HorizonSlider
        value={horizon}
        onChange={setHorizon}
        hasData={horizon === 0 ? stations.length > 0 : !!forecast}
        computedAt={forecast?.stations[0]?.computed_at ?? null}
      />

      {selected && <StationPanel station={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function HorizonSlider({
  value,
  onChange,
  hasData,
  computedAt,
}: {
  value: number;
  onChange: (v: number) => void;
  hasData: boolean;
  computedAt: string | null;
}) {
  // Slider operates on indices into HORIZON_OPTIONS so it only snaps to
  // trained horizons — never to e.g. 75 or 105, which have no booster.
  const valueIdx = Math.max(0, HORIZON_OPTIONS.indexOf(value as (typeof HORIZON_OPTIONS)[number]));
  const ageMin = computedAt
    ? Math.round((Date.now() - new Date(computedAt).getTime()) / 60000)
    : null;

  return (
    <div className="absolute bottom-4 right-4 z-10 bg-white/95 backdrop-blur rounded-xl shadow-lg border border-[var(--color-brand-border)] px-4 pt-3 pb-2 w-72 text-[var(--color-brand-dark)]">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[10px] uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">
          Forecast horizon
        </span>
        <span className="text-sm font-semibold tabular-nums">
          {horizonLabel(value)}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={HORIZON_OPTIONS.length - 1}
        step={1}
        value={valueIdx}
        onChange={(e) => onChange(HORIZON_OPTIONS[Number(e.target.value)])}
        className="w-full accent-[var(--color-brand)] cursor-pointer"
        aria-label="Forecast horizon"
      />
      <div className="flex justify-between text-[10px] text-[var(--color-brand-dark)]/60 tabular-nums mt-0.5 px-0.5">
        {HORIZON_OPTIONS.map((h) => (
          <span
            key={h}
            className={
              h === value
                ? "font-semibold text-[var(--color-brand-dark)]"
                : ""
            }
          >
            {horizonLabel(h)}
          </span>
        ))}
      </div>
      <div className="text-[10px] text-[var(--color-brand-dark)]/50 mt-2 leading-tight">
        {value === 0
          ? hasData
            ? "Live fullness · refreshed every minute"
            : "Loading live data…"
          : hasData
            ? `Predicted fullness · refreshed ${ageMin}m ago`
            : "Loading forecasts…"}
      </div>
    </div>
  );
}

function Legend({ isLive }: { isLive: boolean }) {
  return (
    <div className="absolute top-3 left-3 z-10 bg-white/90 backdrop-blur rounded-lg shadow-sm border border-[var(--color-brand-border)] px-3 py-2 text-xs flex flex-col gap-1.5 text-[var(--color-brand-dark)]">
      <div className="font-semibold">{isLive ? "Live fullness" : "Predicted fullness"}</div>
      <div
        className="h-2 w-44 rounded-full"
        style={{
          background:
            "linear-gradient(to right, hsl(120,70%,45%) 0%, hsl(60,70%,45%) 50%, hsl(0,70%,45%) 100%)",
        }}
        aria-hidden
      />
      <div className="flex justify-between text-[10px] text-[var(--color-brand-dark)]/60 tabular-nums w-44">
        <span>empty</span>
        <span>half</span>
        <span>full</span>
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
    <aside className="absolute right-3 top-3 bottom-3 w-80 max-w-[calc(100%-1.5rem)] z-10 bg-white rounded-xl shadow-lg border border-[var(--color-brand-border)] p-4 flex flex-col gap-4 overflow-y-auto text-[var(--color-brand-dark)]">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold leading-snug">{station.name}</h2>
        <button onClick={onClose} className="text-[var(--color-brand-dark)]/60 hover:text-[var(--color-brand-dark)]">
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
        className="text-xs font-semibold text-[var(--color-brand)] hover:text-[var(--color-brand-dark)] underline underline-offset-4 hover:no-underline transition-colors"
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
        <span className="text-[10px] uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">Fullness</span>
        <span className="text-lg font-semibold" style={{ color }}>
          {formatPct(fill)}
        </span>
      </div>
      <div className="h-2 rounded-full bg-[var(--color-brand-tint)] overflow-hidden">
        <div
          className="h-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-[var(--color-brand-dark)]/50">
        <span>No bikes</span>
        <span>No docks</span>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-[var(--color-brand-border)] bg-[var(--color-brand-tint)] px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">{label}</div>
      <div className="text-lg font-semibold text-[var(--color-brand-dark)]">{value}</div>
    </div>
  );
}
