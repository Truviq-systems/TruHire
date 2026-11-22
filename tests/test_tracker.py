from test_location_role_filters import env
from backend.models import Candidate, CandidateMatch, Position
from backend.services.candidates.tracker_fields import resume_fields


def _submit(env, status="Shortlisted", resume_text=None):
    candidate_id, position_id = env["make"](), env["make_jd"]()
    env["db"].get(Position, position_id).client_name = "Aaseya"
    cand = env["db"].get(Candidate, candidate_id)
    cand.phone, cand.extracted_skills, cand.years_experience = "9876543210", ["Camunda", "Java"], 6.0
    cand.resume_text = resume_text
    env["db"].commit()
    env["client"].put(f"/api/job-descriptions/{position_id}/candidates/{candidate_id}/status",
                      headers=env["headers"], json={"status": status})
    return candidate_id, position_id


def test_tracker_lists_only_status_set_candidates_with_autofill(env):
    candidate_id, position_id = _submit(env)
    other = env["make"]()
    env["db"].add(CandidateMatch(candidate_id=other, position_id=position_id, match_score=90.0))
    env["db"].commit()

    body = env["client"].get("/api/tracker", headers=env["headers"], params={"position_id": position_id}).json()
    assert [r["candidate_id"] for r in body["rows"]] == [candidate_id]
    values = body["rows"][0]["values"]
    assert values["primary_skill"] == "Camunda" and values["contact_no"] == "9876543210"
    assert values["interview_status"] == "Shortlisted" and values["recruiter"] == env["user"].name
    assert body["columns"][0]["label"] == "Primary Skill" and body["columns"][-1]["label"] == "Frameworks"
    by_client = env["client"].get("/api/tracker", headers=env["headers"], params={"client": " aaseya "}).json()
    assert candidate_id in [r["candidate_id"] for r in by_client["rows"]]


def test_tracker_fills_stated_resume_fields_and_cannot_be_edited(env):
    text = "Current CTC: 12 LPA\nExpected CTC: 16 LPA\nNotice Period: 30 days\nPreferred Location: Pune\nWorked on Banking projects with Spring Boot."
    candidate_id, position_id = _submit(env, resume_text=text)
    row = env["client"].get("/api/tracker", headers=env["headers"], params={"position_id": position_id}).json()["rows"][0]["values"]
    assert row["current_ctc"] == "12 LPA" and row["expected_ctc"] == "16 LPA" and row["preferred_location"] == "Pune"
    assert row["domains"] == "Banking" and "Spring Boot" in row["frameworks"]
    assert "lwd" not in row  # not stated in the resume: blank, never guessed
    assert env["client"].put(f"/api/tracker/{position_id}/{candidate_id}", headers=env["headers"], json={"data": {"current_ctc": "1"}}).status_code in (404, 405)


def test_resume_fields_blank_when_nothing_is_stated():
    assert resume_fields("Just a name and some skills", []) == {}


# ── Editable Pipeline / Submission trackers ──────────────────────────────────────────────────

def _entry(env, kind, **body):
    return env["client"].post(f"/api/tracker/{kind}/entries", headers=env["headers"], json=body)


def test_pipeline_lists_the_five_stages_in_order_with_counts(env):
    body = env["client"].get("/api/tracker/pipeline", headers=env["headers"]).json()
    assert [s["label"] for s in body["stages"]] == ["L2 Sheets", "L1 Sheets", "Interview to be Scheduled", "Interview Reject", "Screen Reject"]
    assert len(body["columns"]) == 39
    assert body["columns"][0]["label"] == "Primary Skill" and body["columns"][-1]["label"] == "L2 Interview Panel"


def test_pipeline_entry_create_edit_move_delete(env):
    created = _entry(env, "pipeline", data={"candidate_name": "Asha Rao", "primary_skill": "Java"})
    assert created.status_code == 201 and created.json()["stage"] == "l2_sheets"
    entry_id = created.json()["id"]

    edited = env["client"].patch(f"/api/tracker/entries/{entry_id}", headers=env["headers"],
                                 json={"stage": "screen_reject", "data": {"candidate_name": "Asha R", "primary_skill": ""}})
    assert edited.status_code == 200
    assert edited.json()["stage"] == "screen_reject"
    assert edited.json()["data"] == {"candidate_name": "Asha R"}  # emptied field dropped

    counts = {s["key"]: s["count"] for s in env["client"].get("/api/tracker/pipeline", headers=env["headers"]).json()["stages"]}
    assert counts["screen_reject"] >= 1

    assert env["client"].delete(f"/api/tracker/entries/{entry_id}", headers=env["headers"]).status_code == 204
    assert env["client"].delete(f"/api/tracker/entries/{entry_id}", headers=env["headers"]).status_code == 404


