W = {"completion": 0.35, "efficiency": 0.20, "navigation": 0.15,
     "recovery": 0.15, "friction": 0.15}

def compute_score(summary, friction_points, events):
    completed = 100.0 if summary.get("completed") else 0.0
    n = max(summary.get("actions_count", 1), 1)
    efficiency = max(0.0, 100.0 - (n - 6) * 7.0)

    urls = [e["url"] for e in events if e["url"]]
    backtracks = sum(1 for i, u in enumerate(urls) if u in urls[:i])
    navigations = sum(1 for e in events if e["event_type"] == "NAVIGATION")
    navigation = max(0.0, 100.0 - backtracks * 15.0 - max(0, navigations - 3) * 8.0)

    errors = sum(1 for e in events if e["event_type"] == "ERROR")
    recovery = max(0.0, 100.0 - errors * 25.0)
    if errors and summary.get("completed"):
        recovery = min(100.0, recovery + 15.0)

    penalty = sum({"CRITICAL": 30, "HIGH": 18, "MEDIUM": 8, "LOW": 3}
                  .get(p["severity"], 5) for p in friction_points)
    friction = max(0.0, 100.0 - penalty)

    total = (completed * W["completion"] + efficiency * W["efficiency"]
             + navigation * W["navigation"] + recovery * W["recovery"] + friction * W["friction"])
    return {"ux_score": round(total, 1), "completed": completed,
            "efficiency": round(efficiency, 1), "navigation": round(navigation, 1),
            "recovery": round(recovery, 1), "friction": round(friction, 1)}
