"""The assistant's reach across the rest of TruHire: trackers, analytics, account, comments and edits.

A fake model calls the real tools against the test database. Reads answer at once; every write only
PROPOSES a change, and confirming it runs the same endpoint code the page uses."""
import json

import pytest

from test_location_role_filters import env  # noqa: F401  (fixture agent_env builds on)
from test_assistant_agent import agent_env, ask, call, say, use, _named  # noqa: F401  (fixtures and helpers)
from backend.models import Candidate, Position, TrackerEntry
from backend.services.llm import agent, preflight


@pytest.fixture(autouse=True)
def _fresh_preflight(monkeypatch):
    monkeypatch.setattr(preflight, "get_cache", lambda key: None)   # never replay another test's answer
    monkeypatch.setattr(preflight, "set_cache", lambda *a, **k: None)
    monkeypatch.setattr(preflight, "_bucket", preflight.TokenBucket(burst=1000, refill_seconds=1))


def _call_with_name(tool, name):
    """The shared `call` helper takes the tool name as `name`, so a tool argument called `name` is built by hand."""
    return {"id": "n1", "type": "function", "function": {"name": tool, "arguments": json.dumps({"name": name})}}


def _confirm(env, body, approve=True):
    pending = body["pending"]
    return env["client"].post("/api/assistant/confirm", headers=env["headers"],
                              json={"conversation_id": body["conversation_id"], "pending_id": pending["id"], "approve": approve})


def _tool_result(model, round_index=1):
    return model.calls[round_index][-1]["content"]


def test_every_tool_is_registered_with_an_implementation_and_every_write_with_an_executor():
    names = [t["function"]["name"] for t in agent.TOOLS]
    assert len(names) == len(set(names))
    assert all(n in agent._IMPLEMENTATIONS for n in names)
    assert all(w in agent.EXECUTORS for w in agent.WRITE_TOOLS if w not in ("create_demand", "draft_email"))


def test_the_assistant_lists_tracker_rows_with_their_ids(agent_env):
    entry = agent_env["client"].post("/api/tracker/pipeline/entries", headers=agent_env["headers"],
                                     json={"stage": "l1_sheets", "data": {"candidate_name": "Zaid Khan", "primary_skill": "Pega"}}).json()
    model = agent_env["install"](use(call("list_tracker_rows", tracker="pipeline", stage="L1 Sheets", query="zaid")), say("One row."))

    ask(agent_env, "show the L1 sheets in the pipeline tracker for Zaid")

    result = _tool_result(model)
    assert entry["id"] in result and "Zaid Khan" in result and "L1 Sheets" in result


def test_adding_a_tracker_row_waits_for_confirmation_then_creates_it(agent_env):
    name = f"Meera Iyer {agent_env['tag']}"
    by_name = lambda: agent_env["db"].query(TrackerEntry).filter(TrackerEntry.data["candidate_name"].as_string() == name)  # noqa: E731
    agent_env["install"](use(call("add_tracker_row", tracker="submission", fields={"candidate_name": name, "primary_skill": "Camunda"})))
    body = ask(agent_env, f"add {name} to the submission tracker").json()
    try:
        assert body["action"] == "confirm_action"
        assert by_name().count() == 0  # proposed, not done
        assert _confirm(agent_env, body).json()["action"] == "action_done"
        row = by_name().one()
        assert row.tracker == "submission" and row.data["primary_skill"] == "Camunda"
    finally:
        by_name().delete(synchronize_session=False)
        agent_env["db"].commit()


def test_a_bad_tracker_column_is_refused_before_anything_is_proposed(agent_env):
    model = agent_env["install"](use(call("add_tracker_row", tracker="pipeline", fields={"not_a_column": "x"})), say("That column does not exist."))
    body = ask(agent_env, "add a row to the tracker with a made-up column").json()

    assert body["action"] != "confirm_action"
    assert "Unknown column" in _tool_result(model)


def test_moving_and_deleting_a_tracker_row_are_confirmed_changes(agent_env):
    entry = agent_env["client"].post("/api/tracker/pipeline/entries", headers=agent_env["headers"], json={"data": {"candidate_name": "Row To Move"}}).json()
    agent_env["install"](use(call("update_tracker_row", row_id=entry["id"], stage="Screen Reject", fields={"comments": "No show"})))
    body = ask(agent_env, "move Row To Move to screen reject").json()
    assert _confirm(agent_env, body).json()["action"] == "action_done"
    agent_env["db"].expire_all()
    row = agent_env["db"].get(TrackerEntry, entry["id"])
    assert row.stage == "screen_reject" and row.data["comments"] == "No show"

    agent_env["install"](use(call("delete_tracker_row", row_id=entry["id"])))
    body = ask(agent_env, "delete the Row To Move row from the tracker").json()
    assert body["action"] == "confirm_action"
    assert agent_env["db"].get(TrackerEntry, entry["id"]) is not None
    _confirm(agent_env, body)
    agent_env["db"].expire_all()
    assert agent_env["db"].get(TrackerEntry, entry["id"]) is None


