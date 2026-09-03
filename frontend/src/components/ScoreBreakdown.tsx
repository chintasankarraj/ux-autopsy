import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

export default function ScoreBreakdownView({ bd }: { bd: { ux_score: number; completed: number; efficiency: number; navigation: number; recovery: number; friction: number } }) {
  const data = [
    { name: "Completion", value: bd.completed },
    { name: "Efficiency", value: bd.efficiency },
    { name: "Navigation", value: bd.navigation },
    { name: "Recovery", value: bd.recovery },
    { name: "Friction", value: bd.friction },
  ];
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="font-semibold">Score Breakdown</h2>
        <span className="text-sm text-slate-500">Overall: <strong>{bd.ux_score}/100</strong></span>
      </div>
      <div style={{ height: 220 }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis type="category" dataKey="name" width={90} tickLine={false} axisLine={false} />
            <Tooltip />
            <ReferenceLine x={70} stroke="#94a3b8" strokeDasharray="4 4" />
            <Bar dataKey="value" fill="#0f766e" radius={[0, 6, 6, 0]} barSize={18} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
