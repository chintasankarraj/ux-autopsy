const j = async (r: Response) => {
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return r.json();
};

export const api = {
  health: () => fetch("/api/health").then(j),
  stats: () => fetch("/api/stats").then(j),
  sessions: () => fetch("/api/sessions").then(j),
  session: (id: string) => fetch(`/api/sessions/${id}`).then(j),
  events: (id: string) => fetch(`/api/sessions/${id}/events`).then(j),
  analysis: (id: string) => fetch(`/api/sessions/${id}/analysis`).then(j),
  create: (b: object) =>
    fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(b),
    }).then(j),
  retest: (id: string) =>
    fetch(`/api/sessions/${id}/retest`, { method: "POST" }).then(j),
};
