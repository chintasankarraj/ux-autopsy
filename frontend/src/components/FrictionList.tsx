import { useState } from "react";
import type { FrictionPoint } from "../types";

export default function FrictionList({ points, sevColor }: { points: FrictionPoint[]; sevColor: Record<string, string> }) {
  const [openWhy, setOpenWhy] = useState<number | null>(null);

  if (points.length === 0)
    return <p className="text-sm text-slate-500 border border-dashed border-slate-300 rounded-xl p-6">
      No friction detected in this session.</p>;

  return (
    <div className="space-y-3">
      {points.map((p) => {
        const evidenceItems = p.evidence.split(/;\s*/).filter(Boolean);
        return (
          <div key={p.id} className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${sevColor[p.severity] || sevColor.LOW}`}>
                {p.severity}
              </span>
              <strong className="text-sm">{p.title}</strong>
              <span className="text-xs text-slate-400 ml-auto">signal: {p.signal} · confidence {(p.confidence * 100).toFixed(0)}%</span>
            </div>

            <div className="mt-2">
              <div className="text-xs font-medium text-slate-500 mb-1">Evidence</div>
              <ul className="text-sm text-slate-600 list-disc list-inside space-y-0.5">
                {evidenceItems.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </div>

            {p.affected_action && (
              <p className="text-xs text-slate-400 mt-2">Affected: {p.affected_action}</p>
            )}
            <p className="text-sm text-teal-700 mt-2"><strong>Fix:</strong> {p.recommendation}</p>

            {p.why && (
              <div className="mt-3 border-t border-slate-100 pt-2">
                <button
                  onClick={() => setOpenWhy(openWhy === p.id ? null : p.id)}
                  className="text-xs font-medium text-slate-500 hover:text-slate-900 inline-flex items-center gap-1"
                >
                  {openWhy === p.id ? "▾" : "▸"} Why did this happen?
                </button>
                {openWhy === p.id && (
                  <div className="mt-2 bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm space-y-1.5">
                    {p.why.observed && (
                      <p><strong className="text-slate-500">Observed behavior:</strong> {p.why.observed}</p>
                    )}
                    {p.why.possible_cause && (
                      <p><strong className="text-slate-500">Possible cause:</strong> {p.why.possible_cause}</p>
                    )}
                    {p.why.likely_root_cause && (
                      <p><strong className="text-slate-500">Likely root cause:</strong> {p.why.likely_root_cause}</p>
                    )}
                    {p.why.recommendation && (
                      <p className="text-teal-700"><strong>Recommendation:</strong> {p.why.recommendation}</p>
                    )}
                    {p.why.confidence != null && (
                      <p className="text-xs text-slate-400">Confidence: {(p.why.confidence * 100).toFixed(0)}%</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
