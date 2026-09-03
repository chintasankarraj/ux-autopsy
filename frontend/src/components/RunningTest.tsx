import { useEffect, useState } from "react";
import { api } from "../services/api";

export const STEPS = [
  "Initializing browser", "Loading website", "Understanding page",
  "Performing task", "Recording interactions", "Analyzing behavior",
  "Generating UX Autopsy",
];

/** Polls a session until it completes or fails, showing step-by-step progress. */
export default function RunningTest({
  sessionId,
  onDone,
  onFailed,
}: {
  sessionId: string;
  onDone: (session: any) => void;
  onFailed: (message: string) => void;
}) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    let stopped = false;
    const poll = async () => {
      try {
        const s = await api.session(sessionId);
        if (stopped) return;
        if (s.progress) setStep(s.progress.idx);
        if (s.status === "completed") onDone(s);
        else if (s.status === "failed") onFailed(s.error || "The test failed. See server logs.");
      } catch {
        // transient network hiccup — keep polling
      }
    };
    poll();
    const t = setInterval(poll, 1500);
    return () => {
      stopped = true;
      clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return (
    <div className="max-w-lg mx-auto py-12">
      <h1 className="text-xl font-semibold mb-6">Running UX Test…</h1>
      <ol className="space-y-3" aria-live="polite">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-3 text-sm">
            <span
              className={`w-5 h-5 rounded-full grid place-items-center text-xs shrink-0
              ${i < step ? "bg-emerald-500 text-white"
                : i === step ? "bg-blue-500 text-white animate-pulse"
                : "bg-slate-200 text-slate-500"}`}
            >
              {i < step ? "✓" : i + 1}
            </span>
            <span className={i <= step ? "text-slate-900" : "text-slate-400"}>{s}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
