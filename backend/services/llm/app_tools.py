"""The assistant's tools for the rest of TruHire beyond demands and candidate search: the Pipeline and
Submission trackers, analytics, the account, users, comments, email and ingestion history, the audit log,
and edits to demands and candidates.

Same contract as agent.py: READ tools run at once and feed their result back to the model; WRITE tools
only PROPOSE a change (a pending action the user confirms in the chat) and run through EXECUTORS when
confirmed, calling the very functions the REST endpoints use, so validation, history and cache
invalidation are identical to making the change in the page.

Deliberately not available: deleting candidates, demands, users or comments, uploading files, sending
email and changing roles. Those stay in their pages.
"""
import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import ValidationError

from backend.models import (AVAILABILITY_STATUSES, CANDIDATE_STATUSES, DEMAND_DETAIL_FIELDS, FULFILLED_JD_STATUSES, INACTIVE_JD_STATUSES,
                            JD_STATUSES, NOTICE_PERIOD_UNITS, ROLE_ADMIN, User)
from backend.routers.tracker import KIND_KEYS
from backend.services.llm.agent import Outcome, _STR, _demand_label, _one_candidate, _one_demand, _pending, _tool

MAX_ROWS = 25
TRACKERS = KIND_KEYS
DEMAND_FIELDS = ("title", *DEMAND_DETAIL_FIELDS)
_OBJ = {"type": "object"}
_TRACKER = {"type": "string", "enum": list(TRACKERS)}

TOOLS: List[dict] = [
    # ---- read
    _tool("list_tracker_rows", "Rows of the Pipeline tracker (stages L2 Sheets, L1 Sheets, Interview to be Scheduled, Interview Reject, Screen Reject) "
          "or the Submission tracker. Returns each row's id (needed to change it), stage and column values, plus the stages and columns that exist.",
          {"tracker": _TRACKER, "stage": {**_STR, "description": "stage key or label"}, "query": {**_STR, "description": "text to find in any column"},
           "availability": {"type": "string", "enum": list(AVAILABILITY_STATUSES)}, "limit": {"type": "integer"}}, ["tracker"]),
    _tool("get_analytics", "The Analytics page: positions, fulfilment, candidates per stage, requirements, top skills, score and experience distributions.",
          {"demand": {**_STR, "description": "optional demand to scope the match scores"}}),
    _tool("get_account", "The signed-in user's own account: name, email and role.", {}),
    _tool("list_users", "All users with their role. Admins only.", {}),
    _tool("get_candidate_profile", "A candidate's saved profile: contact, skills, education, location, notice period, status and availability.",
          {"candidate": {**_STR, "description": "name, email, phone, company or TRU-CN id"}}, ["candidate"]),
    _tool("get_comments", "Review comments left on a candidate, optionally for one demand.", {"candidate": _STR, "demand": _STR}, ["candidate"]),
    _tool("get_email_history", "Emails drafted or sent: per demand when `demand` is given, otherwise a summary of demands with email activity.", {"demand": _STR}),
    _tool("get_ingestion_history", "Recent resume upload batches with their counts of parsed, failed and duplicate files.", {"limit": {"type": "integer"}}),
    _tool("get_ai_audit", "Recent AI audit events (prompts, providers, status). Admins only.",
          {"feature": _STR, "status": _STR, "limit": {"type": "integer"}}),
    # ---- write (proposed, confirmed in the chat)
    _tool("add_tracker_row", "PROPOSE adding a row to a tracker. Pass `candidate` to prefill from an ingested candidate. The user must confirm.",
          {"tracker": _TRACKER, "stage": _STR, "candidate": _STR,
           "fields": {**_OBJ, "description": "column key to value, e.g. {\"primary_skill\": \"Java\", \"recruiter\": \"Asha\"}"}}, ["tracker"]),
    _tool("update_tracker_row", "PROPOSE changing a tracker row's values and/or moving it to another stage. Use the row id from list_tracker_rows.",
          {"row_id": _STR, "stage": _STR, "fields": {**_OBJ, "description": "column key to new value; \"\" clears a value"}}, ["row_id"]),
    _tool("delete_tracker_row", "PROPOSE deleting one tracker row. The user must confirm.", {"row_id": _STR}, ["row_id"]),
    _tool("update_demand", "PROPOSE editing a demand's details. Allowed fields: " + ", ".join(DEMAND_FIELDS) + ".",
          {"demand": _STR, "fields": _OBJ}, ["demand", "fields"]),
    _tool("set_demand_status", "PROPOSE changing a demand's lifecycle status. Mapped and Fulfilled name the candidates it was filled with; Cancelled takes a reason.",
          {"demand": _STR, "status": {"type": "string", "enum": list(JD_STATUSES)}, "reason": _STR, "candidates": {"type": "array", "items": _STR}},
          ["demand", "status"]),
    _tool("set_candidate_status", "PROPOSE changing a candidate's overall recruitment status.",
          {"candidate": _STR, "status": {"type": "string", "enum": list(CANDIDATE_STATUSES)}}, ["candidate", "status"]),
    _tool("set_notice_period", "PROPOSE setting a candidate's notice period; omit value and unit to clear it.",
          {"candidate": _STR, "value": {"type": "number"}, "unit": {"type": "string", "enum": list(NOTICE_PERIOD_UNITS)}}, ["candidate"]),
    _tool("add_comment", "PROPOSE adding a review comment on a candidate, optionally for one demand and with a 1-5 rating.",
          {"candidate": _STR, "body": _STR, "demand": _STR, "rating": {"type": "integer"}}, ["candidate", "body"]),
    _tool("update_account_name", "PROPOSE changing the signed-in user's display name.", {"name": _STR}, ["name"]),
]
WRITE_TOOLS = {"add_tracker_row", "update_tracker_row", "delete_tracker_row", "update_demand", "set_demand_status",
               "set_candidate_status", "set_notice_period", "add_comment", "update_account_name"}


