import pytest
from pydantic import ValidationError

from backend.routers.assistant import AssistantMessageRequest
from backend.services.llm import preflight
from backend.services.llm.preflight import PLACEHOLDER, TokenBucket, fit_context_budget


def test_token_bucket_allows_a_burst_then_refills():
    bucket = TokenBucket(burst=2, refill_seconds=10)
    assert bucket.take("u", now=0)[0] and bucket.take("u", now=0)[0]
    allowed, wait = bucket.take("u", now=0)
    assert not allowed and wait == 10
    assert not bucket.take("u", now=5)[0]
    assert bucket.take("u", now=10)[0]
    assert bucket.take("other", now=0)[0]  # another user has their own bucket


def test_blank_messages_are_rejected_and_others_trimmed():
    with pytest.raises(ValidationError):
        AssistantMessageRequest(message="    ")
    assert AssistantMessageRequest(message="  hello  ").message == "hello"


def test_only_standalone_read_only_answers_are_cacheable():
    assert preflight.cacheable("how many java demands", 0, "12", {"action": "open_positions"})
    assert not preflight.cacheable("and the second?", 1, "x", {"action": "reply"})              # depends on earlier turns
    assert not preflight.cacheable("mark him active", 0, "Please confirm", {"action": "confirm_action"})  # a proposed change
    assert not preflight.cacheable("hi", 0, "", {"action": "reply"})                              # no answer
    assert not preflight.cacheable("x" * 301, 0, "ok", {"action": "reply"})


def test_cache_key_is_per_user_normalised_and_changes_with_the_data_version(monkeypatch):
    monkeypatch.setattr(preflight, "get_data_epoch", lambda: "1")
    a = preflight.cache_key("u1", "How many   DEMANDS?", None)
    assert a == preflight.cache_key("u1", "how many demands?", None)
    assert a != preflight.cache_key("u2", "how many demands?", None)
    monkeypatch.setattr(preflight, "get_data_epoch", lambda: "2")
    assert a != preflight.cache_key("u1", "how many demands?", None)


def test_answer_round_trips_through_the_cache(monkeypatch):
    store = {}
    monkeypatch.setattr(preflight, "get_cache", store.get)
    monkeypatch.setattr(preflight, "set_cache", lambda k, v, ttl_seconds=0: store.__setitem__(k, v))
    assert preflight.cached_answer("u", "q", None) is None
    preflight.remember_answer("u", "q", None, "answer", {"action": "reply"})
    assert preflight.cached_answer("u", "q", None) == ("answer", {"action": "reply"})


def _conversation(big=3000):
    return [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "old question " + "x" * big},
        {"role": "assistant", "content": "old answer " + "y" * big},
        {"role": "user", "content": "newest question"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
        {"role": "tool", "tool_call_id": "1", "content": "t" * big},
    ]


def test_context_budget_keeps_system_and_newest_user_and_drops_old_turns_first():
    out = fit_context_budget(_conversation(), 4000)
    assert out[0]["role"] == "system"
    assert any(m["content"] == "newest question" for m in out)
    assert not any("old question" in m["content"] for m in out)
    assert any(m["role"] == "tool" for m in out)  # tool result kept while it still fits


def test_context_budget_replaces_old_tool_results_last_and_keeps_pairs():
    out = fit_context_budget(_conversation(), 500)
    tool = next(m for m in out if m["role"] == "tool")
    assert tool["content"] == PLACEHOLDER and tool["tool_call_id"] == "1"
    assert any(m.get("tool_calls") for m in out)


def test_context_budget_leaves_small_conversations_untouched():
    msgs = _conversation(big=10)
    assert fit_context_budget(msgs, 24000) == msgs


# ── End to end: the order of the pre-flight layers on the real endpoint ─────────────────────

import uuid
from fastapi.testclient import TestClient

from backend.auth import create_access_token, get_password_hash
from backend.database import SessionLocal
from backend.main import app
from backend.models import Conversation, ConversationMessage, User
from backend.routers import assistant
from backend.services.llm import agent


@pytest.fixture
def chat(monkeypatch):
    """A signed-in client, a counter of model-backed agent runs, and a clean cache and rate gate."""
    store, runs = {}, []
    monkeypatch.setattr(preflight, "get_cache", store.get)
    monkeypatch.setattr(preflight, "set_cache", lambda k, v, ttl_seconds=0: store.__setitem__(k, v))
    monkeypatch.setattr(preflight, "_bucket", TokenBucket(burst=3, refill_seconds=3600))
    monkeypatch.setattr(agent, "run_agent", lambda *a, **k: runs.append(1) or ("agent answer", {"action": "reply"}))
    db = SessionLocal()
    user = User(email=f"pf-{uuid.uuid4().hex[:6]}@truhire.com", name="Preflight", hashed_password=get_password_hash("pass12345"))
    db.add(user)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}
    yield TestClient(app), headers, runs
    ids = [c.id for c in db.query(Conversation).filter(Conversation.user_id == user.id).all()]
    db.query(ConversationMessage).filter(ConversationMessage.conversation_id.in_(ids)).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    db.close()


def test_greetings_and_blank_messages_never_reach_the_model(chat):
    client, headers, runs = chat
    assert "create demands" in client.post("/api/assistant/message", json={"message": "hey"}, headers=headers).json()["reply"]
    assert client.post("/api/assistant/message", json={"message": "   "}, headers=headers).status_code == 422
    assert runs == []


def test_a_repeated_standalone_question_is_served_from_the_cache(chat):
    client, headers, runs = chat
    first = client.post("/api/assistant/message", json={"message": "summarise the java requirement skills"}, headers=headers).json()
    again = client.post("/api/assistant/message", json={"message": "Summarise  the Java requirement SKILLS"}, headers=headers).json()
    assert first["reply"] == again["reply"] == "agent answer"
    assert len(runs) == 1


def test_a_follow_up_is_not_cached_because_it_depends_on_the_conversation(chat):
    client, headers, runs = chat
    first = client.post("/api/assistant/message", json={"message": "list candidates for the java requirement"}, headers=headers).json()
    for _ in range(2):
        client.post("/api/assistant/message", json={"message": "and the second candidate?", "conversation_id": first["conversation_id"]}, headers=headers)
    assert len(runs) == 3


def test_the_rate_gate_stops_a_flood_before_it_spends_inference(chat):
    client, headers, runs = chat
    statuses = [client.post("/api/assistant/message", json={"message": f"find candidates for requirement number {i}"}, headers=headers).status_code
                for i in range(5)]
    assert statuses == [200, 200, 200, 429, 429]
    assert len(runs) == 3
