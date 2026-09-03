import type { FrictionPoint } from "../types";

export default function FrictionList({ points, sevColor }: { points: FrictionPoint[]; sevColor: Record<string, string> }) {
  if (points.length === 0)
    return <p className="text-sm text-slate-500 border border-dashed border-slate-300 rounded-xl p-6">
      No friction detected in this session.</p>;
  return (
    <div className="space-y-3">
      {points.map((p) => (
        <div key={p.id} className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${sevColor[p.severity] || sevColor.LOW}`}>
              {p.severity}
            </span>
            <strong className="text-sm">{p.title}</strong>
            <span className="text-xs text-slate-400 ml-auto">signal: {p.signal} · confidence {(p.confidence * 100).toFixed(0)}%</span>
          </div>
          <p className="text-sm text-slate-600 mt-2">{p.evidence}</p>
          {p.affected_action && (
            <p className="text-xs text-slate-400 mt-1">Affected: {p.affected_action}</p>
          )}
          <p className="text-sm text-teal-700 mt-2"><strong>Fix:</strong> {p.recommendation}</p>
        </div>
      ))}
    </div>
  );
}
