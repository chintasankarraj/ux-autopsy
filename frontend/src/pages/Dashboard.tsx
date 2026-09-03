import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, CheckCircle2, Flame, Gauge } from "lucide-react";
import { api } from "../services/api";
import type { Session } from "../types";
import StatCard from "../components/StatCard";

export function StatusDot({ status, completed }: { status: string; completed: number | null }) {
  const color =
    status === "running" ? "bg-blue-400 animate-pulse"
    : status === "failed" || status === "pending" ? "bg-slate-300"
    : completed ? "bg-emerald-500" : "bg-red-500";
  return <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${color}`} />;
}

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.stats().then(setStats).catch(() => setErr("Backend unreachable — start it with: python -m uvicorn backend.app.main:app --port 8000 (from the project root)"));
    api.sessions().then(setSessions).catch(() => {});
  }, []);
  const cards = stats ? [
    { icon: Activity, label: "Total Sessions", value: stats.total_sessions },
    { icon: CheckCircle2, label: "Successful", value: stats.successful_sessions },
    { icon: Gauge, label: "Avg UX Score", value: stats.avg_ux_score },
    { icon: Flame, label: "Friction Points", value: stats.total_friction },
  ] : [];
  return (
    <div>
      <section className="py-10 text-center">
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
          Find out <span className="text-teal-600">WHY</span> users struggle.
        </h1>
        <p className="text-slate-600 mt-3 max-w-xl mx-auto">
          Run synthetic user tests against your website, reconstruct friction,
          and validate UX improvements before your real users hit them.
        </p>
        <div className="mt-6 flex gap-3 justify-center flex-wrap">
          <Link to="/new" className="bg-slate-900 text-white px-5 py-2.5 rounded-lg font-medium hover:bg-slate-700">
            Run New UX Test
          </Link>
          <Link to="/new?demo=1" className="border border-slate-300 bg-white px-5 py-2.5 rounded-lg font-medium hover:bg-slate-100">
            View Demo
          </Link>
        </div>
      </section>
      {err && <p className="text-red-600 text-sm text-center mb-6">{err}</p>}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((c) => (
          <StatCard key={c.label} icon={c.icon} label={c.label} value={c.value ?? "—"} />
        ))}
      </div>
      <h2 className="mt-10 mb-3 font-semibold">Recent Sessions</h2>
      {sessions.length === 0 ? (
        <p className="text-slate-500 text-sm border border-dashed border-slate-300 rounded-xl p-8 text-center">
          No sessions yet. Run your first UX test to see results here.
        </p>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 overflow-hidden">
          {sessions.map((s) => (
            <Link key={s.id} to={`/sessions/${s.id}`} className="flex items-center gap-4 p-4 hover:bg-slate-50">
              <StatusDot status={s.status} completed={s.completed} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{s.task}</div>
                <div className="text-xs text-slate-500 truncate">{s.url}</div>
              </div>
              <div className="text-sm font-semibold shrink-0" title="UX Score">
                {s.ux_score ?? "—"}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
