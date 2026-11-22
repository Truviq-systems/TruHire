import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Date, ForeignKey, JSON, UniqueConstraint, Index, Boolean, func
from sqlalchemy.orm import relationship
from backend.database import Base


def generate_uuid(): return str(uuid.uuid4())


ROLE_ADMIN = "admin"
ROLE_RECRUITER = "recruiter"
ROLES = (ROLE_ADMIN, ROLE_RECRUITER)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=True, default=ROLE_RECRUITER)  # NULL on pre-roles rows; treated as recruiter
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    positions = relationship("Position", back_populates="creator")
    batches = relationship("IngestionBatch", back_populates="creator")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


DEFAULT_DEMAND_NAMES = ("Java", "GenAI", "Camunda", "Pega", "Others")  # the five fixed categories
OTHERS_DEMAND_NAME = "Others"


def canonical_demand_id(name: str) -> str:
    return f"default-demand-{name.lower()}"


def get_demand_display_id(demand_id: Optional[str]) -> Optional[str]:
    for index, name in enumerate(DEFAULT_DEMAND_NAMES, start=1):
        if demand_id == canonical_demand_id(name):
            return f"TRU-DM-{index:02d}"
    return None


class Demand(Base):
    """A hiring demand that groups related requirements (Positions). Purely organisational: matching,
    scoring and candidate statuses stay per-Position, and a Position may exist without a Demand."""
    __tablename__ = "demands"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)  # NULL for system-seeded default demands
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    positions = relationship("Position", back_populates="demand", passive_deletes=True)


JD_STATUSES = ("Open", "Cancelled", "Fulfilled", "Mapped")  # lifecycle of a JD (Position)
# "Map" was renamed and "Closed" was removed (those demands are Cancelled); old rows and clients are still understood.
LEGACY_JD_STATUS_ALIASES = {"Map": "Mapped", "Closed": "Cancelled"}
INACTIVE_JD_STATUSES = ("Cancelled",)  # kept on record but not counted on demand folders
FULFILLED_JD_STATUSES = ("Fulfilled",)  # the demand's positions are filled: reports count them as done
RESUME_LINKED_JD_STATUSES = ("Mapped", "Fulfilled")  # statuses that name the resume(s) the demand was filled with
MAX_CANCELLATION_REASON_CHARS = 1000
CLIENT_NAMES = ("Cretera", "Infosys", "Coforge", "Aaseya", "NTT Data", "Utsuk")  # the clients a demand can belong to
DEFAULT_JD_STATUS = "Open"


