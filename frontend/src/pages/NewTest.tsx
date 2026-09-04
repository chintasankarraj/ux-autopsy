import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../services/api";
import RunningTest from "../components/RunningTest";

const PERSONAS: [string, string, string][] = [
  ["budget_shopper", "Budget Shopper", "Price-conscious; searches, then filters by budget before buying."],
  ["impatient", "Impatient User", "Low patience; clicks the first prominent control without reading."],
  ["beginner", "Confused Beginner", "Tries 'Add to Cart' before 'Buy Now'; pauses before retrying."],
  ["power_user", "Power User", "Skips search; goes straight to category and price filters."],
  ["mobile_user", "Mobile User", "Narrow viewport; controls collapse behind a mobile menu."],
  ["custom", "Custom Persona", "Describe your own synthetic user."],
];
const DEMO_URL = "http://localhost:8000/api/demo-site/";
const DEMO_TASK = "Find a laptop under ₹60,000 and complete the purchase.";

export default function NewTest() {
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const demo = sp.get("demo") === "1";
  const [url, setUrl] = useState(demo ? DEMO_URL : "");
  const [task, setTask] = useState(demo ? DEMO_TASK : "");
  const [persona, setPersona] = useState("budget_shopper");
  const [custom, setCustom] = useState("");
  const [err, setErr] = useState("");
  const [sid, setSid] = useState<string | null>(null);
  const [failMsg, setFailMsg] = useState("");

  const submit = async () => {
    setErr(""); setFailMsg("");
    if (!url.trim()) return setErr("Please enter a website URL.");
    if (task.trim().length < 5) return setErr("Please describe the task (min 5 characters).");
    try {
      const r = await api.create({ url, task, persona, custom_persona: custom || null });
      setSid(r.id);
    } catch (e: any) { setErr(e.message); }
  };

  if (sid) return (
    <div>
      <RunningTest
        sessionId={sid}
        onDone={() => nav(`/sessions/${sid}`)}
        onFailed={(msg) => setFailMsg(msg)}
      />
      {failMsg && (
        <p className="max-w-lg mx-auto -mt-6 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          {failMsg}
          <button onClick={() => { setSid(null); setFailMsg(""); }} className="block mt-2 underline">
            Try again
          </button>
        </p>
      )}
    </div>
  );

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-xl font-semibold mb-1">New UX Test</h1>
      <p className="text-sm text-slate-500 mb-6">
        A synthetic user will attempt your task in a real browser.
      </p>
      {err && <p className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{err}</p>}
      <label className="block text-sm font-medium mb-1" htmlFor="url">Website URL</label>
      <input id="url" value={url} onChange={(e) => setUrl(e.target.value)}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-4 focus:ring-2 focus:ring-slate-900 outline-none"
        placeholder="https://your-site.com or the demo store URL" />
      <label className="block text-sm font-medium mb-1" htmlFor="task">Task description</label>
      <textarea id="task" value={task} onChange={(e) => setTask(e.target.value)} rows={3}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 mb-4 focus:ring-2 focus:ring-slate-900 outline-none"
        placeholder="e.g. Find a laptop under ₹60,000 and complete the purchase." />
      <fieldset className="mb-4">
        <legend className="text-sm font-medium mb-2">Persona</legend>
        <div className="grid sm:grid-cols-2 gap-2">
          {PERSONAS.map(([id, name, desc]) => (
            <label key={id}
              className={`border rounded-lg p-3 cursor-pointer text-sm transition
                ${persona === id ? "border-slate-900 ring-1 ring-slate-900 bg-slate-50" : "border-slate-200 hover:border-slate-400"}`}>
              <input type="radio" name="persona" className="sr-only"
                checked={persona === id} onChange={() => setPersona(id)} />
              <span className="font-medium">{name}</span>
              <span className="block text-xs text-slate-500 mt-0.5">{desc}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {persona === "custom" && (
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1" htmlFor="custom">Describe your persona</label>
          <textarea id="custom" value={custom} onChange={(e) => setCustom(e.target.value)} rows={2}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-slate-900 outline-none"
            placeholder="e.g. Budget-conscious college student with moderate technical knowledge." />
        </div>
      )}
      <button onClick={submit}
        className="w-full bg-slate-900 text-white py-2.5 rounded-lg font-medium hover:bg-slate-700">
        Start UX Test
      </button>
      <p className="text-xs text-slate-400 mt-3 text-center">
        {demo ? "Demo mode: runs against the built-in PixelMart store — no API key needed." :
          "Tip: use “View Demo” on the dashboard to try the built-in demo store."}
      </p>
    </div>
  );
}
