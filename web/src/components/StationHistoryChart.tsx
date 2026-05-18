"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";

function fmtHour(iso: string): string {
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, "0")}:${d
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
}

export default function StationHistoryChart({ stationId }: { stationId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["history", stationId],
    queryFn: () => api.history(stationId, 24),
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return <div className="h-72 grid place-items-center text-sm text-zinc-500">Loading history…</div>;
  }
  if (error) {
    return <div className="h-72 grid place-items-center text-sm text-red-600">{String(error)}</div>;
  }
  const points = (data ?? []).map((p) => ({ ...p, label: fmtHour(p.ts) }));
  if (points.length === 0) {
    return (
      <div className="h-72 grid place-items-center text-sm text-zinc-500 text-center px-4">
        No history yet. The collector runs every 5 minutes — check back soon, the chart will fill in.
      </div>
    );
  }
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgb(228 228 231 / 0.6)" />
          <XAxis dataKey="label" stroke="rgb(113 113 122)" fontSize={11} minTickGap={32} />
          <YAxis stroke="rgb(113 113 122)" fontSize={11} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid rgb(228 228 231)",
              padding: "6px 10px",
            }}
            labelFormatter={(label) => `Time ${label}`}
          />
          <Line
            type="monotone"
            dataKey="bikes"
            stroke="#5fbcd2"
            strokeWidth={2.4}
            dot={false}
            isAnimationActive={false}
            name="Bikes"
          />
          <Line
            type="monotone"
            dataKey="docks"
            stroke="#0e5e7a"
            strokeWidth={2.4}
            dot={false}
            isAnimationActive={false}
            name="Docks"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
