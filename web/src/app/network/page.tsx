"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function NetworkPage() {
  const { data: summary, isLoading, error } = useQuery({
    queryKey: ["networkSummary"],
    queryFn: api.networkSummary,
  });

  if (isLoading) return <div className="p-8 text-sm text-[var(--color-brand-dark)]/60">Loading…</div>;
  if (error || !summary) return <div className="p-8 text-sm text-red-500">Failed to load network data.</div>;

  const ok = summary.total - summary.empty - summary.full;

  return (
    <div className="max-w-3xl w-full mx-auto px-4 py-8 flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-brand-dark)]">Network summary</h1>
        <p className="text-xs text-[var(--color-brand-dark)]/60 mt-1">
          {summary.last_ts ? `Last snapshot ${new Date(summary.last_ts).toLocaleString()}` : "No snapshots yet"}
        </p>
      </header>
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Tile label="Total" value={summary.total} />
        <Tile label="OK" value={ok} tone="green" />
        <Tile label="Empty" value={summary.empty} tone="red" />
        <Tile label="Full" value={summary.full} tone="brand" />
      </section>
      <p className="text-xs text-[var(--color-brand-dark)]/60">
        Hourly heatmap, neighborhood ranking, and the model-comparison panel arrive in M5.
      </p>
    </div>
  );
}

function Tile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "green" | "red" | "brand";
}) {
  const ring =
    tone === "green"
      ? "ring-green-200"
      : tone === "red"
      ? "ring-red-200"
      : tone === "brand"
      ? "ring-[var(--color-brand)]/50"
      : "ring-[var(--color-brand-border)]";
  return (
    <div className={`rounded-xl bg-white ring-1 ${ring} p-4 flex flex-col gap-1`}>
      <div className="text-xs uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">{label}</div>
      <div className="text-2xl font-semibold text-[var(--color-brand-dark)]">{value.toLocaleString()}</div>
    </div>
  );
}