def _fail(message: str) -> Outcome:
    return Outcome({"error": message})


def _admin_only(ctx) -> Optional[Outcome]:
    return None if (ctx.user.role or "") == ROLE_ADMIN else _fail("That needs an admin account.")


def _as_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, str):  # some models send the object as a JSON string
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def _stage_key(kind: str, wanted: Optional[str]) -> Optional[str]:
    from backend.routers import tracker
    if not wanted:
        return None
    needle = str(wanted).strip().casefold()
    for key, label in tracker._kind(kind)["stages"]:
        if needle in (key.casefold(), label.casefold()):
            return key
    return None


# ----------------------------------------------------------------------------- read tools

def _t_list_tracker_rows(ctx, args) -> Outcome:
    from backend.routers import tracker
    kind = args.get("tracker")
    if kind not in TRACKERS:
        return _fail("tracker must be one of: " + ", ".join(TRACKERS) + ".")
    sheet = tracker.sheet(kind, args.get("availability"), ctx.db, ctx.user)
    stage = _stage_key(kind, args.get("stage"))
    if args.get("stage") and stage is None:
        return _fail("Unknown stage. Stages: " + ", ".join(s["label"] for s in sheet["stages"]) + ".")
    needle = str(args.get("query") or "").strip().casefold()
    rows = [r for r in sheet["rows"] if (not stage or r["stage"] == stage)
            and (not needle or any(needle in str(v).casefold() for v in r["data"].values()))]
    limit = max(1, min(int(args.get("limit") or MAX_ROWS), MAX_ROWS))
    return Outcome({"tracker": kind, "stages": sheet["stages"], "total_matching": len(rows), "statuses": sheet["statuses"],
                    "columns": [c["key"] for c in sheet["columns"]],
                    "rows": [{"id": r["id"], "stage": r["stage"], "availability": r["availability"], **r["data"]} for r in rows[:limit]]})


def _t_get_analytics(ctx, args) -> Outcome:
    from backend.routers import analytics
    position_id = None
    if args.get("demand"):
        pos, problem = _one_demand(ctx.db, args.get("demand"))
        if problem:
            return problem
        position_id = pos.id
    overview = analytics._compute_overview(position_id, ctx.db)
    rows = analytics.get_requirements_report(ctx.db, ctx.user)["requirements"]
    live = [r for r in rows if r["status"] not in INACTIVE_JD_STATUSES]
    positions = sum(r["no_of_positions"] for r in live)
    fulfilled = sum(r["no_of_positions"] for r in live if r["status"] in FULFILLED_JD_STATUSES)
    stages: Dict[str, int] = {}
    for r in live:
        for k, v in r["stages"].items():
            stages[k] = stages.get(k, 0) + v
    return Outcome({"summary": overview["summary"], "positions": positions, "fulfilled_positions": fulfilled,
                    "percent_fulfilled": round(100 * fulfilled / positions) if positions else 0, "candidates_by_review_stage": stages,
                    "status_funnel": overview["status_funnel"], "top_skills": overview["top_skills"][:10],
                    "experience_distribution": overview["experience_distribution"], "match_score_distribution": overview["match_score_distribution"],
                    "scoped_to": position_id})