class Position(Base):
    __tablename__ = "positions"
    id = Column(String, primary_key=True, default=generate_uuid)
    display_id = Column(String, unique=True, index=True, nullable=True)
    title = Column(String, nullable=False, index=True)
    jd_text = Column(Text, nullable=False)
    jd_summary = Column(Text, nullable=True)
    jd_version = Column(Integer, default=1, nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    file_url = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    # Location / role / work mode read from the JD, cached per jd_version so the LLM runs once per edit.
    search_filters = Column(JSON, nullable=True)
    # Optional grouping; NULL = standalone requirement. Deleting a Demand never deletes its positions.
    demand_id = Column(String, ForeignKey("demands.id", ondelete="SET NULL"), nullable=True, index=True)
    # JD details entered by the recruiter; NULL = not stated. status NULL on pre-status rows is treated as Open.
    status = Column(String, nullable=True, default=DEFAULT_JD_STATUS, index=True)
    role = Column(String, nullable=True)
    experience_years = Column(Float, nullable=True)  # minimum years required
    experience_max_years = Column(Float, nullable=True)
    no_of_positions = Column(Integer, nullable=True)  # how many hires the demand is for; NULL on demands made before this field
    locations = Column(JSON, nullable=True)  # list of places; `location` below mirrors it as "; "-joined text
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    location = Column(String, nullable=True)
    client_name = Column(String, nullable=True)  # optional; NULL = not stated
    demand_owner = Column(String, nullable=True)  # free-text owner name shown on demand cards; NULL = not stated
    current_status = Column(Text, nullable=True)  # free-text "where the demand stands"; separate from the lifecycle `status`
    updated_at = Column(DateTime, nullable=True)  # last modified; NULL = never changed since creation
    updated_by = Column(String, nullable=True)  # user id of the last modifier; NULL = unknown / never changed
    cancellation_reason = Column(Text, nullable=True)  # only while status is Cancelled
    mapped_candidate_ids = Column(JSON, nullable=True)  # candidate ids the demand is Mapped / Fulfilled with
    creator = relationship("User", back_populates="positions")
    demand = relationship("Demand", back_populates="positions")
    matches = relationship("CandidateMatch", back_populates="position", cascade="all, delete-orphan")
    __table_args__ = (Index("idx_position_client_name_normalized", func.lower(func.trim(client_name))),)


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"
    id = Column(String, primary_key=True, default=generate_uuid)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_files = Column(Integer, default=0)
    processed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    status = Column(String, default="processing")
    error_log = Column(JSON, default=list)
    # Live progress: overall stage (queued/reading/embedding/indexing/done) and one entry per
    # file {filename, status, detail} with status queued/extracting/analyzing/embedding/indexing/indexed/duplicate/failed.
    stage = Column(String, default="queued")
    file_status = Column(JSON, default=list)
    # Set by POST /batches/{id}/cancel; process_batch checks it between files and before indexing.
    cancel_requested = Column(Boolean, default=False, nullable=False, server_default="false")
    # Heartbeat: written on every progress update. A processing batch that stops updating belongs to a dead task.
    updated_at = Column(DateTime, nullable=True)
    creator = relationship("User", back_populates="batches")
    candidates = relationship("Candidate", back_populates="batch")


class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String, primary_key=True, default=generate_uuid)
    display_id = Column(String, unique=True, index=True, nullable=True)
    position_id = Column(String, ForeignKey("positions.id"), nullable=True)
    resume_file_url = Column(String, nullable=True)
    candidate_name = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    email_norm = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    phone_norm = Column(String, nullable=True, index=True)
    current_company = Column(String, nullable=True, index=True)
    extracted_skills = Column(JSON, default=list)
    years_experience = Column(Float, default=0.0)
    education = Column(Text, nullable=True)
    # Extracted only when the resume states them; NULL/[] means unknown, never a guess.
    location = Column(String, nullable=True)
    location_norm = Column(String, nullable=True)   # '|bengaluru|karnataka|india|' (see retrieval/filters.py)
    job_titles = Column(JSON, default=list)         # most recent first
    title_norms = Column(String, nullable=True)
    resume_text = Column(Text, nullable=True)
    pii_detected = Column(JSON, default=dict)
    status = Column(String, default="New", index=True)
    status_updated_by = Column(String, nullable=True)
    status_updated_at = Column(DateTime, nullable=True)
    # Global talent availability is independent of per-requirement hiring stage.
    availability_status = Column(String, nullable=True, default="Active", index=True)
    availability_updated_by = Column(String, nullable=True)
    availability_updated_at = Column(DateTime, nullable=True)
    # Notice period as stated by the recruiter: a non-negative number plus a unit (see NOTICE_PERIOD_UNITS).
    notice_period_value = Column(Float, nullable=True)
    notice_period_unit = Column(String, nullable=True)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ingestion_batch_id = Column(String, ForeignKey("ingestion_batches.id"), nullable=True)
    file_hash = Column(String, nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    opensearch_doc_id = Column(String, nullable=True)
    qdrant_point_id = Column(String, nullable=True)
    batch = relationship("IngestionBatch", back_populates="candidates")
    matches = relationship("CandidateMatch", back_populates="candidate", cascade="all, delete-orphan")


class CandidateMatch(Base):
    __tablename__ = "candidate_matches"
    id = Column(String, primary_key=True, default=generate_uuid)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    position_id = Column(String, ForeignKey("positions.id"), nullable=False)
    match_score = Column(Float, nullable=False, index=True)
    score_breakdown = Column(JSON, default=dict)
    llm_summary = Column(Text, nullable=True)
    cited_quote = Column(Text, nullable=True)
    cited_section = Column(Text, nullable=True)
    jd_version = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    candidate = relationship("Candidate", back_populates="matches")
    position = relationship("Position", back_populates="matches")
    __table_args__ = (UniqueConstraint("candidate_id", "position_id", name="uq_candidate_position"), Index("idx_candidate_match_score", "position_id", "match_score"))


class SearchState(Base):
    __tablename__ = "search_states"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    query = Column(Text, default="", nullable=False)
    filter_skills = Column(JSON, default=list)
    min_experience = Column(Float, nullable=True)
    location = Column(String, nullable=True)
    role = Column(String, nullable=True)
    position_id = Column(String, ForeignKey("positions.id", ondelete="SET NULL"), nullable=True, index=True)
    client_name = Column(String, nullable=True)
    client_groups = Column(JSON, default=list)
    top_n = Column(Integer, default=20, nullable=False)
    results = Column(JSON, default=list)
    total_matches = Column(Integer, default=0, nullable=False)
    retrieval = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))



