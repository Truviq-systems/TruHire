"""Pre-flight layer for the assistant: cheap, deterministic checks that run before any model call.

Order, cheapest first (see the router's `_answer`):
  1. validate    request model strips and rejects blank messages; the size cap lives on the request
  2. scope       scope.is_in_scope(): off-topic messages are refused without a model call
  3. route       exact, confident intents (greeting, saved counts) are answered by code
  4. cache       a standalone read-only question already answered at this data version is replayed
  5. gate        a per-user token bucket stops loops and floods before they spend inference
  6. budget      the context sent to the model is trimmed to a fixed size
  7. model       the tool-calling agent, only when reasoning is actually needed

Everything here is plain code: no model, no network. The cache is exact-match on purpose: TruHire answers
come from live data, and a similar question can have a different answer, so a similarity cache is not safe.
"""
import hashlib
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings
from backend.services.common.cache import get_cache, get_data_epoch, set_cache

# Answers that may be replayed: read-only results. Anything that proposes or starts a change is never cached.
CACHEABLE_ACTIONS = frozenset({
    "reply", "candidate_lookup", "client_groups", "client_demands", "open_positions", "matches",
    "candidate_history", "candidate_comparison", "client_candidate_matches",
})
PLACEHOLDER = "[earlier tool result omitted to fit the context budget]"


# ----------------------------------------------------------------------------- rate gate (token bucket)

class TokenBucket:
    """`burst` tokens, refilled at one per `refill_seconds`. take() returns (allowed, seconds_to_wait)."""

    def __init__(self, burst: int, refill_seconds: float):
        self.burst, self.refill = float(burst), float(refill_seconds)
        self._state: Dict[str, Tuple[float, float]] = {}   # key -> (tokens, last_seen)
        self._lock = threading.Lock()

    def take(self, key: str, now: Optional[float] = None) -> Tuple[bool, float]:
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._state.get(key, (self.burst, now))
            tokens = min(self.burst, tokens + (now - last) / self.refill)
            if tokens < 1:
                self._state[key] = (tokens, now)
                return False, round((1 - tokens) * self.refill, 1)
            self._state[key] = (tokens - 1, now)
            if len(self._state) > 5000:   # bound memory: drop users who have fully refilled
                self._state = {k: v for k, v in self._state.items() if v[0] < self.burst}
            return True, 0.0


_bucket = TokenBucket(settings.ASSISTANT_RATE_BURST, settings.ASSISTANT_RATE_REFILL_SECONDS)


def allow_inference(user_id: str) -> Tuple[bool, float]:
    """May this user start another model-backed turn right now?"""
    return _bucket.take(user_id)


# ----------------------------------------------------------------------------- exact-match answer cache

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def cache_key(user_id: str, message: str, position_id: Optional[str]) -> str:
    """Per user (the agent's memory personalises answers) and per data version (any write changes the epoch)."""
    raw = "|".join((user_id, _normalize(message), position_id or "", get_data_epoch()))
    return "assistant:answer:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cacheable(message: str, prior_user_turns: int, reply: str, ui: dict) -> bool:
    """Only a standalone question (nothing earlier in the conversation to depend on) whose answer was read-only."""
    return (prior_user_turns == 0 and bool(reply) and len(message) <= 300
            and (ui or {}).get("action", "reply") in CACHEABLE_ACTIONS)


def cached_answer(user_id: str, message: str, position_id: Optional[str]) -> Optional[Tuple[str, dict]]:
    hit = get_cache(cache_key(user_id, message, position_id))
    return (hit["reply"], hit["ui"]) if isinstance(hit, dict) and "reply" in hit else None


def remember_answer(user_id: str, message: str, position_id: Optional[str], reply: str, ui: dict) -> None:
    set_cache(cache_key(user_id, message, position_id), {"reply": reply, "ui": ui}, ttl_seconds=settings.ASSISTANT_CACHE_TTL)


# ----------------------------------------------------------------------------- context budget

def _size(messages: List[Dict[str, Any]]) -> int:
    return sum(len(str(m.get("content") or "")) + len(str(m.get("tool_calls") or "")) for m in messages)


def fit_context_budget(messages: List[Dict[str, Any]], max_chars: int) -> List[Dict[str, Any]]:
    """Trim to roughly max_chars (about max_chars/4 tokens). The system prompt and the newest user message
    always stay. Oldest chat turns go first; then the oldest tool results are replaced by a short note, so
    every assistant tool call still has its matching tool message."""
    msgs = [dict(m) for m in messages]
    keep_last_user = max((i for i, m in enumerate(msgs) if m["role"] == "user"), default=-1)
    i = 1
    while _size(msgs) > max_chars and i < len(msgs):
        if i != keep_last_user and msgs[i]["role"] in ("user", "assistant") and not msgs[i].get("tool_calls"):
            del msgs[i]
            keep_last_user -= 1 if keep_last_user > i else 0
        else:
            i += 1
    for m in msgs:
        if _size(msgs) <= max_chars:
            break
        if m["role"] == "tool" and m.get("content") != PLACEHOLDER:
            m["content"] = PLACEHOLDER
    return msgs