def _t_get_account(ctx, args) -> Outcome:
    return Outcome({"name": ctx.user.name, "email": ctx.user.email, "role": ctx.user.role or "recruiter"})


def _t_list_users(ctx, args) -> Outcome:
    if (blocked := _admin_only(ctx)):
        return blocked
    users = ctx.db.query(User).order_by(User.name).all()
    return Outcome({"count": len(users), "users": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role or "recruiter"} for u in users]})


def _t_get_candidate_profile(ctx, args) -> Outcome:
    cand, problem = _one_candidate(ctx.db, args.get("candidate"))
    if problem:
        return problem
    notice = f"{cand.notice_period_value:g} {cand.notice_period_unit}" if cand.notice_period_value is not None and cand.notice_period_unit else None
    profile = {"id": cand.id, "display_id": cand.display_id, "name": cand.candidate_name, "email": cand.email, "phone": cand.phone,
               "current_company": cand.current_company, "location": cand.location, "years_experience": cand.years_experience,
               "education": cand.education, "skills": cand.extracted_skills or [], "notice_period": notice, "status": cand.status,
               "availability": cand.availability_status or "Active"}
    ctx.recent["candidate"] = f"{cand.display_id} {cand.candidate_name}"
    return Outcome({k: v for k, v in profile.items() if v not in (None, "", [])})


def _t_get_comments(ctx, args) -> Outcome:
    from backend.routers import reviews
    cand, problem = _one_candidate(ctx.db, args.get("candidate"))
    if problem:
        return problem
    position_id = None
    if args.get("demand"):
        pos, problem = _one_demand(ctx.db, args.get("demand"))
        if problem:
            return problem
        position_id = pos.id
    comments = reviews.list_comments(cand.id, position_id, ctx.db, ctx.user)
    return Outcome({"candidate": cand.candidate_name, "count": len(comments), "comments": comments[:20]})


def _t_get_email_history(ctx, args) -> Outcome:
    from backend.routers import email
    if args.get("demand"):
        pos, problem = _one_demand(ctx.db, args.get("demand"))
        if problem:
            return problem
        return Outcome({"demand": _demand_label(pos), "records": email.email_history_for_role(pos.id, ctx.db, ctx.user)})
    return Outcome({"demands_with_email_activity": email.email_history_roles(ctx.db, ctx.user)})


def _t_get_ingestion_history(ctx, args) -> Outcome:
    from backend.routers import ingestion
    batches = ingestion.list_batches(max(1, min(int(args.get("limit") or 10), 25)), 0, ctx.db, ctx.user)
    keep = ("id", "status", "stage", "created_at", "total_files", "processed_count", "failed_count", "duplicate_count")
    return Outcome({"total": batches["total"], "batches": [{k: getattr(b, k, None) for k in keep} for b in batches["batches"]]})


def _t_get_ai_audit(ctx, args) -> Outcome:
    from backend.routers import ai_audit
    if (blocked := _admin_only(ctx)):
        return blocked
    result = ai_audit.list_ai_audit_events(feature=args.get("feature"), status=args.get("status"), provider=None, user_id=None, trace_id=None,
                                           date_from=None, date_to=None, limit=max(1, min(int(args.get("limit") or 10), 25)), offset=0,
                                           db=ctx.db, admin=ctx.user)
    return Outcome({"total": result["total"], "events": [{k: e.get(k) for k in ("created_at", "feature", "provider", "status", "error")} for e in result["items"]]})


# ----------------------------------------------------------------------------- write tools (propose)

def _checked_fields(kind: str, fields: Dict[str, Any], clearing: bool = False) -> Optional[Outcome]:
    from backend.routers import tracker
    try:
        tracker._clean(kind, {k: ("" if clearing and v is None else v) for k, v in fields.items()})
    except HTTPException as exc:
        return _fail(str(exc.detail))
    return None


def _t_add_tracker_row(ctx, args) -> Outcome:
    kind = args.get("tracker")
    if kind not in TRACKERS:
        return _fail("tracker must be one of: " + ", ".join(TRACKERS) + ".")
    stage = _stage_key(kind, args.get("stage")) if args.get("stage") else None
    if args.get("stage") and stage is None:
        return _fail("Unknown stage for that tracker.")
    fields = _as_object(args.get("fields"))
    if (bad := _checked_fields(kind, fields)):
        return bad
    candidate_id, who = None, ""
    if args.get("candidate"):
        cand, problem = _one_candidate(ctx.db, args.get("candidate"))
        if problem:
            return problem
        candidate_id, who = cand.id, f" for {cand.candidate_name} ({cand.display_id})"
    name = fields.get("candidate_name") or ""
    return _pending(ctx, "add_tracker_row", {"tracker": kind, "stage": stage, "candidate_id": candidate_id, "fields": fields},
                    f"add a row{who or (f' for {name}' if name else '')} to the {kind} tracker" + (f" ({args['stage']})" if stage else ""))


