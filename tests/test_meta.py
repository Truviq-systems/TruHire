from backend.config import settings
from backend.models import CANDIDATE_STATUSES, REQUIREMENT_STATUSES
from test_location_role_filters import env  # noqa: F401  (shared fixture)


def test_meta_returns_enums_from_models(env):
    r = env["client"].get("/api/meta", headers=env["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["requirement_statuses"] == list(REQUIREMENT_STATUSES)
    assert body["search"]["max_top_n"] == settings.SEARCH_MAX_TOP_N
    assert body["comment_max_chars"] == settings.COMMENT_MAX_CHARS
    assert body["roles"] == ["admin", "recruiter"]
    assert body["candidate_statuses"] == list(CANDIDATE_STATUSES)


def test_meta_requires_auth(env):
    assert env["client"].get("/api/meta").status_code == 401


def test_meta_serves_the_report_tracker_and_ingestion_settings_the_ui_used_to_retype(env):
    from backend import models
    from backend.routers import tracker
    body = env["client"].get("/api/meta", headers=env["headers"]).json()

    # report rules: which demand statuses are excluded / fulfilled, and which review stages mean progress
    assert body["inactive_jd_statuses"] == list(models.INACTIVE_JD_STATUSES)
    assert body["fulfilled_jd_statuses"] == list(models.FULFILLED_JD_STATUSES)
    assert body["reason_required_jd_statuses"] == list(models.REASON_REQUIRED_JD_STATUSES)
    assert body["default_jd_status"] == models.DEFAULT_JD_STATUS == "Active"
    assert body["jd_statuses"] == ["Active", "Non-Active", "On Hold", "Filled"]
    assert body["progressed_requirement_statuses"] == list(models.PROGRESSED_REQUIREMENT_STATUSES)
    assert set(body["progressed_requirement_statuses"]) <= set(body["requirement_statuses"])
    assert set(body["inactive_jd_statuses"] + body["fulfilled_jd_statuses"]) <= set(body["jd_statuses"])
    assert body["analytics"] == {"timeline_weeks": settings.ANALYTICS_TIMELINE_WEEKS, "attention_limit": settings.ANALYTICS_ATTENTION_LIMIT}

    # availability, the trackers and the interview types
    assert body["availability_statuses"] == list(models.AVAILABILITY_STATUSES)
    assert body["default_availability"] in body["availability_statuses"]
    assert [k["key"] for k in body["tracker_kinds"]] == list(tracker.KIND_KEYS)
    assert all(k["title"] and k["description"] for k in body["tracker_kinds"] + body["interview_kinds"])
    assert [k["key"] for k in body["interview_kinds"]] == [k for k, _, _ in models.INTERVIEW_KINDS]
    assert body["demand_detail_fields"] == list(models.DEMAND_DETAIL_FIELDS)

    # ingestion progress: stages, per-file weights, which states are final and how outcomes are counted
    ingestion = body["ingestion"]
    assert [s["key"] for s in ingestion["stages"]] == [k for k, _ in models.INGEST_STAGES]
    assert ingestion["file_status_weights"] == models.INGEST_FILE_STATUS_WEIGHTS
    assert set(ingestion["final_file_statuses"]) == {k for k, w in models.INGEST_FILE_STATUS_WEIGHTS.items() if w == 1}
    for statuses in ingestion["file_outcomes"].values():
        assert set(statuses) <= set(ingestion["file_status_weights"])
    assert ingestion["slow_after_seconds"] == settings.INGEST_SLOW_AFTER_SECONDS
    assert set(ingestion["finished_batch_statuses"]) == {"completed", "failed", "cancelled"}


def test_the_batch_statuses_the_backend_writes_are_the_ones_the_ui_is_told_are_finished():
    import inspect
    from backend import models
    from backend.routers import ingestion
    source = inspect.getsource(ingestion)
    for status in models.INGEST_FINISHED_BATCH_STATUSES:
        assert f'"{status}"' in source, f"process_batch never writes {status!r}"