class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=True, index=True)
    position_id = Column(String, ForeignKey("positions.id"), nullable=True, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at")
    demand_sessions = relationship("AssistantDemandSession", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    message_data = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    conversation = relationship("Conversation", back_populates="messages")


DEMAND_SESSION_ACTIVE = ("choose_mode", "collecting", "review", "creating")


class AssistantDemandSession(Base):
    """One guided "create a demand" workflow inside an assistant conversation. The server owns the state (mode, current
    field, collected values); the chat model never decides which field comes next. Scoped to the user who started it."""
    __tablename__ = "assistant_demand_sessions"
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="choose_mode")  # choose_mode | collecting | review | creating | created | cancelled
    input_mode = Column(String, nullable=True)  # all_fields | step_by_step; NULL until chosen
    current_field = Column(String, nullable=True)
    values = Column(JSON, nullable=False, default=dict)  # validated values by API field name
    sources = Column(JSON, nullable=False, default=dict)  # field -> document | user | skipped
    errors = Column(JSON, nullable=False, default=dict)  # field -> message from the last failed answer
    source_document = Column(JSON, nullable=True)  # {filename, file_url, notes}
    created_position_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    conversation = relationship("Conversation", back_populates="demand_sessions")


CANDIDATE_STATUSES = ("New", "Shortlisted", "Interviewed", "Rejected")
REQUIREMENT_STATUSES = ("New", "Mapped", "Shortlisted", "Interviewed", "Rejected")  # per-requirement review stages
PROGRESSED_REQUIREMENT_STATUSES = ("Shortlisted", "Interviewed")  # stages that mean a candidate is moving forward (reports)
AVAILABILITY_STATUSES = ("Active", "Not Active")  # a candidate's global availability, independent of any requirement
DEFAULT_AVAILABILITY = AVAILABILITY_STATUSES[0]
# The Interviews section: (key, title, description). The workflow behind each is defined later.
INTERVIEW_KINDS = (
    ("internal", "Internal Interview", "Interviews held by the TruHire panel before a candidate is submitted."),
    ("client", "Client Interview", "Interviews held by the client after a submission."),
)
# Ingestion progress: the overall stages, and each file's pipeline state with its weight (0-1) on the progress bar.
INGEST_STAGES = (("reading", "Reading & AI analysis"), ("embedding", "Embedding"), ("indexing", "Indexing"), ("done", "Done"))
INGEST_FILE_STATUS_WEIGHTS = {"queued": 0, "extracting": 0.15, "analyzing": 0.4, "parsed": 0.55, "embedding": 0.7, "indexing": 0.85,
                              "indexed": 1, "updated": 1, "duplicate": 1, "skipped": 1, "failed": 1}
INGEST_FINAL_FILE_STATUSES = tuple(k for k, w in INGEST_FILE_STATUS_WEIGHTS.items() if w == 1)
INGEST_FINISHED_BATCH_STATUSES = ("completed", "failed", "cancelled")
# Which per-file states the progress card counts as processed, duplicate or failed.
INGEST_FILE_OUTCOMES = {"processed": ("indexed", "updated"), "duplicates": ("duplicate",), "failed": ("failed",)}
# Demand details a recruiter may edit (PositionUpdateRequest, the assistant's update_demand tool).
DEMAND_DETAIL_FIELDS = ("role", "location", "locations", "no_of_positions", "client_name", "demand_owner", "current_status",
                        "experience_years", "experience_max_years", "start_date", "end_date")
DEFAULT_REQUIREMENT_STATUS = "New"


class RequirementCandidateStatus(Base):
    """Recruiter review status of one candidate for one requirement; independent of Candidate.status."""
    __tablename__ = "requirement_candidate_statuses"
    id = Column(String, primary_key=True, default=generate_uuid)
    position_id = Column(String, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default=DEFAULT_REQUIREMENT_STATUS)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("position_id", "candidate_id", name="uq_requirement_candidate_status"),)


