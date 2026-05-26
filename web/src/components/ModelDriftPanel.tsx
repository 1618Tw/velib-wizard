"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, type ModelRun } from "@/lib/api";

const HORIZONS = [15, 30, 45, 60, 90, 120] as const;
type Horizon = (typeof HORIZONS)[number];

type Tone = "green" | "amber" | "red" | "zinc";

function toneClasses(tone: Tone): { bg: string; ring: string; text: string } {
  return {
    green: { bg: "bg-green-50", ring: "ring-green-200", text: "text-green-700" },
    amber: { bg: "bg-amber-50", ring: "ring-amber-200", text: "text-amber-700" },
    red: { bg: "bg-red-50", ring: "ring-red-200", text: "text-red-700" },
    zinc: { bg: "bg-white", ring: "ring-[var(--color-brand-border)]", text: "text-[var(--color-brand-dark)]" },
  }[tone];
}

/** A run "wins" cleanly when MAE is meaningfully below baseline AND
 *  win_pct (per-row beats) is comfortably above 50%. */
function runTone(run: ModelRun | undefined): Tone {
  if (!run || run.mae_test === null || run.baseline_mae === null) return "zinc";
  const ratio = run.mae_test / run.baseline_mae;
  const win = run.win_pct ?? 0;
  if (ratio <= 0.95 && win >= 0.55) return "green";
  if (ratio >= 1.0 || win < 0.5) return "red";
  return "amber";
}

function fmtMAE(x: number | null): string {
  if (x === null) return "—";
  return (x * 100).toFixed(2) + "%";
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function horizonLabel(min: Horizon): string {
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m === 0 ? `${h}h` : `${h}h${m}`;
}

export default function ModelDriftPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["model-runs"],
    queryFn: () => api.modelRuns(30),
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
    retry: 1,
  });

  const [selected, setSelected] = useState<Horizon>(120);

  const byHorizon = useMemo(() => {
    const map = new Map<number, ModelRun[]>();
    HORIZONS.forEach((h) => map.set(h, []));
    data?.runs.forEach((r) => {
      const arr = map.get(r.horizon_minutes);
      if (arr) arr.push(r);
    });
    return map;
  }, [data]);

  const latestByHorizon = useMemo(() => {
    const map = new Map<number, ModelRun | undefined>();
    HORIZONS.forEach((h) => {
      const runs = byHorizon.get(h) ?? [];
      map.set(h, runs[runs.length - 1]);
    });
    return map;
  }, [byHorizon]);

  if (isLoading) {
    return (
      <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4">
        <h2 className="text-sm font-semibold text-[var(--color-brand-dark)]">Model drift</h2>
        <p className="text-xs text-[var(--color-brand-dark)]/60 mt-2">Loading training history…</p>
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4">
        <h2 className="text-sm font-semibold text-[var(--color-brand-dark)]">Model drift</h2>
        <p className="text-xs text-red-700 mt-2">Could not load training history.</p>
      </section>
    );
  }

  if (data.n_runs === 0) {
    return (
      <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4">
        <h2 className="text-sm font-semibold text-[var(--color-brand-dark)]">Model drift</h2>
        <p className="text-xs text-[var(--color-brand-dark)]/60 mt-2">
          No training runs yet. Trigger one nightly cycle and this panel will populate.
        </p>
      </section>
    );
  }

  const selectedRuns = byHorizon.get(selected) ?? [];
  const chartData = selectedRuns.map((r) => ({
    label: fmtDate(r.trained_at),
    model: r.mae_test === null ? null : r.mae_test * 100,
    baseline: r.baseline_mae === null ? null : r.baseline_mae * 100,
  }));

  return (
    <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-[var(--color-brand-dark)]">Model drift</h2>
        <span className="text-xs text-[var(--color-brand-dark)]/60">
          LightGBM v1 · MAE vs hour-of-week baseline
        </span>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {HORIZONS.map((h) => {
          const latest = latestByHorizon.get(h);
          const t = toneClasses(runTone(latest));
          const ratio =
            latest && latest.mae_test !== null && latest.baseline_mae !== null
              ? latest.mae_test / latest.baseline_mae
              : null;
          return (
            <div
              key={h}
              className={`rounded-lg ${t.bg} ring-1 ${t.ring} p-3 flex flex-col gap-0.5`}
            >
              <div className="text-[10px] uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">
                {horizonLabel(h)}
              </div>
              <div className={`text-lg font-semibold ${t.text}`}>
                {fmtMAE(latest?.mae_test ?? null)}
              </div>
              <div className="text-[10px] text-[var(--color-brand-dark)]/60 leading-tight">
                baseline {fmtMAE(latest?.baseline_mae ?? null)}
                {ratio !== null && (
                  <> · {ratio < 1 ? "−" : "+"}
                    {Math.abs((1 - ratio) * 100).toFixed(0)}%
                  </>
                )}
              </div>
              <div className="text-[10px] text-[var(--color-brand-dark)]/60">
                win {latest?.win_pct !== undefined && latest?.win_pct !== null
                  ? `${(latest.win_pct * 100).toFixed(0)}%`
                  : "—"}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex gap-1 flex-wrap">
        {HORIZONS.map((h) => (
          <button
            key={h}
            onClick={() => setSelected(h)}
            className={
              "text-xs px-2.5 py-1 rounded-md border transition-colors " +
              (h === selected
                ? "bg-[var(--color-brand)] text-white border-[var(--color-brand)]"
                : "bg-white text-[var(--color-brand-dark)] border-[var(--color-brand-border)] hover:bg-[var(--color-brand-tint)]")
            }
          >
            {horizonLabel(h)}
          </button>
        ))}
      </div>

      <div className="h-52">
        {chartData.length === 0 ? (
          <div className="h-full grid place-items-center text-sm text-[var(--color-brand-dark)]/60">
            No runs at this horizon yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#cfe6ee" />
              <XAxis dataKey="label" fontSize={10} stroke="#0e5e7a" minTickGap={20} />
              <YAxis
                fontSize={10}
                stroke="#0e5e7a"
                tickFormatter={(v) => `${v.toFixed(1)}%`}
                width={42}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  borderRadius: 8,
                  border: "1px solid #cfe6ee",
                  padding: "6px 10px",
                  color: "#0e5e7a",
                }}
                formatter={(v) =>
                  typeof v === "number" ? `${v.toFixed(2)}%` : String(v)
                }
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: "#0e5e7a" }}
                iconType="plainline"
              />
              <Line
                type="monotone"
                dataKey="model"
                name="Model"
                stroke="#5fbcd2"
                strokeWidth={2}
                dot={{ r: 2.5 }}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="baseline"
                name="Baseline"
                stroke="#94a3b8"
                strokeWidth={1.5}
                strokeDasharray="4 3"
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <p className="text-[11px] text-[var(--color-brand-dark)]/60 leading-snug">
        Test-set MAE per nightly retrain. Lower is better. Model line below the dashed baseline ⇒ LightGBM is beating
        the hour-of-week mean. Sustained crossing above the baseline is the drift signal to act on.
      </p>
    </section>
  );
}
