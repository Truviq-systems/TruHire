"""Trackers. GET "" is the read-only Requirement Tracker (one row per candidate a recruiter has set a
status on for a requirement). /pipeline and /submission are the editable sheets: rows a recruiter adds,
edits, moves between stages and deletes."""
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.services.candidates.tracker_fields import resume_fields
from backend.models import AVAILABILITY_STATUSES, DEFAULT_AVAILABILITY, Candidate, Position, RequirementCandidateStatus, TrackerEntry, User
from backend.services.common.cache import bump_data_epoch

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

# (key, label) in table order. Read-only: values come from the candidate record and what the resume states.
COLUMNS = (
    ("primary_skill", "Primary Skill"), ("recruiter", "Recruiter"), ("source_name", "Source Name"),
    ("source_date", "Source Date"), ("interview_status", "Internal Interview Status"),
    ("candidate_name", "Candidate Name"), ("contact_no", "Contact No"), ("email", "Email ID"),
    ("total_experience", "Total Experience"), ("relevant_experience", "Relevant Experience"),
    ("payroll_company", "Payroll Company"), ("serving_notice", "Serving Notice"), ("notice_period", "Notice Period"),
    ("lwd", "LWD (Last Working Date)"), ("expected_joining", "Expected Joining Date"),
    ("current_ctc", "Current CTC"), ("expected_ctc", "Expected CTC"), ("current_location", "Current Location"),
    ("preferred_location", "Preferred Location"), ("offer_in_hand", "Offer in Hand"),
    ("reason_for_change", "Reason for Change"), ("domains", "Domains"), ("frameworks", "Frameworks"),
)
MAX_ROWS = 1000


def _auto(cand: Candidate, status: str, recruiter: Optional[str]) -> dict:
    notice = f"{cand.notice_period_value:g} {cand.notice_period_unit}" if cand.notice_period_value is not None and cand.notice_period_unit else None
    skills = cand.extracted_skills or []
    values = {
        "primary_skill": skills[0] if skills else None, "recruiter": recruiter,
        "source_date": cand.uploaded_at.isoformat() if cand.uploaded_at else None, "interview_status": status,
        "candidate_name": cand.candidate_name, "contact_no": cand.phone, "email": cand.email,
        "total_experience": f"{cand.years_experience:g} yrs" if cand.years_experience is not None else None,
        "payroll_company": cand.current_company, "notice_period": notice, "current_location": cand.location,
    }
    return {**resume_fields(cand.resume_text, skills), **{k: v for k, v in values.items() if v not in (None, "")}}


