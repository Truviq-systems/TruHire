from fastapi import APIRouter, Depends

from backend.auth import get_current_user
from backend.config import settings
from backend.models import (
    AVAILABILITY_STATUSES, CANDIDATE_STATUSES, CLIENT_NAMES, DEFAULT_AVAILABILITY, DEFAULT_JD_STATUS, DEMAND_DETAIL_FIELDS, FULFILLED_JD_STATUSES,
    INACTIVE_JD_STATUSES, INGEST_FILE_OUTCOMES, INGEST_FILE_STATUS_WEIGHTS, INGEST_FINAL_FILE_STATUSES, INGEST_FINISHED_BATCH_STATUSES, INGEST_STAGES, INTERVIEW_KINDS,
    PROGRESSED_REQUIREMENT_STATUSES, RESUME_LINKED_JD_STATUSES, DEFAULT_REQUIREMENT_STATUS, JD_STATUSES, NOTICE_PERIOD_UNITS, EMAIL_STATUS_FAILED, EMAIL_STATUS_SENT, EMAIL_STATUS_SIMULATED,
    REQUIREMENT_STATUSES, ROLES, User,
)
from backend.routers.email import EMAIL_STATUS_PENDING
from backend.routers.tracker import tracker_kinds

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("")
def get_meta(user: User = Depends(get_current_user)):
    """Enums and limits the UI needs, read from the same constants the backend enforces."""
    return {
        "roles": list(ROLES),
        "jd_statuses": list(JD_STATUSES),
        "default_jd_status": DEFAULT_JD_STATUS,
        "resume_linked_jd_statuses": list(RESUME_LINKED_JD_STATUSES),
        "inactive_jd_statuses": list(INACTIVE_JD_STATUSES),
        "fulfilled_jd_statuses": list(FULFILLED_JD_STATUSES),
        "client_names": list(CLIENT_NAMES),
        "notice_period_units": list(NOTICE_PERIOD_UNITS),
        "requirement_statuses": list(REQUIREMENT_STATUSES),
        "default_requirement_status": DEFAULT_REQUIREMENT_STATUS,
        "progressed_requirement_statuses": list(PROGRESSED_REQUIREMENT_STATUSES),
        "availability_statuses": list(AVAILABILITY_STATUSES),
        "default_availability": DEFAULT_AVAILABILITY,
        "demand_detail_fields": list(DEMAND_DETAIL_FIELDS),
        "tracker_kinds": tracker_kinds(),
        "interview_kinds": [{"key": k, "title": t, "description": d} for k, t, d in INTERVIEW_KINDS],
        "candidate_statuses": list(CANDIDATE_STATUSES),
        "email_statuses": [EMAIL_STATUS_PENDING, EMAIL_STATUS_SENT, EMAIL_STATUS_SIMULATED, EMAIL_STATUS_FAILED],
        "page_sizes": {"history": settings.HISTORY_PAGE_SIZE, "audit": settings.AUDIT_PAGE_SIZE},
        "search": {"default_top_n": settings.SEARCH_DEFAULT_TOP_N, "max_top_n": settings.SEARCH_MAX_TOP_N},
        "analytics": {"timeline_weeks": settings.ANALYTICS_TIMELINE_WEEKS, "attention_limit": settings.ANALYTICS_ATTENTION_LIMIT},
        "ingestion": {
            "stages": [{"key": k, "label": label} for k, label in INGEST_STAGES],
            "file_status_weights": INGEST_FILE_STATUS_WEIGHTS,
            "final_file_statuses": list(INGEST_FINAL_FILE_STATUSES),
            "file_outcomes": {outcome: list(statuses) for outcome, statuses in INGEST_FILE_OUTCOMES.items()},
            "finished_batch_statuses": list(INGEST_FINISHED_BATCH_STATUSES),
            "slow_after_seconds": settings.INGEST_SLOW_AFTER_SECONDS,
        },
        "comment_max_chars": settings.COMMENT_MAX_CHARS,
        "accepted_jd_file_types": settings.jd_accepted_extensions,
    }
