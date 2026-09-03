import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Session } from "../types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function Compare() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sel, setSel] = useState<string[]>([]);
  useEffect(() => { api.sessions().then(setSessions).catch(() => {}); }, []);
  const done = sessions.filter((s) => s.status === "completed" && s.ux_score != null);

  const toggle = (id: string) =>
    setSel((prev) => prev.includes(id) ? prev.filter((x) => x !== id)
      : prev.length < 3 ? [...prev, id] : prev);

  const chosen = done.filter((s) => sel.includes(s.id));
  const data = chosen.map((s) => ({
    name: s.task.slice(0, 20) + "…",
    score: s.ux_score,
    actions: s.actions_count,
    friction: s.friction_count,
  }));

  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Compare Sessions</h1>
      <p className="text-sm text-slate-500 mb-6">
        Pick up to 3 completed sessions to compare UX scores side by side —
        e.g. the same task before and after a fix (A/B validation).
      </p>
      {done.length === 0 ? (
        <p className="text-sm text-slate-500 border border-dashed border-slate-300 rounded-xl p-8 text-center">
          No completed sessions yet.</p>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 gap-2 mb-6">
            {done.map((s) => (
              <label key={s.id}
                className={`border rounded-lg p-3 cursor-pointer text-sm flex items-center gap-3
                  ${sel.includes(s.id) ? "border-slate-900 ring-1 ring-slate-900 bg-slate-50" : "border-slate-200"}`}>
                <input type="checkbox" className="sr-only" checked={sel.includes(s.id)}
                  onChange={() => toggle(s.id)} />
                <span className="font-semibold">{s.ux_score}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium truncate">{s.task}</span>
                  <span className="block text-xs text-slate-500 truncate">{s.persona} · {s.id}</span>
                </span>
              </label>
            ))}
          </div>
          {data.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-4" style={{ height: 300 }}>
              <ResponsiveContainer>
                <BarChart data={data}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="score" fill="#0f766e" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
