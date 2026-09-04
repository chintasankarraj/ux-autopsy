import { useState } from "react";
import type { EventItem, FrictionPoint } from "../types";

const ICONS: Record<string, string> = {
  PAGE_VIEW: "📄", CLICK: "👆", TYPE: "⌨️", SCROLL: "↕️",
  NAVIGATION: "🧭", WAIT: "⏳", ERROR: "⚠️", BACKTRACK: "↩️",
  TASK_SUCCESS: "✅", TASK_FAILURE: "❌", ABANDONMENT: "🚪",
};

const KIND_FALLBACKS: Record<string, string> = {
  button: "the action button",
  input: "the input field",
  link: "a navigation link",
};

// Internal element ids (e.g. "button_06") are ephemeral, DOM-order-based
// bookkeeping — never shown to the user. A missing label falls back to a
// generic, still-readable phrase derived from the id's kind prefix instead.
function elementLabel(text: string | null, id: string | null): string | null {
  if (text) return text;
  if (!id) return null;
  const kind = id.split("_")[0].toLowerCase();
  return KIND_FALLBACKS[kind] || "the relevant control";
}

export default function Timeline({
  events,
  sevColor,
  frictionPoints = [],
}: {
  events: EventItem[];
  sevColor: Record<string, string>;
  frictionPoints?: FrictionPoint[];
}) {
  const [open, setOpen] = useState<number | null>(null);
  const [brokenShots, setBrokenShots] = useState<Set<number>>(new Set());

  const frictionFor = (e: EventItem) =>
    frictionPoints.find((p) => p.affected_action && p.affected_action === (e.element_text || e.element_id));

  return (
    <div className="space-y-2">
      {events.map((e) => {
        const related = frictionFor(e);
        return (
          <div key={e.id}>
            <button
              onClick={() => setOpen(open === e.id ? null : e.id)}
              className={`w-full text-left flex items-center gap-3 p-3 rounded-lg border text-sm
                ${e.event_type === "ERROR" ? "border-red-200 bg-red-50"
                  : e.success === 0 ? "border-orange-200 bg-orange-50"
                  : related ? "border-amber-200 bg-amber-50"
                  : "bg-white border-slate-200"} hover:border-slate-400 transition`}>
              <span aria-hidden="true">{ICONS[e.event_type] || "•"}</span>
              <span className="font-medium w-24 shrink-0">{e.event_type.replace("_", " ")}</span>
              <span className="text-slate-600 truncate flex-1">
                {elementLabel(e.element_text, e.element_id) || e.url}
              </span>
              {related && (
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${sevColor[related.severity] || sevColor.LOW}`}>
                  ⚠ {related.severity}
                </span>
              )}
              <span className="text-xs text-slate-400 shrink-0">{(e.ts_ms / 1000).toFixed(1)}s</span>
              <span className="text-xs text-slate-400 shrink-0">{e.success === 0 ? "failed" : ""}</span>
            </button>
            {open === e.id && (
              <div className="ml-8 mt-1 mb-2 bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm space-y-1">
                <p><strong className="text-slate-500">Timestamp:</strong> {(e.ts_ms / 1000).toFixed(1)}s into session</p>
                {e.url && <p className="break-all"><strong className="text-slate-500">URL:</strong> {e.url}</p>}
                {e.reason && <p><strong className="text-slate-500">Reason:</strong> "{e.reason}"</p>}
                {elementLabel(e.element_text, e.element_id) && (
                  <p><strong className="text-slate-500">Element:</strong> {elementLabel(e.element_text, e.element_id)}</p>
                )}
                {e.error && <p className="text-red-600"><strong>Error:</strong> {e.error}</p>}
                {related && (
                  <p className="text-amber-700">
                    <strong>Related friction:</strong> {related.title} ({related.severity}) — see Friction
                    Points below for full evidence.
                  </p>
                )}
                {e.screenshot_path && !brokenShots.has(e.id) && (
                  <img src={`/api/screenshots/${e.screenshot_path.split("/").pop()}`}
                    alt={`screenshot for step ${e.id}`}
                    onError={() => setBrokenShots((prev) => new Set(prev).add(e.id))}
                    className="mt-2 rounded border border-slate-200 max-w-sm" />
                )}
                {e.screenshot_path && brokenShots.has(e.id) && (
                  <p className="text-xs text-slate-400">Screenshot unavailable for this step.</p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