def _tracker_entry(ctx, row_id: Optional[str]):
    from backend.routers import tracker
    try:
        return tracker._get_entry(ctx.db, str(row_id or "")), None
    except HTTPException:
        return None, _fail("No tracker row has that id. Call list_tracker_rows to get the id.")


def _t_update_tracker_row(ctx, args) -> Outcome:
    entry, problem = _tracker_entry(ctx, args.get("row_id"))
    if problem:
        return problem
    fields = _as_object(args.get("fields"))
    stage = _stage_key(entry.tracker, args.get("stage")) if args.get("stage") else None
    if args.get("stage") and stage is None:
        return _fail("Unknown stage for that tracker.")
    if not fields and not stage:
        return _fail("Nothing to change: give fields and/or a stage.")
    if (bad := _checked_fields(entry.tracker, {**(entry.data or {}), **fields}, clearing=True)):
        return bad
    name = (entry.data or {}).get("candidate_name") or "this row"
    parts = ([f"set {', '.join(f'{k} to {v!r}' if v != '' else f'clear {k}' for k, v in fields.items())}"] if fields else []) + ([f"move it to {args['stage']}"] if stage else [])
    return _pending(ctx, "update_tracker_row", {"row_id": entry.id, "stage": stage, "fields": fields},
                    f"in the {entry.tracker} tracker, for {name}: " + " and ".join(parts))


def _t_delete_tracker_row(ctx, args) -> Outcome:
    entry, problem = _tracker_entry(ctx, args.get("row_id"))
    if problem:
        return problem
    name = (entry.data or {}).get("candidate_name") or "an unnamed row"
    return _pending(ctx, "delete_tracker_row", {"row_id": entry.id}, f"delete {name} from the {entry.tracker} tracker")


def _demand_request(fields: Dict[str, Any]):
    from backend.routers.job_descriptions import PositionUpdateRequest
    return PositionUpdateRequest(**fields)


def _t_update_demand(ctx, args) -> Outcome:
    pos, problem = _one_demand(ctx.db, args.get("demand"))
    if problem:
        return problem
    fields = _as_object(args.get("fields"))
    unknown = sorted(set(fields) - set(DEMAND_FIELDS))
    if unknown or not fields:
        return _fail("Allowed fields: " + ", ".join(DEMAND_FIELDS) + (f". Not allowed: {', '.join(unknown)}." if unknown else "."))
    try:
        _demand_request(fields)
    except ValidationError as exc:
        return _fail("Those values are not valid: " + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())[:300])
    return _pending(ctx, "update_demand", {"position_id": pos.id, "fields": fields},
                    f"update {_demand_label(pos)}: " + ", ".join(f"{k} to {v!r}" for k, v in fields.items()))


def _t_set_demand_status(ctx, args) -> Outcome:
    pos, problem = _one_demand(ctx.db, args.get("demand"))
    if problem:
        return problem
    status = next((s for s in JD_STATUSES if s.casefold() == str(args.get("status") or "").strip().casefold()), None)
    if not status:
        return _fail("Status must be one of: " + ", ".join(JD_STATUSES) + ".")
    ids = []
    for ref in args.get("candidates") or []:
        cand, problem = _one_candidate(ctx.db, ref)
        if problem:
            return problem
        ids.append(cand.id)
    return _pending(ctx, "set_demand_status", {"position_id": pos.id, "status": status, "reason": args.get("reason"), "candidate_ids": ids or None},
                    f"set {_demand_label(pos)} to {status}" + (f" (reason: {args['reason']})" if args.get("reason") else ""))


def _t_set_candidate_status(ctx, args) -> Outcome:
    cand, problem = _one_candidate(ctx.db, args.get("candidate"))
    if problem:
        return problem
    status = next((s for s in CANDIDATE_STATUSES if s.casefold() == str(args.get("status") or "").strip().casefold()), None)
    if not status:
        return _fail("Status must be one of: " + ", ".join(CANDIDATE_STATUSES) + ".")
    return _pending(ctx, "set_candidate_status", {"candidate_id": cand.id, "status": status},
                    f"set {cand.candidate_name} ({cand.display_id}) to {status}")


