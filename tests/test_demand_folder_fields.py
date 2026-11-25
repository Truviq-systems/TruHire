"""Folder counts, client name, timestamps, tentative end date and the Map -> Mapped rename."""
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.main import app
from backend.database import SessionLocal, engine, ensure_schema
from backend.models import Candidate, Position, User, canonical_demand_id, get_next_candidate_display_id
from backend.auth import create_access_token, get_password_hash

client = TestClient(app)
JAVA_JD = "Senior Java Developer. Build Spring Boot microservices with Hibernate and JPA on the JVM. Maven, JUnit."
JAVA = canonical_demand_id("Java")


def _headers():
    db = SessionLocal()
    try:
        user = db.query(User).first()
        if not user:
            user = User(email="recruiter@truhire.com", name="Test Recruiter", hashed_password=get_password_hash("pass123"))
            db.add(user)
            db.commit()
            db.refresh(user)
        return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}
    finally:
        db.close()


@pytest.fixture
def made():
    h = _headers()
    ids = []

    def make(title="Folder Field Test", **extra):
        r = client.post("/api/job-descriptions", json={"title": f"{title} {uuid.uuid4().hex[:5]}", "jd_text": JAVA_JD, **extra}, headers=h)
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
        return r.json()

    yield h, make
    for i in ids:
        client.delete(f"/api/job-descriptions/{i}", headers=h)


_resumes = []


