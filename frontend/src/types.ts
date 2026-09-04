export interface ScoreBreakdown {
  ux_score: number; completed: number; efficiency: number;
  navigation: number; recovery: number; friction: number;
}
export interface Session {
  id: string; url: string; task: string; persona: string; status: string;
  completed: number | null; actions_count: number | null; duration_ms: number | null;
  pages_visited: number | null; friction_count: number | null; ux_score: number | null;
  score_breakdown: ScoreBreakdown | null; error: string | null; started_at: string;
  provider?: string | null;
  progress?: { step: string; idx: number } | null;
}
export interface FrictionWhy {
  observed: string | null;
  possible_cause: string | null;
  likely_root_cause: string | null;
  recommendation: string | null;
  confidence: number | null;
}
export interface FrictionPoint {
  id: number; title: string; severity: string; evidence: string;
  affected_action: string; confidence: number; recommendation: string; signal: string;
  why?: FrictionWhy;
}
export interface RootCause {
  observed: string; possible_cause: string; likely_root_cause: string; recommendation: string;
  confidence?: number;
}
export interface Analysis {
  executive_summary: string; root_causes: RootCause[]; provider: string;
  fallback?: boolean | number; fallback_reason?: string | null;
}
export interface EventItem {
  id: number; event_type: string; url: string; element_id: string | null;
  element_text: string | null; action: string | null; reason: string | null;
  confidence: number | null;
  screenshot_path: string | null; ts_ms: number; duration_ms: number | null;
  success: number; error: string | null;
}