def _t_set_notice_period(ctx, args) -> Outcome:
    from backend.routers.candidates import NoticePeriodRequest
    cand, problem = _one_candidate(ctx.db, args.get("candidate"))
    if problem:
        return problem
    unit = next((u for u in NOTICE_PERIOD_UNITS if u.casefold() == str(args.get("unit") or "").strip().casefold()), None) if args.get("unit") else None
    try:
        request = NoticePeriodRequest(value=args.get("value"), unit=unit)
        request.check()   # both fields or neither, and the 2-year cap: the same rule the page applies
    except ValidationError as exc:
        return _fail("Not a valid notice period: " + exc.errors()[0]["msg"])
    except HTTPException as exc:
        return _fail(str(exc.detail))
    what = f"{request.value:g} {request.unit}" if request.value is not None else "no notice period (cleared)"
    return _pending(ctx, "set_notice_period", {"candidate_id": cand.id, "value": request.value, "unit": request.unit},
                    f"set the notice period of {cand.candidate_name} ({cand.display_id}) to {what}")


def _t_add_comment(ctx, args) -> Outcome:
    from backend.routers.reviews import CommentRequest
    cand, problem = _one_candidate(ctx.db, args.get("candidate"))
    if problem:
        return problem
    position_id = None
    if args.get("demand"):
        pos, problem = _one_demand(ctx.db, args.get("demand"))
        if problem:
            return problem
        position_id = pos.id
    try:
        CommentRequest(body=str(args.get("body") or ""), rating=args.get("rating"), position_id=position_id)
    except ValidationError as exc:
        return _fail("Not a valid comment: " + exc.errors()[0]["msg"])
    return _pending(ctx, "add_comment", {"candidate_id": cand.id, "body": args["body"], "rating": args.get("rating"), "position_id": position_id},
                    f"add this comment on {cand.candidate_name} ({cand.display_id}): {str(args['body'])[:120]!r}")


def _t_update_account_name(ctx, args) -> Outcome:
    name = " ".join(str(args.get("name") or "").split())
    if not 1 <= len(name) <= 100:
        return _fail("The name must be 1 to 100 characters.")
    return _pending(ctx, "update_account_name", {"name": name}, f"change your display name from {ctx.user.name!r} to {name!r}")


IMPLEMENTATIONS = {name[3:]: fn for name, fn in list(globals().items()) if name.startswith("_t_")}


# ----------------------------------------------------------------------------- executors (after the user confirms)

def _x_add_tracker_row(db, user, a):
    from backend.routers import tracker
    tracker.create_entry(a["tracker"], tracker.EntryIn(stage=a.get("stage"), candidate_id=a.get("candidate_id"), data=a.get("fields") or {}), db, user)


def _x_update_tracker_row(db, user, a):
    from backend.routers import tracker
    tracker.update_entry(a["row_id"], tracker.EntryPatch(stage=a.get("stage"), data=a.get("fields") or None), db, user)


def _x_delete_tracker_row(db, user, a):
    from backend.routers import tracker
    tracker.delete_entry(a["row_id"], db, user)


def _x_update_demand(db, user, a):
    from backend.routers.job_descriptions import update_jd
    update_jd(a["position_id"], _demand_request(a["fields"]), db, user)


def _x_set_demand_status(db, user, a):
    from backend.routers.job_descriptions import set_jd_status
    set_jd_status(a["position_id"], a["status"], db, user, a.get("reason"), a.get("candidate_ids"))


def _x_set_candidate_status(db, user, a):
    from backend.routers.candidates import CandidateStatusUpdateRequest, update_candidate_status
    update_candidate_status(a["candidate_id"], CandidateStatusUpdateRequest(status=a["status"]), db, user)


def _x_set_notice_period(db, user, a):
    from backend.routers.candidates import NoticePeriodRequest, update_notice_period
    update_notice_period(a["candidate_id"], NoticePeriodRequest(value=a.get("value"), unit=a.get("unit")), db, user)


def _x_add_comment(db, user, a):
    from backend.routers.reviews import CommentRequest, add_comment
    add_comment(a["candidate_id"], CommentRequest(body=a["body"], rating=a.get("rating"), position_id=a.get("position_id")), db, user)


def _x_update_account_name(db, user, a):
    from backend.routers.auth import UserNameRequest, update_me
    update_me(UserNameRequest(name=a["name"]), db, user)


EXECUTORS = {name[3:]: fn for name, fn in list(globals().items()) if name.startswith("_x_")}