@pytest.fixture(autouse=True)
def _remove_resumes():
    yield
    db = SessionLocal()
    try:
        db.query(Candidate).filter(Candidate.id.in_(_resumes)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    _resumes.clear()


def resume_id(name="Mapping Tester"):
    """A stored resume (candidate) to map demands to."""
    db = SessionLocal()
    try:
        user = db.query(User).first()
        cand = Candidate(candidate_name=name, display_id=get_next_candidate_display_id(db), extracted_skills=[], uploaded_by=user.id,
                         uploaded_at=datetime.utcnow(), file_hash=uuid.uuid4().hex, original_filename="r.pdf")
        db.add(cand)
        db.commit()
        _resumes.append(cand.id)
        return cand.id
    finally:
        db.close()


def _map(h, jd_id, status, ids):
    return client.put(f"/api/job-descriptions/{jd_id}/status", json={"status": status, "candidate_ids": ids}, headers=h)


def _java_folder(h):
    return next(d for d in client.get("/api/demands", headers=h).json() if d["id"] == JAVA)


def _cancel(h, jd_id, reason="Client withdrew the demand"):
    return client.put(f"/api/job-descriptions/{jd_id}/status", json={"status": "Non-Active", "cancellation_reason": reason}, headers=h)


def test_non_active_demands_are_not_counted_but_kept(made):
    h, make = made
    base = _java_folder(h)["jd_count"]
    a, b, c = make(), make(), make()
    assert _java_folder(h)["jd_count"] == base + 3
    assert _cancel(h, b["id"]).status_code == 200
    assert _cancel(h, c["id"]).status_code == 200
    assert _java_folder(h)["jd_count"] == base + 1
    # The records are still there, under the folder and by id.
    listed = {d["id"] for d in client.get(f"/api/demands/{JAVA}/job-descriptions", headers=h).json()}
    assert {a["id"], b["id"], c["id"]} <= listed
    assert client.get(f"/api/job-descriptions/{b['id']}", headers=h).json()["status"] == "Non-Active"
    # Reactivating counts it again.
    client.put(f"/api/job-descriptions/{b['id']}/status", json={"status": "Active"}, headers=h)
    assert _java_folder(h)["jd_count"] == base + 2
    # Filled and On Hold are counted.
    assert _map(h, a["id"], "Filled", [resume_id()]).status_code == 200
    assert _java_folder(h)["jd_count"] == base + 2


def test_client_name_is_optional_editable_clearable_and_known_or_typed(made):
    h, make = made
    jd = make()
    assert jd["client_name"] is None
    r = client.put(f"/api/job-descriptions/{jd['id']}", json={"client_name": "  Infosys "}, headers=h)
    assert r.status_code == 200 and r.json()["client_name"] == "Infosys"
    assert client.get(f"/api/job-descriptions/{jd['id']}", headers=h).json()["client_name"] == "Infosys"
    assert make(client_name="ntt data")["client_name"] == "NTT Data"  # matched case-insensitively, stored canonically
    r = client.put(f"/api/job-descriptions/{jd['id']}", json={"client_name": ""}, headers=h)
    assert r.json()["client_name"] is None
    # Editing something else leaves the client alone.
    client.put(f"/api/job-descriptions/{jd['id']}", json={"client_name": "Utsuk"}, headers=h)
    assert client.put(f"/api/job-descriptions/{jd['id']}", json={"location": "Pune"}, headers=h).json()["client_name"] == "Utsuk"
    # "Others": a client outside the list is stored as typed.
    assert client.put(f"/api/job-descriptions/{jd['id']}", json={"client_name": "  Globex  "}, headers=h).json()["client_name"] == "Globex"
    assert make(client_name="Initech")["client_name"] == "Initech"
    assert client.get("/api/meta", headers=h).json()["client_names"] == ["Cretera", "Infosys", "Coforge", "Aaseya", "NTT Data", "Utsuk"]


def test_folder_card_summarises_clients_of_counted_demands(made):
    h, make = made
    before = _java_folder(h)
    one = make(client_name="Utsuk")
    two = make(client_name="coforge")
    dup = make(client_name="COFORGE")
    none = make()
    gone = make(client_name="Aaseya")
    _cancel(h, gone["id"])
    folder = _java_folder(h)
    assert "Utsuk" in folder["clients"]
    assert sum(1 for c in folder["clients"] if c.lower() == "coforge") == 1  # same client, one entry
    assert "Aaseya" not in folder["clients"]  # cancelled demands do not count
    assert folder["clients"] == sorted(folder["clients"], key=str.lower)
    assert folder["unassigned_client_count"] == before["unassigned_client_count"] + 1
    assert {one["id"], two["id"], dup["id"], none["id"]}


def test_created_and_last_modified_timestamps(made):
    h, make = made
    jd = make()
    assert jd["created_at"] and jd["updated_at"] is None
    assert jd["last_modified_at"] == jd["created_at"]  # never edited: modified = created
    edited = client.put(f"/api/job-descriptions/{jd['id']}", json={"location": "Chennai"}, headers=h).json()
    assert edited["updated_at"] and edited["last_modified_at"] == edited["updated_at"]
    assert edited["created_at"] == jd["created_at"]
    assert edited["last_modified_at"] >= jd["created_at"]
    # A status change and a client change also move it; a no-op save does not.
    again = client.put(f"/api/job-descriptions/{jd['id']}", json={"location": "Chennai"}, headers=h).json()
    assert again["updated_at"] == edited["updated_at"]
    st = _cancel(h, jd["id"]).json()
    assert st["last_modified_at"] >= edited["last_modified_at"]
    listed = next(p for p in client.get("/api/job-descriptions", headers=h).json() if p["id"] == jd["id"])
    assert listed["last_modified_at"] == st["last_modified_at"]


def test_tentative_end_date_can_be_changed_and_cleared(made):
    h, make = made
    jd = make(start_date="2026-01-01", end_date="2026-06-30")
    r = client.put(f"/api/job-descriptions/{jd['id']}", json={"end_date": "2026-09-30"}, headers=h)
    assert r.json()["end_date"] == "2026-09-30"
    r = client.put(f"/api/job-descriptions/{jd['id']}", json={"end_date": None}, headers=h)
    assert r.status_code == 200 and r.json()["end_date"] is None
    assert r.json()["start_date"] == "2026-01-01"
    assert client.put(f"/api/job-descriptions/{jd['id']}", json={"end_date": "2025-01-01"}, headers=h).status_code == 422


def test_legacy_statuses_map_and_old_values_are_accepted(made):
    h, make = made
    meta = client.get("/api/meta", headers=h).json()
    assert meta["jd_statuses"] == ["Active", "Non-Active", "On Hold", "Filled"]
    rid = resume_id()
    jd = make(status="Filled", candidate_ids=[rid])
    assert jd["status"] == "Filled"
    # Old clients that still send "Open" / "Map" / "Mapped" / "Fulfilled" are accepted and normalized.
    r = client.put(f"/api/job-descriptions/{jd['id']}/status", json={"status": "Open"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "Active"
    r = client.put(f"/api/job-descriptions/{jd['id']}/status", json={"status": "Map", "candidate_ids": [rid]}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "Filled"
    assert make(status="Mapped", candidate_ids=[rid])["status"] == "Filled"
    assert client.put(f"/api/job-descriptions/{jd['id']}/status", json={"status": "Nope"}, headers=h).status_code == 400


def test_existing_legacy_status_rows_are_migrated(made):
    h, make = made
    jd_map = make()
    jd_open = make()
    with engine.begin() as c:
        c.execute(text("UPDATE positions SET status = 'Map' WHERE id = :i"), {"i": jd_map["id"]})
        c.execute(text("UPDATE positions SET status = 'Open' WHERE id = :i"), {"i": jd_open["id"]})
    ensure_schema()
    with engine.connect() as c:
        assert c.execute(text("SELECT status FROM positions WHERE id = :i"), {"i": jd_map["id"]}).scalar() == "Filled"
        assert c.execute(text("SELECT status FROM positions WHERE id = :i"), {"i": jd_open["id"]}).scalar() == "Active"


def test_non_active_and_on_hold_need_a_reason_which_is_kept_until_active(made):
    h, make = made
    jd = make()
    url = f"/api/job-descriptions/{jd['id']}/status"
    assert client.put(url, json={"status": "Non-Active"}, headers=h).status_code == 422
    assert client.put(url, json={"status": "Non-Active", "cancellation_reason": "   "}, headers=h).status_code == 422
    assert client.put(url, json={"status": "On Hold"}, headers=h).status_code == 422
    assert client.get(f"/api/job-descriptions/{jd['id']}", headers=h).json()["status"] == "Active"  # nothing half-saved
    r = _cancel(h, jd["id"], "  Budget frozen  ")
    assert r.status_code == 200 and r.json()["cancellation_reason"] == "Budget frozen"
    listed = next(p for p in client.get("/api/job-descriptions", headers=h).json() if p["id"] == jd["id"])
    assert listed["status"] == "Non-Active" and listed["cancellation_reason"] == "Budget frozen"  # persisted, survives a reload
    # On Hold also requires and saves a reason.
    r_hold = client.put(url, json={"status": "On Hold", "cancellation_reason": "Awaiting client sign-off"}, headers=h)
    assert r_hold.status_code == 200 and r_hold.json()["status"] == "On Hold" and r_hold.json()["cancellation_reason"] == "Awaiting client sign-off"
    # The same through the edit form (PUT) and in the history log.
    other = make()
    assert client.put(f"/api/job-descriptions/{other['id']}", json={"status": "Non-Active"}, headers=h).status_code == 422
    r = client.put(f"/api/job-descriptions/{other['id']}", json={"status": "Non-Active", "cancellation_reason": "Role merged"}, headers=h)
    assert r.status_code == 200 and r.json()["cancellation_reason"] == "Role merged"
    history = client.get("/api/requirement-history", params={"action": "status_changed", "limit": 200}, headers=h).json()["items"]
    entry = next(e for e in history if e["item_id"] == other["id"])
    assert entry["changes"]["cancellation_reason"]["new"] == "Role merged"
    # Returning to Active clears it.
    r = client.put(f"/api/job-descriptions/{jd['id']}/status", json={"status": "Active"}, headers=h)
    assert r.json()["status"] == "Active" and r.json()["cancellation_reason"] is None


def test_filled_needs_resumes_which_are_listed_and_persist(made):
    h, make = made
    jd = make()
    a, b = resume_id("Asha Rao"), resume_id("Vikram Shah")
    assert _map(h, jd["id"], "Filled", []).status_code == 422
    assert client.put(f"/api/job-descriptions/{jd['id']}/status", json={"status": "Filled"}, headers=h).status_code == 422
    assert _map(h, jd["id"], "Filled", [a, "no-such-resume"]).status_code == 422
    assert client.get(f"/api/job-descriptions/{jd['id']}", headers=h).json()["mapped_resumes"] == []
    r = _map(h, jd["id"], "Filled", [a, b, a])  # duplicates collapse
    assert r.status_code == 200
    assert sorted(x["candidate_name"] for x in r.json()["mapped_resumes"]) == ["Asha Rao", "Vikram Shah"]
    assert all(x["display_id"] and x["id"] for x in r.json()["mapped_resumes"])
    listed = next(p for p in client.get("/api/job-descriptions", headers=h).json() if p["id"] == jd["id"])
    assert {x["id"] for x in listed["mapped_resumes"]} == {a, b}
    # Updating status to Filled again keeps the resumes unless new ones are sent.
    r = client.put(f"/api/job-descriptions/{jd['id']}/status", json={"status": "Filled"}, headers=h)
    assert r.status_code == 200 and {x["id"] for x in r.json()["mapped_resumes"]} == {a, b}
    r = _map(h, jd["id"], "Filled", [b])
    assert [x["id"] for x in r.json()["mapped_resumes"]] == [b]
    # Another status drops them.
    assert client.put(f"/api/job-descriptions/{jd['id']}/status", json={"status": "Active"}, headers=h).json()["mapped_resumes"] == []


def test_a_resume_deleted_after_mapping_does_not_break_the_demand(made):
    h, make = made
    jd = make()
    a, b = resume_id("Stays"), resume_id("Goes")
    _map(h, jd["id"], "Filled", [a, b])
    db = SessionLocal()
    try:
        db.query(Candidate).filter(Candidate.id == b).delete()
        db.commit()
    finally:
        db.close()
    got = client.get(f"/api/job-descriptions/{jd['id']}", headers=h)
    assert got.status_code == 200 and [x["id"] for x in got.json()["mapped_resumes"]] == [a]
    listed = next(p for p in client.get("/api/job-descriptions", headers=h).json() if p["id"] == jd["id"])
    assert [x["id"] for x in listed["mapped_resumes"]] == [a]


def test_saving_a_demand_records_who_modified_it_and_when(made):
    h, make = made
    jd = make()
    assert jd["last_modified_by"] == jd["created_by_name"]  # never edited: the creator
    r = client.put(f"/api/job-descriptions/{jd['id']}", json={"location": "Mumbai"}, headers=h).json()
    assert r["last_modified_by"] and r["last_modified_at"] == r["updated_at"]
    listed = next(p for p in client.get("/api/job-descriptions", headers=h).json() if p["id"] == jd["id"])
    assert listed["last_modified_by"] == r["last_modified_by"]
    # A save that changes nothing leaves both alone.
    again = client.put(f"/api/job-descriptions/{jd['id']}", json={"location": "Mumbai"}, headers=h).json()
    assert again["updated_at"] == r["updated_at"]


def test_closed_no_longer_exists_and_old_closed_rows_become_non_active(made):
    h, make = made
    meta = client.get("/api/meta", headers=h).json()
    assert meta["jd_statuses"] == ["Active", "Non-Active", "On Hold", "Filled"] and meta["resume_linked_jd_statuses"] == ["Filled"]
    assert meta["reason_required_jd_statuses"] == ["Non-Active", "On Hold"]
    jd = make()
    with engine.begin() as c:
        c.execute(text("UPDATE positions SET status = 'Closed' WHERE id = :i"), {"i": jd["id"]})
    ensure_schema()
    got = client.get(f"/api/job-descriptions/{jd['id']}", headers=h).json()
    assert got["status"] == "Non-Active" and got["cancellation_reason"] is None  # no reason was ever recorded: handled, not an error


def test_resume_search_by_id_or_name_for_the_mapping_popup(made):
    h, _ = made
    name = f"Zyxwv{uuid.uuid4().hex[:6]}"
    rid = resume_id(f"{name} Quill")
    by_name = client.get("/api/candidates", params={"q": name.lower()}, headers=h).json()
    assert [c["id"] for c in by_name["candidates"]] == [rid] and by_name["total"] == 1
    display_id = by_name["candidates"][0]["display_id"]
    by_id = client.get("/api/candidates", params={"q": display_id.lower()}, headers=h).json()
    assert rid in [c["id"] for c in by_id["candidates"]]
    assert client.get("/api/candidates", params={"q": "no-such-resume-xyz%"}, headers=h).json()["candidates"] == []