def test_the_assistant_can_rename_the_signed_in_user_only_after_confirming(agent_env):
    original = agent_env["user"].name
    agent_env["install"](use(_call_with_name("update_account_name", "  Pavansai   R  ")))
    body = ask(agent_env, "change my name to Pavansai R").json()
    assert body["action"] == "confirm_action"
    assert agent_env["client"].get("/api/auth/me", headers=agent_env["headers"]).json()["name"] == original
    _confirm(agent_env, body)
    assert agent_env["client"].get("/api/auth/me", headers=agent_env["headers"]).json()["name"] == "Pavansai R"


def test_reading_the_account_and_analytics(agent_env):
    model = agent_env["install"](use(call("get_account"), call("get_analytics")), say("Here you go."))
    ask(agent_env, "show my account and the analytics report")
    results = model.calls[1]
    assert agent_env["user"].email in results[-2]["content"]
    assert "percent_fulfilled" in results[-1]["content"]


def test_a_recruiter_cannot_use_the_admin_tools(agent_env):
    model = agent_env["install"](use(call("list_users"), call("get_ai_audit")), say("Not allowed."))
    ask(agent_env, "list all users and show the audit log")
    assert "admin account" in model.calls[1][-2]["content"] and "admin account" in model.calls[1][-1]["content"]


def test_updating_a_demand_and_a_candidate_goes_through_confirmation(agent_env):
    position = agent_env["db"].get(Position, agent_env["make_jd"]())
    position.no_of_positions = 2
    agent_env["db"].commit()
    agent_env["install"](use(call("update_demand", demand=position.display_id, fields={"no_of_positions": 5, "demand_owner": "Asha"})))
    body = ask(agent_env, f"set {position.display_id} to 5 positions owned by Asha").json()
    assert body["action"] == "confirm_action"
    _confirm(agent_env, body)
    agent_env["db"].expire_all()
    refreshed = agent_env["db"].get(Position, position.id)
    assert refreshed.no_of_positions == 5 and refreshed.demand_owner == "Asha"

    candidate = _named(agent_env, f"Notice Tester{agent_env['tag']}")
    agent_env["install"](use(call("set_notice_period", candidate=candidate.candidate_name, value=30, unit="days")))
    body = ask(agent_env, "set the notice period to 30 days").json()
    _confirm(agent_env, body)
    agent_env["db"].expire_all()
    assert agent_env["db"].get(Candidate, candidate.id).notice_period_value == 30


def test_an_invalid_demand_edit_is_refused_at_proposal_time(agent_env):
    position = agent_env["db"].get(Position, agent_env["make_jd"]())
    model = agent_env["install"](use(call("update_demand", demand=position.display_id, fields={"status": "Open"})), say("Cannot do that."))
    body = ask(agent_env, "change the status through the edit tool").json()
    assert body["action"] != "confirm_action" and "Allowed fields" in _tool_result(model)


def test_a_comment_is_added_only_after_confirmation(agent_env):
    candidate = _named(agent_env, f"Comment Target{agent_env['tag']}")
    agent_env["install"](use(call("add_comment", candidate=candidate.candidate_name, body="Strong on Camunda.", rating=4)))
    body = ask(agent_env, "comment that the candidate is strong on Camunda").json()
    before = agent_env["client"].get(f"/api/candidates/{candidate.id}/comments", headers=agent_env["headers"]).json()
    assert body["action"] == "confirm_action" and len(before) == 0
    _confirm(agent_env, body)
    after = agent_env["client"].get(f"/api/candidates/{candidate.id}/comments", headers=agent_env["headers"]).json()
    assert [c["body"] for c in after] == ["Strong on Camunda."]


def test_tracker_questions_are_on_topic_for_the_scope_guard():
    from backend.services.llm.scope import is_in_scope
    for text in ("add a row to the pipeline tracker", "change my name", "show the submission tracker", "what is on the L2 sheets"):
        assert is_in_scope(text), text
