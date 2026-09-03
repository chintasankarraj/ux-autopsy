import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export default function StatCard({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon?: LucideIcon;
  label: string;
  value: ReactNode;
  tone?: "default" | "success" | "danger";
}) {
  const toneClass =
    tone === "success" ? "bg-emerald-50 border-emerald-200"
    : tone === "danger" ? "bg-red-50 border-red-200"
    : "bg-white border-slate-200";
  return (
    <div className={`rounded-xl p-4 border ${toneClass}`}>
      {Icon && <Icon className="w-4 h-4 text-slate-400 mb-2" aria-hidden="true" />}
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  );
}
