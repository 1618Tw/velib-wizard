import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function NetworkPage() {
  const summary = await api.networkSummary();
  const ok = summary.total - summary.empty - summary.full;
  return (
    <div className="max-w-3xl w-full mx-auto px-4 py-8 flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Network summary</h1>
        <p className="text-xs text-zinc-500 mt-1">
          {summary.last_ts ? `Last snapshot ${new Date(summary.last_ts).toLocaleString()}` : "No snapshots yet"}
        </p>
      </header>
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Tile label="Total" value={summary.total} />
        <Tile label="OK" value={ok} tone="green" />
        <Tile label="Empty" value={summary.empty} tone="red" />
        <Tile label="Full" value={summary.full} tone="blue" />
      </section>
      <p className="text-xs text-zinc-500">
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
  tone?: "green" | "red" | "blue";
}) {
  const ring =
    tone === "green"
      ? "ring-green-200 dark:ring-green-900"
      : tone === "red"
      ? "ring-red-200 dark:ring-red-900"
      : tone === "blue"
      ? "ring-blue-200 dark:ring-blue-900"
      : "ring-zinc-200 dark:ring-zinc-800";
  return (
    <div className={`rounded-xl bg-white dark:bg-zinc-900 ring-1 ${ring} p-4 flex flex-col gap-1`}>
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-2xl font-semibold">{value.toLocaleString()}</div>
    </div>
  );
}
