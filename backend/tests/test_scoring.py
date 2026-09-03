from backend.app.analysis.scoring import compute_score

def test_perfect_run():
    s = {"completed": True, "actions_count": 5, "duration_ms": 20000}
    sc = compute_score(s, [], [])
    assert sc["ux_score"] > 85

def test_failed_run_scores_lower():
    good = compute_score({"completed": True, "actions_count": 5}, [], [])
    bad = compute_score({"completed": False, "actions_count": 20},
                        [{"severity": "CRITICAL"}], [])
    assert bad["ux_score"] < good["ux_score"]
