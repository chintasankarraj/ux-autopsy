import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { api } from "../services/api";
import type { Session, EventItem, FrictionPoint, Analysis } from "../types";
import Timeline from "../components/Timeline";
import FrictionList from "../components/FrictionList";
import ScoreBreakdownView from "../components/ScoreBreakdown";
import RunningTest from "../components/RunningTest";
import StatCard from "../components/StatCard";

const sevColor: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-700", HIGH: "bg-orange-100 text-orange-700",
  MEDIUM: "bg-amber-100 text-amber-700", LOW: "bg-slate-100 text-slate-600",
};

export default function SessionResults() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<Session | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [fps, setFps] = useState<FrictionPoint[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [err, setErr] = useState("");

  const load = () => {
    if (!id) return;
    api.session(id).then((d) => setS(d)).catch((e) => setErr(e.message));
    api.events(id).then(setEvents).catch(() => {});
    api.analysis(id).then((d) => { setFps(d.friction_points); setAnalysis(d.analysis); }).catch(() => {});
  };
  useEffect(load, [id]);

  const retest = async () => {
    if (!id) return;
    try { const r = await api.retest(id); window.location.href = `/sessions/${r.id}`; }
    catch (e: any) { setErr(e.message); }
  };

  if (err) return <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-4">{err}</p>;
  if (!s) return <p className="text-slate-500 text-sm">Loading session…</p>;

  if (id && (s.status === "pending" || s.status === "running")) {
    return (
      <RunningTest
        sessionId={id}
        onDone={() => load()}
        onFailed={(msg) => { setErr(msg); load(); }}
      />
    );
  }

  const bd = s.score_breakdown;
  const stats: [string, ReactNode][] = [
    ["Task Completion", s.completed ? "Yes" : "No"],
    ["Time Taken", s.duration_ms ? `${(s.duration_ms / 1000).toFixed(1)}s` : "—"],
    ["Total Actions", s.actions_count ?? "—"],
    ["Friction Points", s.friction_count ?? "—"],
    ["Pages Visited", s.pages_visited ?? "—"],
  ];

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <a href="/" className="text-sm text-slate-500 hover:text-slate-900 inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" /> All sessions
          </a>
          <h1 className="text-xl font-semibold mt-1">Session {s.id}</h1>
          <p className="text-sm text-slate-500">{s.task}</p>
          <p className="text-xs text-slate-400 mt-0.5">{s.url}</p>
        </div>
        <button onClick={retest}
          className="inline-flex items-center gap-2 border border-slate-300 bg-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-100 shrink-0">
          <RefreshCw className="w-4 h-4" /> Retest
        </button>
      </div>

      {s.status === "failed" && (
        <p className="mb-6 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-4 inline-flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> Test failed: {s.error}
        </p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className={`rounded-xl p-4 col-span-2 md:col-span-1 border ${s.completed ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
          <div className="flex items-center gap-2 mb-1">
            {s.completed ? <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              : <XCircle className="w-4 h-4 text-red-600" />}
            <span className="text-xs font-medium text-slate-600">UX Score</span>
          </div>
          <div className="text-3xl font-bold">{s.ux_score ?? "—"}</div>
        </div>
        {stats.slice(1).map(([label, v]) => (
          <StatCard key={label} label={label} value={v} />
        ))}
      </div>

      {bd && <ScoreBreakdownView bd={bd} />}

      <section className="mt-8">
        <h2 className="font-semibold mb-1">UX Autopsy</h2>
        {analysis ? (
          <>
            <h3 className="text-sm font-medium text-slate-500 mt-4 mb-1">Executive Summary</h3>
            <p className="text-sm leading-relaxed bg-white border border-slate-200 rounded-xl p-4">
              {analysis.executive_summary}
            </p>
            <h3 className="text-sm font-medium text-slate-500 mt-6 mb-2">Root-Cause Analysis</h3>
            <div className="space-y-3">
              {analysis.root_causes.map((rc, i) => (
                <div key={i} className="bg-white border border-slate-200 rounded-xl p-4 text-sm space-y-2">
                  <p><strong className="text-slate-500">Observed:</strong> {rc.observed}</p>
                  <p><strong className="text-slate-500">Possible cause:</strong> {rc.possible_cause}</p>
                  <p><strong className="text-slate-500">Likely root cause:</strong> {rc.likely_root_cause}</p>
                  <p className="text-teal-700"><strong>Recommendation:</strong> {rc.recommendation}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-400 mt-3">
              Analysis generated by {analysis.provider === "mock" ? "deterministic heuristics (demo mode)" : analysis.provider}.
              Scores are computed deterministically and are never altered by the LLM.
            </p>
          </>
        ) : (
          <p className="text-sm text-slate-500 border border-dashed border-slate-300 rounded-xl p-6">
            Analysis not available yet.
          </p>
        )}
      </section>

      <section className="mt-8">
        <h2 className="font-semibold mb-3">Friction Points ({fps.length})</h2>
        <FrictionList points={fps} sevColor={sevColor} />
      </section>

      <section className="mt-8">
        <h2 className="font-semibold mb-3">Action Timeline</h2>
        <Timeline events={events} sevColor={sevColor} />
      </section>
    </div>
  );
}