def test_tracker_entry_rejects_unknown_columns_stages_and_trackers(env):
    assert _entry(env, "pipeline", data={"nope": "x"}).status_code == 422
    assert _entry(env, "pipeline", stage="bogus").status_code == 422
    assert _entry(env, "pipeline", data={"client_interview_time": "10:00"}).status_code == 422  # submission-only column
    assert env["client"].get("/api/tracker/unknown", headers=env["headers"]).status_code == 404


def test_submission_uses_client_columns_and_validates_status(env):
    body = env["client"].get("/api/tracker/submission", headers=env["headers"]).json()
    labels = [c["label"] for c in body["columns"]]
    assert "Client Submission Date" in labels and "Client Interview Status" in labels
    assert "Client Interview Date" in labels and "Client Interview Time" in labels
    assert "Source date" not in labels and "Internal Interview Status" not in labels
    created = _entry(env, "submission", data={"candidate_name": "Ravi", "client_interview_status": body["statuses"][0]})
    assert created.status_code == 201 and created.json()["data"]["client_submission_date"]
    assert _entry(env, "submission", data={"client_interview_status": "Not A Status"}).status_code == 422


def test_entry_from_candidate_prefills_and_availability_filter(env):
    candidate_id = env["make"]()
    cand = env["db"].get(Candidate, candidate_id)
    cand.phone, cand.extracted_skills = "9000000001", ["Pega"]
    env["db"].commit()
    created = _entry(env, "pipeline", candidate_id=candidate_id)
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["contact_no"] == "9000000001" and data["primary_skill"] == "Pega" and "source_date" not in data
    assert created.json()["availability"] == "Active"

    env["client"].patch(f"/api/candidates/{candidate_id}/availability", headers=env["headers"], json={"status": "Not Active"})
    inactive = env["client"].get("/api/tracker/pipeline", headers=env["headers"], params={"availability": "Not Active"}).json()
    assert created.json()["id"] in [r["id"] for r in inactive["rows"]]
    active = env["client"].get("/api/tracker/pipeline", headers=env["headers"], params={"availability": "Active"}).json()
    assert created.json()["id"] not in [r["id"] for r in active["rows"]]
    assert env["client"].get("/api/tracker/pipeline", headers=env["headers"], params={"availability": "x"}).status_code == 422
    assert _entry(env, "pipeline", candidate_id="missing").status_code == 404


# ── Startup index reconciliation (lives here with the other new-feature tests) ──────────────

def test_reconcile_reindexes_only_when_an_index_lags_the_database(env, monkeypatch):
    from backend.routers import ingestion
    candidate_id = env["make"]()
    cand = env["db"].get(Candidate, candidate_id)
    cand.resume_text = "Java developer"
    env["db"].commit()
    total = env["db"].query(Candidate).filter(Candidate.resume_text != "").count()

    calls = []
    monkeypatch.setattr(ingestion, "_reindex_task", lambda ids, user_id: calls.append(list(ids)))

    monkeypatch.setattr(ingestion, "index_status_counts", lambda: {"documents": 0, "points": total})  # keyword index empty
    ingestion.reconcile_indexes()
    assert len(calls) == 1 and candidate_id in calls[0]

    monkeypatch.setattr(ingestion, "index_status_counts", lambda: {"documents": total, "points": total})  # in sync
    ingestion.reconcile_indexes()
    assert len(calls) == 1


# ── Analytics requirements report ───────────────────────────────────────────────────────────

def test_requirements_report_lists_each_requirement_with_stage_counts(env):
    candidate_id, position_id = _submit(env, status="Shortlisted")
    body = env["client"].get("/api/insights/requirements", headers=env["headers"]).json()
    row = next(r for r in body["requirements"] if r["id"] == position_id)
    assert row["client_name"] == "Aaseya" and row["no_of_positions"] >= 1
    assert row["stages"]["Shortlisted"] == 1 and set(row["stages"]) == set(body["stages"])
    assert row["status"] in ("Open", "Mapped", "Fulfilled", "Cancelled")


def test_the_old_analytics_paths_still_answer_so_an_older_frontend_keeps_working(env):
    for new, old in (("/api/insights/requirements", "/api/analytics/requirements"), ("/api/insights/overview", "/api/analytics/overview")):
        current = env["client"].get(new, headers=env["headers"])
        legacy = env["client"].get(old, headers=env["headers"])
        assert current.status_code == legacy.status_code == 200
        assert set(current.json()) == set(legacy.json())
