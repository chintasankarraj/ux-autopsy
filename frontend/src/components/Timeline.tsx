import { useState } from "react";
import type { EventItem } from "../types";

const ICONS: Record<string, string> = {
  PAGE_VIEW: "📄", CLICK: "👆", TYPE: "⌨️", SCROLL: "↕️",
  NAVIGATION: "🧭", WAIT: "⏳", ERROR: "⚠️",
  TASK_SUCCESS: "✅", TASK_FAILURE: "❌", ABANDONMENT: "🚪",
};

export default function Timeline({ events, sevColor }: { events: EventItem[]; sevColor: Record<string, string> }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-2">
      {events.map((e) => (
        <div key={e.id}>
          <button
            onClick={() => setOpen(open === e.id ? null : e.id)}
            className={`w-full text-left flex items-center gap-3 p-3 rounded-lg border text-sm
              ${e.event_type === "ERROR" ? "border-red-200 bg-red-50"
                : e.success === 0 ? "border-orange-200 bg-orange-50"
                : "bg-white border-slate-200"} hover:border-slate-400 transition`}>
            <span aria-hidden="true">{ICONS[e.event_type] || "•"}</span>
            <span className="font-medium w-24 shrink-0">{e.event_type.replace("_", " ")}</span>
            <span className="text-slate-600 truncate flex-1">
              {e.element_text || e.element_id || e.url}
            </span>
            <span className="text-xs text-slate-400 shrink-0">{(e.ts_ms / 1000).toFixed(1)}s</span>
            <span className="text-xs text-slate-400 shrink-0">{e.success === 0 ? "failed" : ""}</span>
          </button>
          {open === e.id && (
            <div className="ml-8 mt-1 mb-2 bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm space-y-1">
              {e.reason && <p><strong className="text-slate-500">Reason:</strong> “{e.reason}”</p>}
              {e.element_id && <p><strong className="text-slate-500">Element:</strong> {e.element_id}</p>}
              {e.error && <p className="text-red-600"><strong>Error:</strong> {e.error}</p>}
              {e.screenshot_path && (
                <img src={`/api/screenshots/${e.screenshot_path.split("/").pop()}`}
                  alt={`screenshot for step ${e.id}`}
                  className="mt-2 rounded border border-slate-200 max-w-sm" />
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