class TrackerEntry(Base):
    """One row of the Pipeline or Submission tracker. `stage` is the table the row sits in
    (pipeline stage, or the submission's client status); `data` holds the column values keyed
    by the column list in routers/tracker.py, so adding a column needs no migration."""
    # Not "tracker_entries": databases created by an earlier version already hold a table of that name
    # with a different shape (position_id/candidate_id required), which must be left untouched.
    __tablename__ = "tracker_rows"
    id = Column(String, primary_key=True, default=generate_uuid)
    tracker = Column(String, nullable=False, index=True)  # "pipeline" | "submission"
    stage = Column(String, nullable=False, index=True)
    candidate_id = Column(String, ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True)
    data = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CandidateAssignment(Base):
    """Which recruiter reviews a candidate for a requirement. One assignee per (requirement, candidate)."""
    __tablename__ = "candidate_assignments"
    id = Column(String, primary_key=True, default=generate_uuid)
    position_id = Column(String, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("position_id", "candidate_id", name="uq_candidate_assignment"),)


class CandidateComment(Base):
    """Shared review feedback on a candidate, optionally scoped to one requirement. Visible to every user."""
    __tablename__ = "candidate_comments"
    id = Column(String, primary_key=True, default=generate_uuid)
    candidate_id = Column(String, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    position_id = Column(String, ForeignKey("positions.id", ondelete="CASCADE"), nullable=True, index=True)
    author_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5, optional
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    edited_at = Column(DateTime, nullable=True)
    author = relationship("User", foreign_keys=[author_id])


class CandidateActivity(Base):
    """Privacy-conscious append-only timeline event; snapshots survive JD edits/deletion."""
    __tablename__ = "candidate_activities"
    id = Column(String, primary_key=True, default=generate_uuid)
    candidate_id = Column(String, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    actor_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_name = Column(String, nullable=True)
    position_id = Column(String, nullable=True)
    position_title = Column(String, nullable=True)
    client_name = Column(String, nullable=True)
    summary = Column(String(500), nullable=False)
    __table_args__ = (Index("idx_candidate_activity_history", "candidate_id", "occurred_at", "id"),)


EMAIL_STATUS_SENT = "sent"
EMAIL_STATUS_SIMULATED = "simulated"
EMAIL_STATUS_FAILED = "failed"


NOTICE_PERIOD_UNITS = ("Days", "Weeks", "Months")

HISTORY_CREATED, HISTORY_UPDATED, HISTORY_DELETED, HISTORY_STATUS_CHANGED = "created", "updated", "deleted", "status_changed"
HISTORY_ACTIONS = (HISTORY_CREATED, HISTORY_UPDATED, HISTORY_STATUS_CHANGED, HISTORY_DELETED)


class RequirementHistory(Base):
    """Append-only audit trail of demand/JD changes. Item and user fields are snapshots so entries
    survive deletion of the JD or the user; `changes` maps field -> {old, new} where applicable."""
    __tablename__ = "requirement_history"
    id = Column(String, primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    item_type = Column(String, nullable=False, default="jd")  # jd | demand
    source = Column(String, nullable=True)  # requirements UI | assistant | system
    item_id = Column(String, nullable=True, index=True)
    item_display_id = Column(String, nullable=True)
    item_title = Column(String, nullable=True)
    demand_id = Column(String, nullable=True, index=True)
    demand_display_id = Column(String, nullable=True)
    demand_name = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    user_name = Column(String, nullable=True)
    changes = Column(JSON, nullable=True)


class EmailRecord(Base):
    """Email history. Role/candidate fields are snapshots so history survives requirement or candidate deletion."""
    __tablename__ = "email_records"
    id = Column(String, primary_key=True, default=generate_uuid)
    position_id = Column(String, nullable=True, index=True)
    position_display_id = Column(String, nullable=True)
    position_title = Column(String, nullable=True)
    candidate_id = Column(String, nullable=True, index=True)
    candidate_display_id = Column(String, nullable=True)
    candidate_name = Column(String, nullable=True)
    recipient_email = Column(String, nullable=False)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String, nullable=False, index=True)
    delivery_mode = Column(String, nullable=False)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String, nullable=True, unique=True)
    sent_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AIAuditEvent(Base):
    """One row per AI model call, guardrail verdict or AI-driven screening decision.

    Prompts and outputs are stored only as PII-redacted, truncated previews plus a hash
    of the full prompt, so the trail is reviewable without becoming a second resume store.
    """
    __tablename__ = "ai_audit_events"
    id = Column(String, primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    trace_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    feature = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=True)
    status = Column(String, nullable=False, index=True)  # ok | error | blocked
    prompt_sha256 = Column(String, nullable=True)
    prompt_preview = Column(Text, nullable=True)
    output_preview = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)  # guardrail verdicts, screening reasons, etc.
    error = Column(Text, nullable=True)


