"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, CheckCircle2, ExternalLink, RefreshCw, XCircle } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, type StatusOverview } from "@/lib/api";
import ModelDriftPanel from "./ModelDriftPanel";

const SUPABASE_FREE_BYTES = 500 * 1024 * 1024; // 500 MB

function fmtNumber(n: number): string {
  return n.toLocaleString();
}

function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}m`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

function relativeAge(iso: string | null): string {
  if (!iso) return "—";
  const diffSec = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diffSec < 60) return `${Math.floor(diffSec)}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

function fmtBucket(iso: string): string {
  const d = new Date(iso);
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

type Tone = "green" | "amber" | "red" | "zinc";

function toneClasses(tone: Tone): { bg: string; ring: string; text: string } {
  return {
    green: { bg: "bg-green-50", ring: "ring-green-200", text: "text-green-700" },
    amber: { bg: "bg-amber-50", ring: "ring-amber-200", text: "text-amber-700" },
    red:   { bg: "bg-red-50", ring: "ring-red-200", text: "text-red-700" },
    zinc:  { bg: "bg-white", ring: "ring-[var(--color-brand-border)]", text: "text-[var(--color-brand-dark)]" },
  }[tone];
}

function ageTone(mins: number | null): Tone {
  if (mins === null) return "red";
  if (mins < 7) return "green";
  if (mins < 15) return "amber";
  return "red";
}

function rateTone(n: number, expected: number): Tone {
  if (n >= expected * 0.9) return "green";
  if (n >= expected * 0.6) return "amber";
  return "red";
}

function storageTone(bytes: number): Tone {
  const ratio = bytes / SUPABASE_FREE_BYTES;
  if (ratio < 0.8) return "green";
  if (ratio < 0.95) return "amber";
  return "red";
}

export default function StatusDashboard() {
  const { data, isLoading, isError, refetch, isFetching, error } = useQuery({
    queryKey: ["status"],
    queryFn: api.status,
    refetchInterval: 30_000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8 text-center text-[var(--color-brand-dark)]/60">
        Loading status…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <BigBadge tone="red" label="Backend unreachable" />
        <p className="text-sm text-[var(--color-brand-dark)]/70 mt-3 text-center">
          The status endpoint did not respond. Render service is likely sleeping or down.
        </p>
        <p className="mt-2 text-xs text-[var(--color-brand-dark)]/50 text-center break-all">
          {String(error ?? "unknown error")}
        </p>
        <div className="mt-6 flex justify-center">
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 text-sm px-3 py-2 rounded-md bg-[var(--color-brand)] text-white hover:bg-[var(--color-brand-hover)] transition-colors"
          >
            <RefreshCw size={14} /> Try again
          </button>
        </div>
      </div>
    );
  }

  return <StatusBody status={data} onRefresh={() => refetch()} refreshing={isFetching} />;
}

function StatusBody({
  status,
  onRefresh,
  refreshing,
}: {
  status: StatusOverview;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const d = status.data;
  const overallTone: Tone = status.ok ? "green" : "red";
  const overallLabel = status.ok
    ? "Healthy"
    : d.minutes_since_last_snapshot === null
    ? "No data yet"
    : d.minutes_since_last_snapshot >= 15
    ? "Stale data — cron stalled?"
    : !status.gbfs_reachable
    ? "GBFS feed unreachable"
    : "Degraded";

  const sparkData = status.sparkline.map((s) => ({ label: fmtBucket(s.bucket), n: s.n }));

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-5">
      <BigBadge
        tone={overallTone}
        label={overallLabel}
        sub={`Last snapshot ${relativeAge(d.last_snapshot_ts)} · checked ${relativeAge(status.checked_at)}`}
        onRefresh={onRefresh}
        refreshing={refreshing}
      />

      <section className="grid grid-cols-2 gap-3">
        <Tile
          label="Last snapshot"
          value={d.minutes_since_last_snapshot !== null ? `${d.minutes_since_last_snapshot} min ago` : "—"}
          tone={ageTone(d.minutes_since_last_snapshot)}
          sub={d.last_snapshot_ts ? new Date(d.last_snapshot_ts).toLocaleString() : undefined}
        />
        <Tile
          label="GBFS feed"
          value={status.gbfs_reachable ? "Reachable" : "Unreachable"}
          tone={status.gbfs_reachable ? "green" : "red"}
        />
        <Tile
          label="Snapshots · last hour"
          value={fmtNumber(d.snapshots_last_hour)}
          tone={rateTone(d.snapshots_last_hour, d.stations * 12)}
          sub={`expected ≈ ${fmtNumber(d.stations * 12)} (${d.stations} stations × 12 ticks)`}
        />
        <Tile
          label="Snapshots · last 24h"
          value={fmtNumber(d.snapshots_last_24h)}
          tone={rateTone(d.snapshots_last_24h, d.stations * 288)}
          sub={`expected ≈ ${fmtNumber(d.stations * 288)}`}
        />
        <Tile
          label="Database size"
          value={fmtBytes(d.database_bytes)}
          tone={storageTone(d.database_bytes)}
          sub={`of 500 MB free tier · ${((d.database_bytes / SUPABASE_FREE_BYTES) * 100).toFixed(1)}%`}
        />
        <Tile
          label="Backend uptime"
          value={fmtDuration(status.uptime_seconds)}
          tone="zinc"
          sub={`since ${new Date(status.process_started_at).toLocaleString()}`}
        />
      </section>

      <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4">
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="text-sm font-semibold text-[var(--color-brand-dark)]">Snapshot cadence · last 6 hours</h2>
          <span className="text-xs text-[var(--color-brand-dark)]/60">per 15-minute bucket</span>
        </div>
        <div className="h-44">
          {sparkData.length === 0 ? (
            <div className="h-full grid place-items-center text-sm text-[var(--color-brand-dark)]/60">
              Not enough history yet.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sparkData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cfe6ee" />
                <XAxis dataKey="label" fontSize={10} stroke="#0e5e7a" minTickGap={20} />
                <YAxis fontSize={10} stroke="#0e5e7a" allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    fontSize: 11,
                    borderRadius: 8,
                    border: "1px solid #cfe6ee",
                    padding: "6px 10px",
                    color: "#0e5e7a",
                  }}
                />
                <Bar dataKey="n" fill="#5fbcd2" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <p className="text-[11px] text-[var(--color-brand-dark)]/60 mt-1">
          Each bar should be ≈ {fmtNumber(d.stations * 3)} (one snapshot per station, three ticks per 15-min bucket).
        </p>
      </section>

      <ModelDriftPanel />

      <section className="rounded-xl border border-[var(--color-brand-border)] bg-white p-4 flex flex-col gap-3">
        <h2 className="text-sm font-semibold flex items-center gap-2 text-[var(--color-brand-dark)]">
          <Activity size={14} /> External dashboards
        </h2>
        <ExtLink href="https://dashboard.render.com" label="Render" hint="logs, deploys, service status" />
        <ExtLink href="https://console.cron-job.org" label="cron-job.org" hint="cron execution history" />
        <ExtLink href="https://supabase.com/dashboard" label="Supabase" hint="DB browser, SQL editor, size" />
      </section>
    </div>
  );
}

function BigBadge({
  tone,
  label,
  sub,
  onRefresh,
  refreshing,
}: {
  tone: Tone;
  label: string;
  sub?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const t = toneClasses(tone);
  const Icon = tone === "green" ? CheckCircle2 : tone === "amber" ? AlertCircle : XCircle;
  return (
    <div
      className={`rounded-2xl ${t.bg} ring-1 ${t.ring} px-5 py-4 flex items-center gap-4`}
    >
      <Icon className={t.text} size={32} />
      <div className="flex-1 min-w-0">
        <div className={`text-xl sm:text-2xl font-semibold ${t.text}`}>{label}</div>
        {sub && <div className="text-xs text-[var(--color-brand-dark)]/70 mt-0.5">{sub}</div>}
      </div>
      {onRefresh && (
        <button
          onClick={onRefresh}
          className="text-[var(--color-brand-dark)]/60 hover:text-[var(--color-brand-dark)] p-2 transition-colors"
          aria-label="Refresh"
        >
          <RefreshCw size={18} className={refreshing ? "animate-spin" : ""} />
        </button>
      )}
    </div>
  );
}

function Tile({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone: Tone;
  sub?: string;
}) {
  const t = toneClasses(tone);
  return (
    <div className={`rounded-xl ${t.bg} ring-1 ${t.ring} p-3 sm:p-4 flex flex-col gap-1`}>
      <div className="text-[10px] sm:text-xs uppercase tracking-wide text-[var(--color-brand-dark)]/60 font-semibold">{label}</div>
      <div className={`text-lg sm:text-xl font-semibold ${t.text}`}>{value}</div>
      {sub && <div className="text-[10px] sm:text-xs text-[var(--color-brand-dark)]/60 leading-snug">{sub}</div>}
    </div>
  );
}

function ExtLink({ href, label, hint }: { href: string; label: string; hint: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="flex items-center justify-between text-sm border border-[var(--color-brand-border)] rounded-md px-3 py-2 hover:bg-[var(--color-brand-tint)] transition-colors"
    >
      <div className="flex flex-col">
        <span className="font-semibold text-[var(--color-brand-dark)]">{label}</span>
        <span className="text-xs text-[var(--color-brand-dark)]/60">{hint}</span>
      </div>
      <ExternalLink size={14} className="text-[var(--color-brand)]" />
    </a>
  );
}
