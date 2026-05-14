import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { api } from "@/lib/api";
import StationHistoryChart from "@/components/StationHistoryChart";

export const dynamic = "force-dynamic";

export default async function StationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const station = await api.station(id);

  return (
    <div className="max-w-3xl w-full mx-auto px-4 py-8 flex flex-col gap-6">
      <Link
        href="/"
        className="text-sm text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 flex items-center gap-1 w-fit"
      >
        <ArrowLeft size={14} /> Back to map
      </Link>

      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{station.name}</h1>
        <p className="text-xs text-zinc-500">
          ID {station.station_id} · capacity {station.capacity}
        </p>
      </header>

      <section className="grid grid-cols-3 gap-3">
        <Tile label="Bikes available" value={station.bikes ?? "—"} accent="green" />
        <Tile label="Docks available" value={station.docks ?? "—"} accent="blue" />
        <Tile label="Capacity" value={station.capacity} />
      </section>

      <section className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold">Last 24 hours</h2>
          <span className="text-xs text-zinc-500">bikes (green) · docks (blue)</span>
        </div>
        <StationHistoryChart stationId={station.station_id} />
      </section>

      <p className="text-xs text-zinc-500">
        Forecast curve and POI context land in M3 / M4.
      </p>
    </div>
  );
}

function Tile({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: "green" | "blue";
}) {
  const ring =
    accent === "green"
      ? "ring-green-200 dark:ring-green-900"
      : accent === "blue"
      ? "ring-blue-200 dark:ring-blue-900"
      : "ring-zinc-200 dark:ring-zinc-800";
  return (
    <div
      className={`rounded-xl bg-white dark:bg-zinc-900 ring-1 ${ring} p-4 flex flex-col gap-1`}
    >
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