class IdSequence(Base):
    """Monotonic counters for human-readable display IDs; numbers are never reused after deletion."""
    __tablename__ = "id_sequences"
    name = Column(String, primary_key=True)
    value = Column(Integer, nullable=False, default=0)


POSITION_ID_PREFIX = "DM-"
CANDIDATE_ID_PREFIX = "TRU-CN-"


def _max_existing_display_number(db, model, prefix: str) -> int:
    import re
    max_num = 0
    for (d_id,) in db.query(model.display_id).filter(model.display_id.like(f"{prefix}%")).all():
        m = re.fullmatch(rf"{re.escape(prefix)}(\d+)", d_id or "")
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num


def seed_id_sequence(db, model, prefix: str) -> None:
    """Create the counter row if missing, starting after the highest ID already issued."""
    row = db.query(IdSequence).filter(IdSequence.name == prefix).first()
    existing_max = _max_existing_display_number(db, model, prefix)
    if row is None:
        db.add(IdSequence(name=prefix, value=existing_max))
        db.flush()
    elif row.value < existing_max:
        row.value = existing_max


def _next_display_id(db, model, prefix: str) -> str:
    # The atomic UPDATE takes the write lock, so concurrent sessions cannot draw the same number.
    updated = db.query(IdSequence).filter(IdSequence.name == prefix).update(
        {IdSequence.value: IdSequence.value + 1}, synchronize_session=False
    )
    if not updated:
        seed_id_sequence(db, model, prefix)
        db.query(IdSequence).filter(IdSequence.name == prefix).update(
            {IdSequence.value: IdSequence.value + 1}, synchronize_session=False
        )
    value = db.query(IdSequence.value).filter(IdSequence.name == prefix).scalar()
    return f"{prefix}{value:04d}"


def get_next_position_display_id(db) -> str:
    return _next_display_id(db, Position, POSITION_ID_PREFIX)


def get_next_candidate_display_id(db) -> str:
    return _next_display_id(db, Candidate, CANDIDATE_ID_PREFIX)
