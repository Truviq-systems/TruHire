import os
from typing import List, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Local runs use .env by default. Set TRUHIRE_ENV_FILE=.env.production to load
    # a separate local production-like config; real production should inject vars.
    model_config = SettingsConfigDict(
        env_file=os.getenv("TRUHIRE_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "TruHire"
    APP_ENV: str = "development"

    # Logging (see backend/logging_config.py). LOG_JSON=true for structured logs; empty LOG_FILE disables the file.
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False
    LOG_FILE: str = "./logs/truhire.log"
    SLOW_REQUEST_MS: int = 2000

    # PostgreSQL only, e.g. postgresql+psycopg://user:pass@localhost:5432/truhire
    # (URL-encode special characters in the password, e.g. "@" -> "%40"). Required, no default.
    DATABASE_URL: str
    DATABASE_URL_UNPOOLED: Optional[str] = None
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Neon Object Storage uses its S3-compatible API. Keep its private credentials
    # in environment variables; use local disk for development unless selected.
    OBJECT_STORAGE_BACKEND: str = "local"
    OBJECT_STORAGE_BUCKET: Optional[str] = None
    AWS_ENDPOINT_URL_S3: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None

    # Required, no default: a baked-in signing key in source would be a leaked secret.
    # Set in .env (generate with: python -c "import secrets; print(secrets.token_urlsafe(48))").
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # OpenAI-compatible LLM/embedding server. Required, no default: an infra address
    # has no safe generic value (not a real address, not localhost either - a silent
    # localhost fallback would mask a missing/wrong .env just as much as a real one
    # baked into source would leak it). Set in .env; the app fails to start without it.
    VLLM_BASE_URL: str
    VLLM_API_KEY: Optional[str] = None
    VLLM_MODEL: Optional[str] = None
    VLLM_EMBEDDING_MODEL: Optional[str] = None
    VLLM_TIMEOUT: float = 120.0

    # Separate embedding server, since the DGX vLLM instance above only serves the
    # Qwen generation model and does not expose /v1/embeddings. Falls back to
    # VLLM_BASE_URL if unset (which will correctly fail with a 404 rather than
    # silently using the generation model).
    EMBEDDING_BASE_URL: Optional[str] = None
    VLLM_EMBEDDING_BASE_URL: Optional[str] = None
    VLLM_EMBEDDING_API_KEY: Optional[str] = None

    # ── Cloud LLM fallback providers (chat only; embeddings use local fastembed) ──
    # Used by backend/services/llm/router.py when vLLM (DGX) is unreachable.
    # Priority: vLLM → OpenRouter → Groq → Gemini.

    # OpenRouter — 1st fallback. Routes to any model via a single API key.
    OPENROUTER_API_KEY_1: Optional[str] = None
    OPENROUTER_API_KEY_2: Optional[str] = None
    OPENROUTER_API_KEY_3: Optional[str] = None
    OPENROUTER_CHAT_MODEL: str = "openai/gpt-4o-mini"  # override via .env

    # Groq — 2nd fallback. Ultra-fast inference for Llama / Mixtral models.
    GROQ_API_KEY_1: Optional[str] = None
    GROQ_API_KEY_2: Optional[str] = None
    GROQ_API_KEY_3: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Gemini — 3rd fallback. Three keys for high rate-limit headroom.
    GEMINI_API_KEY_1: Optional[str] = None
    GEMINI_API_KEY_2: Optional[str] = None
    GEMINI_API_KEY_3: Optional[str] = None
    GEMINI_CHAT_MODEL: str = "gemini-2.0-flash-lite"  # override via .env

    # Chat latency budget (seconds). vLLM is always tried first; a slow or failing key/provider is skipped.
    LLM_TOTAL_TIMEOUT: float = 60.0          # hard cap for one chat call across vLLM + every cloud key
    LLM_CONNECT_TIMEOUT: float = 3.0         # fail fast when the DGX box / a provider is unreachable
    LLM_VLLM_CHAT_TIMEOUT: float = 30.0      # max wait for the DGX before moving to the cloud chain
    LLM_CLOUD_KEY_TIMEOUT: float = 15.0      # max wait per cloud API key before trying the next key
    LLM_KEY_COOLDOWN_SECONDS: float = 20.0   # a key that just failed is tried last for this long
    LLM_VLLM_BREAKER_FAILURES: int = 2       # consecutive DGX failures before it is skipped
    LLM_VLLM_BREAKER_COOLDOWN: float = 30.0  # seconds to skip the DGX, then probe it again
    LLM_CLOUD_REDACT_PII: bool = True        # strip emails/phones/ids before text leaves for a cloud LLM

    # Vector database. Required, no default - same reasoning as VLLM_BASE_URL above.
    QDRANT_URL: str
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "truhire_candidate_vectors"
    QDRANT_DISTANCE: str = "Cosine"
    # Memory-efficient layout (applied when the collection is created): full-precision
    # vectors live on disk, int8-quantized copies stay in RAM for fast search, and the top
    # hits are re-scored against the originals. ~4x less RAM per chunk at negligible recall loss.
    QDRANT_ON_DISK: bool = True
    QDRANT_QUANTIZATION: bool = True
    QDRANT_QUANTILE: float = 0.99
    QDRANT_RESCORE_OVERSAMPLING: float = 2.0
    # How long (seconds) the "collection exists / dimension ok" check is cached in-process.
    INDEX_STATE_TTL: int = 300

    # OpenSearch is retained for lexical/BM25 retrieval in the hybrid pipeline.
    # Required, no default - same reasoning as VLLM_BASE_URL above.
    OPENSEARCH_URL: str
    OPENSEARCH_USER: Optional[str] = None
    OPENSEARCH_PASSWORD: Optional[str] = None
    OPENSEARCH_INDEX: str = "truhire_candidates_v2"

    # "local" runs fastembed in-process (no API key, no external server); anything
    # else calls out to the configured vLLM-compatible embedding endpoint.
    EMBEDDING_PROVIDER: str = "local"
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_MODEL: Optional[str] = None
    EMBEDDING_DIM: int = 768
    # Where fastembed keeps the downloaded ONNX model. Unset = fastembed's default, a temp dir that
    # is wiped on restart (re-download, 30-60s cold start). Point it at a persistent disk in production.
    FASTEMBED_CACHE_DIR: Optional[str] = None

    # Laya: local non-autoregressive decision model (choice/score/noul), used as a fast
    # judgment layer instead of an LLM call for reranking, chat intent/decisions, and
    # guardrails. Falls back to the vLLM LLM path whenever Laya's own confidence is low
    # (its "escalate" action) or when it's disabled/unavailable.
    LAYA_ENABLED: bool = True
    LAYA_CONFIDENCE_THRESHOLD: float = 0.65
    LAYA_RERANK_WEIGHT: float = 0.20
    # Laya reranking only runs on a shortlist near the top of the deterministic
    # ranking, not the whole retrieval pool (which can be up to 500 candidates) - on
    # CPU-only hardware Laya measured ~0.4s/candidate even batched, so reranking the
    # full pool could add tens of seconds to a single search. This bounds that cost
    # while still reranking where it can actually change the final top_n.
    LAYA_RERANK_POOL_CAP: int = 50
    FIT_SCORE_WORKERS: int = 16
    CACHE_TTL_DECISION: int = 3600
    # Interactive search returns deterministic hybrid scores immediately. The
    # DGX fit reranker can be enabled when slower model-based refinement is desired.
    SEARCH_LLM_RERANK_ENABLED: bool = False
    SEARCH_VECTOR_TIMEOUT: float = 8.0

    # Cross-encoder reranker (BGE) applied to the best-matching chunk of each shortlisted
    # candidate. Runs in-process via fastembed/ONNX on CPU; if the model cannot load the
    # search degrades gracefully to the un-reranked ordering.
    RERANKER_ENABLED: bool = False  # CPU cross-encoder: about 0.5 s per candidate, so off by default
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"
    RERANKER_POOL_CAP: int = 30
    RERANKER_WEIGHT: float = 0.30
    RERANKER_RETRY_SECONDS: int = 300

    INGEST_BATCH_SIZE: int = 50
    MAX_UPLOAD_MB: int = 15
    STORAGE_DIR: str = "./uploads"
    RESUME_STORAGE_DIR: str = "./uploads/resumes"
    JD_STORAGE_DIR: str = "./uploads/job_descriptions"

    # Data Retention (in days, generic, loaded from .env)
    # Resumes, chunks/embeddings, and JD information will be stored only for this duration
    DATA_RETENTION_DAYS: int = 30
    RESUME_RETENTION_DAYS: Optional[int] = None
    JD_RETENTION_DAYS: Optional[int] = None
    RETENTION_CLEANUP_INTERVAL_HOURS: int = 24

    @property
    def effective_resume_retention_days(self) -> int:
        return self.RESUME_RETENTION_DAYS if self.RESUME_RETENTION_DAYS is not None else self.DATA_RETENTION_DAYS

    @property
    def effective_jd_retention_days(self) -> int:
        return self.JD_RETENTION_DAYS if self.JD_RETENTION_DAYS is not None else self.DATA_RETENTION_DAYS

    SEARCH_MAX_TOP_N: int = 100
    SEARCH_DEFAULT_TOP_N: int = 20

    # Reviewer collaboration + client-facing limits (served to the UI via /api/meta).
    BOOTSTRAP_ADMIN_EMAILS: str = ""  # comma-separated; these emails register as admin, everyone else as recruiter
    COMMENT_MAX_CHARS: int = 2000
    HISTORY_PAGE_SIZE: int = 25
    AUDIT_PAGE_SIZE: int = 25
    JD_ACCEPTED_EXTENSIONS: str = ".pdf,.docx,.doc,.rtf,.odt,.txt,.md"

    @property
    def bootstrap_admin_emails(self) -> set:
        return {e.strip().lower() for e in self.BOOTSTRAP_ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def jd_accepted_extensions(self) -> list:
        return [e.strip() for e in self.JD_ACCEPTED_EXTENSIONS.split(",") if e.strip()]
    HYBRID_VECTOR_WEIGHT: float = 0.60
    HYBRID_LEXICAL_WEIGHT: float = 0.40
    HYBRID_RRF_K: int = 60
    SEARCH_CANDIDATE_MULTIPLIER: int = 3

    SEMANTIC_WEIGHT: float = 0.60
    SKILL_WEIGHT: float = 0.40
    BASELINE_SCORE: float = 0.0
    SEMANTIC_COSINE_FLOOR: float = 0.40
    SEMANTIC_COSINE_CEIL: float = 0.85
    EXPERIENCE_PENALTY: float = 0.10
    EDUCATION_PENALTY: float = 0.05

    # Requirements view only lists candidates at or above this match score.
    REQUIREMENT_MATCH_THRESHOLD: float = 50.0

    # AI governance. With enforcement on, AI output that the guardrails cannot verify
    # (including when Laya is unavailable) is replaced by deterministic fallbacks or blocked.
    GUARDRAILS_ENFORCE: bool = True
    AI_AUDIT_RETENTION_DAYS: int = 365

    # Outbound email. Without SMTP_HOST, sends are recorded as "simulated" and nothing leaves the server.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT: float = 20.0
    # Hiring-company facts given to the LLM when drafting candidate emails; unset values are never invented.
    COMPANY_NAME: Optional[str] = None
    COMPANY_DESCRIPTION: Optional[str] = None

    ANALYTICS_TOP_SKILLS: int = 20
    CACHE_TTL_QUERY: int = 60
    # Assistant pre-flight (services/llm/preflight.py): the rate gate before a model-backed turn, the exact-match
    # answer cache for standalone read-only questions, and the size the agent's context is trimmed to
    # (characters; about a quarter as many tokens).
    ASSISTANT_RATE_BURST: int = 15
    ASSISTANT_RATE_REFILL_SECONDS: float = 4.0
    ASSISTANT_CACHE_TTL: int = 300
    AGENT_CONTEXT_CHAR_BUDGET: int = 24000
    # Analytics report: weeks on the demand timeline, and how many items "Needs attention" lists.
    ANALYTICS_TIMELINE_WEEKS: int = 26
    ANALYTICS_ATTENTION_LIMIT: int = 5
    # Ingestion: a processing batch with no progress write for this long is treated as dead and marked failed;
    # the progress card says the AI step is slow after this many seconds without an update.
    INGEST_STALE_SECONDS: int = 180
    INGEST_SLOW_AFTER_SECONDS: int = 20
    # Chunks embedded per call, so a large batch reports progress (and a heartbeat) between slices.
    INGEST_EMBED_SLICE: int = 32
    # Redis cache: connect timeout, and how long to wait before trying an unreachable Redis again.
    REDIS_CONNECT_TIMEOUT: float = 2.0
    REDIS_RETRY_SECONDS: int = 30
    CACHE_TTL_SEARCH: int = 900  # search results; every candidate/JD/index write clears the "search:" prefix
    # Scored requirement->candidate matches are expensive (embedding + retrieval + rerankers). They are keyed by
    # JD version and index epoch, so they self-invalidate on any change and can safely live long.
    CACHE_TTL_MATCHES: int = 86400

    # Redis connection settings
    REDIS_URL: Optional[str] = None
    CACHE_REDIS_URL: Optional[str] = None
    QUEUE_REDIS_URL: Optional[str] = None
    REDIS_HOST: Optional[str] = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    USE_ARQ_QUEUE: bool = False

    @property
    def effective_redis_url(self) -> Optional[str]:
        if self.REDIS_URL and self.REDIS_URL.strip():
            return self.REDIS_URL.strip()
        if self.REDIS_HOST and self.REDIS_PASSWORD:
            from urllib.parse import quote_plus
            return f"redis://:{quote_plus(self.REDIS_PASSWORD)}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        elif self.REDIS_HOST:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return None

    @property
    def effective_cache_redis_url(self) -> Optional[str]:
        return (self.CACHE_REDIS_URL or "").strip() or self.effective_redis_url

    @property
    def effective_queue_redis_url(self) -> Optional[str]:
        return (self.QUEUE_REDIS_URL or "").strip() or self.effective_redis_url

    def get_arq_redis_settings(self):
        """Returns arq RedisSettings with unquoted password to avoid authentication failure."""
        from arq.connections import RedisSettings
        from urllib.parse import unquote
        queue_url = self.effective_queue_redis_url
        if self.QUEUE_REDIS_URL and queue_url:
            rs = RedisSettings.from_dsn(queue_url)
            if rs.password:
                rs.password = unquote(rs.password)
            return rs
        if self.REDIS_PASSWORD and self.REDIS_HOST:
            return RedisSettings(
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                password=self.REDIS_PASSWORD,
            )
        if queue_url:
            rs = RedisSettings.from_dsn(queue_url)
            if rs.password:
                rs.password = unquote(rs.password)
            return rs
        return RedisSettings()

    # Rate limiting (slowapi/limits syntax: "<count>/<second|minute|hour|day>").
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "300/minute"  # per signed-in user (per IP when signed out); one search page makes several calls
    RATE_LIMIT_USE_REDIS: bool = True  # share counts between API workers; falls back to per-process if Redis is down

    # In development any localhost/127.0.0.1 port is allowed (frontend can run on any port).
    # In production set CORS_ORIGINS to the exact frontend origin(s) and leave this empty.
    CORS_ORIGIN_REGEX: Optional[str] = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173", "http://localhost:3000",
        "http://127.0.0.1:5173", "http://127.0.0.1:3000"
    ]


    @model_validator(mode="after")
    def _check_secrets(self):
        if not self.DATABASE_URL.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg://user:pass@host:5432/db).")
        # Database by environment: development -> local Postgres, production -> Neon (cloud).
        from urllib.parse import urlparse
        db_host = (urlparse(self.DATABASE_URL).hostname or "").lower()
        env_name = self.APP_ENV.lower()
        if env_name == "production" and db_host in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("APP_ENV=production must use the Neon database, not a local one. Set DATABASE_URL to the Neon URL.")
        if env_name in ("development", "dev") and db_host.endswith(".neon.tech"):
            raise ValueError("APP_ENV=development must use the local database, not Neon. Point DATABASE_URL at local Postgres.")
        if self.OBJECT_STORAGE_BACKEND.lower() not in ("local", "neon"):
            raise ValueError("OBJECT_STORAGE_BACKEND must be 'local' or 'neon'.")
        if self.OBJECT_STORAGE_BACKEND.lower() == "neon":
            required_storage_values = {
                "OBJECT_STORAGE_BUCKET": self.OBJECT_STORAGE_BUCKET,
                "AWS_ENDPOINT_URL_S3": self.AWS_ENDPOINT_URL_S3,
                "AWS_ACCESS_KEY_ID": self.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": self.AWS_SECRET_ACCESS_KEY,
                "AWS_REGION": self.AWS_REGION,
            }
            missing = [name for name, value in required_storage_values.items() if not value]
            if missing:
                raise ValueError(f"Neon object storage is enabled but required settings are missing: {', '.join(missing)}")
        if self.APP_ENV.lower() not in ("development", "dev", "test") and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters outside development.")
        return self


settings = Settings()


def database_target() -> str:
    """The database the app will use as `user@host:port/db` (never the password), plus a note when a
    process environment variable overrides the env file. An exported DATABASE_URL in the terminal wins
    over .env, so a stale one silently points the app at the wrong login or server."""
    from urllib.parse import urlparse
    parsed = urlparse(settings.DATABASE_URL)
    target = f"{parsed.username}@{parsed.hostname}:{parsed.port}{parsed.path}"
    from_env = os.environ.get("DATABASE_URL")
    if from_env and from_env == settings.DATABASE_URL:
        from dotenv import dotenv_values
        in_file = dotenv_values(os.getenv("TRUHIRE_ENV_FILE", ".env")).get("DATABASE_URL")
        if in_file and in_file != from_env:
            return (f"{target}  <- from the DATABASE_URL environment variable, which overrides "
                    f"{os.getenv('TRUHIRE_ENV_FILE', '.env')}. Clear it with: Remove-Item Env:DATABASE_URL")
    return target