@router.get("")
def tracker_rows(position_id: Optional[str] = None, client: Optional[str] = None,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = (db.query(RequirementCandidateStatus, Candidate, Position, User.name)
             .join(Candidate, Candidate.id == RequirementCandidateStatus.candidate_id)
             .join(Position, Position.id == RequirementCandidateStatus.position_id)
             .outerjoin(User, User.id == RequirementCandidateStatus.updated_by))
    if position_id:
        query = query.filter(RequirementCandidateStatus.position_id == position_id)
    if client and client.strip():
        query = query.filter(func.lower(func.trim(Position.client_name)) == client.strip().lower())
    rows = query.order_by(Position.client_name, Position.display_id, RequirementCandidateStatus.updated_at.desc()).limit(MAX_ROWS).all()
    return {"columns": [{"key": k, "label": label} for k, label in COLUMNS],
            "rows": [{"position_id": pos.id, "candidate_id": cand.id, "demand_id": pos.display_id,
                      "demand_title": pos.title, "client_name": pos.client_name,
                      "values": _auto(cand, status.status, recruiter)}
                     for status, cand, pos, recruiter in rows]}


# ── Editable trackers ────────────────────────────────────────────────────────────────────────
# (key, label, kind) in table order. kind drives the input: text, date, time, long (textarea), link.
_PROFILE = (
    ("candidate_name", "Candidate Name", "text"), ("contact_no", "Contact No", "text"), ("email", "Email ID", "text"),
    ("total_experience", "Total Experience", "text"), ("relevant_experience", "Relevant Experience", "text"),
    ("payroll_company", "Payroll Company", "text"), ("serving_notice", "Serving Notice", "text"),
    ("notice_period", "Notice Period", "text"), ("lwd", "LWD (Last Working Date)", "date"),
    ("expected_joining", "Expected Joining Date", "date"), ("current_ctc", "Current CTC", "text"),
    ("expected_ctc", "Expected CTC", "text"), ("current_location", "Current Location", "text"),
    ("preferred_location", "Preferred Location", "text"), ("offer_in_hand", "Offer in Hand", "text"),
    ("reason_for_change", "Reason for Change", "long"), ("domains", "Domains", "text"), ("frameworks", "Frameworks", "text"),
    ("comments", "Comments", "long"), ("certifications", "Certifications", "text"), ("ats_match", "ATS Match %", "text"),
    ("remarks", "Remarks / Profile Summary", "long"), ("linkedin", "LinkedIn Profile Link", "link"),
    ("previous_designation", "Previous Designation", "text"), ("past_companies", "Past Companies", "text"),
    ("education", "Education", "text"), ("key_skills", "Key Skills", "text"), ("tagline", "Profile Tag line", "text"),
)
PIPELINE_COLUMNS = (
    ("primary_skill", "Primary Skill", "text"), ("recruiter", "Recruiter", "text"), ("source_name", "Source Name", "text"),
    ("source_date", "Source date", "date"), ("interview_status", "Internal Interview Status", "text"),
    ("interview_date", "Internal Interview Date", "date"), ("interview_panel", "Internal Interview Panel", "text"),
    *_PROFILE,
    ("l1_date", "L1 Interview Date", "date"), ("l1_panel", "L1 Interview Panel", "text"),
    ("l2_date", "L2 Interview Date", "date"), ("l2_panel", "L2 Interview Panel", "text"),
)
# Client submissions: source date and internal interview status become their client equivalents, the
# client interview date and time are added, and the internal / L1 / L2 interview fields do not apply.
SUBMISSION_COLUMNS = (
    ("primary_skill", "Primary Skill", "text"), ("recruiter", "Recruiter", "text"), ("source_name", "Source Name", "text"),
    ("client_submission_date", "Client Submission Date", "date"), ("client_interview_status", "Client Interview Status", "text"),
    ("client_interview_date", "Client Interview Date", "date"), ("client_interview_time", "Client Interview Time", "time"),
    *_PROFILE,
)
PIPELINE_STAGES = (
    ("l2_sheets", "L2 Sheets"), ("l1_sheets", "L1 Sheets"), ("interview_to_be_scheduled", "Interview to be Scheduled"),
    ("interview_reject", "Interview Reject"), ("screen_reject", "Screen Reject"),
)
SUBMISSION_STAGE = "submitted"
# Dropdown for Client Interview Status. Provisional until the real list is supplied; edit here only.
SUBMISSION_STATUSES = ("Submitted", "Under Review", "Interview Scheduled", "Selected", "Rejected", "On Hold")

_KINDS = {
    "pipeline": {"title": "Pipeline Tracker", "description": "Candidates by stage, from L2 sheets down to screen rejects.",
                 "columns": PIPELINE_COLUMNS, "stages": PIPELINE_STAGES, "default_stage": PIPELINE_STAGES[0][0]},
    "submission": {"title": "Submission Tracker", "description": "Candidates submitted to clients, with the client interview status and schedule.",
                   "columns": SUBMISSION_COLUMNS, "stages": ((SUBMISSION_STAGE, "Submissions"),), "default_stage": SUBMISSION_STAGE},
}
KIND_KEYS = tuple(_KINDS)


def tracker_kinds() -> list:
    """The trackers the UI offers, in order: [{key, title, description}]."""
    return [{"key": key, "title": spec["title"], "description": spec["description"]} for key, spec in _KINDS.items()]
_MAX_VALUE_LEN = 2000


class EntryIn(BaseModel):
    stage: Optional[str] = None
    candidate_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class EntryPatch(BaseModel):
    stage: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


def _kind(kind: str) -> dict:
    if kind not in _KINDS:
        raise HTTPException(status_code=404, detail="Unknown tracker.")
    return _KINDS[kind]


def _clean(kind: str, data: Dict[str, Any]) -> Dict[str, str]:
    allowed = {key for key, _, _ in _kind(kind)["columns"]}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown column(s): {', '.join(unknown)}.")
    cleaned = {k: str(v).strip() for k, v in data.items() if v is not None}
    if any(len(v) > _MAX_VALUE_LEN for v in cleaned.values()):
        raise HTTPException(status_code=422, detail=f"Values are limited to {_MAX_VALUE_LEN} characters.")
    status = cleaned.get("client_interview_status")
    if kind == "submission" and status and status not in SUBMISSION_STATUSES:
        raise HTTPException(status_code=422, detail="Client Interview Status is not one of the allowed values.")
    return {k: v for k, v in cleaned.items() if v}


def _stage(kind: str, stage: Optional[str]) -> str:
    spec = _kind(kind)
    stage = stage or spec["default_stage"]
    if stage not in {key for key, _ in spec["stages"]}:
        raise HTTPException(status_code=422, detail="Unknown stage.")
    return stage


def _serialize(entry: TrackerEntry, availability: Optional[str]) -> dict:
    return {"id": entry.id, "stage": entry.stage, "candidate_id": entry.candidate_id, "availability": availability,
            "data": entry.data or {}, "updated_at": entry.updated_at.isoformat() if entry.updated_at else None}


def _availability(db: Session, entry: TrackerEntry) -> Optional[str]:
    if not entry.candidate_id:
        return None
    return db.query(Candidate.availability_status).filter(Candidate.id == entry.candidate_id).scalar() or DEFAULT_AVAILABILITY


@router.get("/{kind}")
def sheet(kind: str, availability: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Columns, stage counts and rows. availability=Active|Not Active keeps rows whose linked candidate has that availability."""
    spec = _kind(kind)
    if availability not in (None, *AVAILABILITY_STATUSES):
        raise HTTPException(status_code=422, detail="availability must be one of: " + ", ".join(AVAILABILITY_STATUSES) + ".")
    query = (db.query(TrackerEntry, Candidate.availability_status)
             .outerjoin(Candidate, Candidate.id == TrackerEntry.candidate_id)
             .filter(TrackerEntry.tracker == kind))
    if availability:
        # A candidate with no stored availability counts as the default, matching the Candidate History page.
        query = query.filter(TrackerEntry.candidate_id.isnot(None), func.coalesce(Candidate.availability_status, DEFAULT_AVAILABILITY) == availability)
    rows = query.order_by(TrackerEntry.updated_at.desc()).limit(MAX_ROWS).all()
    counts: Dict[str, int] = {key: 0 for key, _ in spec["stages"]}
    for entry, _ in rows:
        counts[entry.stage] = counts.get(entry.stage, 0) + 1
    return {
        "columns": [{"key": k, "label": label, "kind": col_kind} for k, label, col_kind in spec["columns"]],
        "stages": [{"key": key, "label": label, "count": counts.get(key, 0)} for key, label in spec["stages"]],
        "statuses": list(SUBMISSION_STATUSES) if kind == "submission" else [],
        "rows": [_serialize(entry, (avail or DEFAULT_AVAILABILITY) if entry.candidate_id else None) for entry, avail in rows],
    }


@router.post("/{kind}/entries", status_code=201)
def create_entry(kind: str, body: EntryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stage = _stage(kind, body.stage)
    typed = _clean(kind, body.data)
    prefill: Dict[str, str] = {}
    if body.candidate_id:
        cand = db.query(Candidate).filter(Candidate.id == body.candidate_id).first()
        if cand is None:
            raise HTTPException(status_code=404, detail="Candidate not found.")
        allowed = {key for key, _, _ in _kind(kind)["columns"]}
        # The candidate's upload time is not a source/submission date; the recruiter sets those.
        prefill = {k: str(v) for k, v in _auto(cand, None, None).items() if k in allowed and k != "source_date"}
    if kind == "submission":
        typed.setdefault("client_submission_date", date.today().isoformat())
    entry = TrackerEntry(tracker=kind, stage=stage, candidate_id=body.candidate_id, data={**prefill, **typed}, created_by=user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    bump_data_epoch()
    return _serialize(entry, _availability(db, entry))


def _get_entry(db: Session, entry_id: str) -> TrackerEntry:
    entry = db.query(TrackerEntry).filter(TrackerEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Tracker row not found.")
    return entry


@router.patch("/entries/{entry_id}")
def update_entry(entry_id: str, body: EntryPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = _get_entry(db, entry_id)
    if body.stage is not None:
        entry.stage = _stage(entry.tracker, body.stage)
    if body.data is not None:
        merged = {**(entry.data or {}), **{k: ("" if v is None else v) for k, v in body.data.items()}}
        entry.data = _clean(entry.tracker, merged)  # an emptied field is dropped
    db.commit()
    db.refresh(entry)
    bump_data_epoch()
    return _serialize(entry, _availability(db, entry))


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_get_entry(db, entry_id))
    db.commit()
    bump_data_epoch()
