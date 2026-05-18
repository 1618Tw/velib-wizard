"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { api } from "@/lib/api";
import StationHistoryChart from "@/components/StationHistoryChart";

export default function StationClient() {
  const { id } = useParams<{ id: string }>();
  const { data: station, isLoading, error } = useQuery({
    queryKey: ["station", id],
    queryFn: () => api.station(id),
    enabled: !!id,
  });

  if (isLoading) return <div className="p-8 text-sm text-[var(--color-brand-dark)]/60">Loading…</div>;
  if (error || !station) return <div className="p-8 text-sm text-red-500">Failed to load station.</div>;

  return (
    <div className="max-w-3xl w-full mx-auto px-4 py-8 flex flex-col gap-6">
      <Link
        href="/"
        className="text-sm text-[var(--color-brand-dark)]/70 hover:text-[var(--color-brand-dark)] flex items-center gap-1 w-fit transition-colors"
      >
        <ArrowLeft size={14} /> Back to map
      </Link>

      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-brand-dark)]">{station.name}</h1>
        <p className="text-xs text-[var(--color-brand-dark)]/60">
          ID {station.station_id} · capacity {station.capacity}
        </p>
      </header>

      <Fullness bikes={station.bikes} docks={station.docks} />

      <section className="grid grid-cols-3 gap-3">
        <Tile label="Bikes available" value={station.bikes ?? "—"} accent="brand" />
        <Tile label="Docks available" value={station.docks ?? "—"} accent="brand-dark" />
        <Tile label="Capacity" value={station.capacity} />
      </section>

      <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-[var(--color-brand-dark)]">Last 24 hours</h2>
          <span className="text-xs text-[var(--color-brand-dark)]/60">
            <span className="inline-block w-2 h-2 rounded-full align-middle mr-1" style={{ backgroundColor: "#5fbcd2" }} />bikes
            <span className="inline-block w-2 h-2 rounded-full align-middle ml-3 mr-1" style={{ backgroundColor: "#0e5e7a" }} />docks
          </span>
        </div>
        <StationHistoryChart stationId={station.station_id} />
      </section>

      <p className="text-xs text-[var(--color-brand-dark)]/60">
        Forecast curve and POI context land in M3 / M4.
      </p>
    </div>
  );
}

function Fullness({ bikes, docks }: { bikes: number | null; docks: number | null }) {
  if (bikes === null || docks === null) return null;
  const total = bikes + docks;
  if (total === 0) {
    return <div className="text-xs text-[var(--color-brand-dark)]/60">No live data yet for this station.</div>;
  }
  const fill = bikes / total;
  const pct = Math.round(fill * 100);
  const dist = Math.abs(fill - 0.5);
  const color = dist < 0.2 ? "#16a34a" : dist < 0.4 ? "#f59e0b" : "#dc2626";
  return (
    <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4 flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="text-xs uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">Currently</span>
        <span className="text-2xl font-semibold" style={{ color }}>{pct}% full</span>
      </div>
      <div className="h-2 rounded-full bg-[var(--color-brand-tint)] overflow-hidden">
        <div className="h-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <div className="flex justify-between text-[10px] text-[var(--color-brand-dark)]/50">
        <span>No bikes</span>
        <span>No docks</span>
      </div>
    </section>
  );
}

function Tile({ label, value, accent }: { label: string; value: number | string; accent?: "brand" | "brand-dark" }) {
  const ring =
    accent === "brand"
      ? "ring-[var(--color-brand)]/50"
      : accent === "brand-dark"
      ? "ring-[var(--color-brand-dark)]/40"
      : "ring-[var(--color-brand-border)]";
  return (
    <div className={`rounded-xl bg-white ring-1 ${ring} p-4 flex flex-col gap-1`}>
      <div className="text-xs uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">{label}</div>
      <div className="text-2xl font-semibold text-[var(--color-brand-dark)]">{value}</div>
    </div>
  );
}
