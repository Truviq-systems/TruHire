"""An ingestion batch can never stay "processing" forever: a task that dies is detected and the page is told."""
from datetime import datetime, timedelta

from test_ingestion_history_and_progress import _make_batch, _stub_pipeline, auth  # noqa: F401  (fixture and helpers)
from backend.config import settings
from backend.database import SessionLocal
from backend.models import INGEST_FINAL_FILE_STATUSES, IngestionBatch
from backend.routers import ingestion as ing


def _batch(batch_id):
    db = SessionLocal()
    try:
        row = db.get(IngestionBatch, batch_id)
        return {"status": row.status, "stage": row.stage, "errors": row.error_log, "files": row.file_status,
                "failed": row.failed_count, "heartbeat": row.updated_at}
    finally:
        db.close()


def _age(batch_id, seconds):
    db = SessionLocal()
    db.get(IngestionBatch, batch_id).updated_at = datetime.utcnow() - timedelta(seconds=seconds)
    db.commit()
    db.close()


def test_a_crash_outside_the_per_file_handling_fails_the_batch_instead_of_leaving_it_processing(auth, monkeypatch):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(ing, "_cancel_requested", lambda db, batch_id: (_ for _ in ()).throw(RuntimeError("database went away")))
    name = f"crash-{auth['tag']}.txt"
    bid = _make_batch(auth["user_id"], [name])

    ing.process_batch(bid, [(name, b"Python developer")], auth["user_id"])

    row = _batch(bid)
    assert row["status"] == "failed" and row["stage"] == "done"
    assert "database went away" in row["errors"][-1]["error"]
    assert row["files"][0]["status"] == "failed" and row["failed"] == 1


def test_progress_writes_stamp_a_heartbeat(auth, monkeypatch):
    _stub_pipeline(monkeypatch)
    name = f"beat-{auth['tag']}.txt"
    bid = _make_batch(auth["user_id"], [name])
    ing.process_batch(bid, [(name, f"Java developer {auth['tag']} with Spring".encode())], auth["user_id"])
    row = _batch(bid)
    assert row["status"] == "completed" and row["heartbeat"] is not None


def test_a_batch_that_stopped_updating_is_failed_when_the_page_polls_it(auth):
    bid = _make_batch(auth["user_id"], ["a.txt", "b.txt"])
    _age(bid, settings.INGEST_STALE_SECONDS + 5)

    polled = auth["client"].get(f"/api/ingest/batches/{bid}", headers=auth["headers"]).json()

    assert polled["status"] == "failed" and polled["stage"] == "done"
    assert all(f["status"] == "failed" for f in polled["file_status"])
    assert "interrupted" in polled["error_log"][-1]["error"].lower()


def test_a_batch_with_a_recent_heartbeat_is_left_alone(auth):
    bid = _make_batch(auth["user_id"], ["a.txt"])
    _age(bid, 5)
    polled = auth["client"].get(f"/api/ingest/batches/{bid}", headers=auth["headers"]).json()
    assert polled["status"] == "processing"


def test_the_startup_sweep_fails_only_stale_batches_and_keeps_finished_files(auth):
    stale = _make_batch(auth["user_id"], ["old.txt"])
    live = _make_batch(auth["user_id"], ["new.txt"])
    done = _make_batch(auth["user_id"], ["done.txt"])
    db = SessionLocal()
    db.get(IngestionBatch, done).file_status = [{"filename": "done.txt", "status": "indexed", "detail": "ok"}]
    db.commit()
    db.close()
    _age(stale, settings.INGEST_STALE_SECONDS + 5)
    _age(live, 5)
    _age(done, settings.INGEST_STALE_SECONDS + 5)

    ing.fail_stale_batches()

    assert _batch(stale)["status"] == "failed"
    assert _batch(live)["status"] == "processing"
    kept = _batch(done)
    assert kept["status"] == "failed" and kept["files"][0]["status"] == "indexed"  # already-indexed work is not rewritten


def test_embedding_runs_in_slices_with_a_heartbeat_between_them(auth, monkeypatch):
    _stub_pipeline(monkeypatch)
    sizes = []
    monkeypatch.setattr(ing, "generate_embeddings_batch", lambda texts: sizes.append(len(texts)) or [[0.1] * 8 for _ in texts])
    monkeypatch.setattr(settings, "INGEST_EMBED_SLICE", 1)
    name = f"slice-{auth['tag']}.txt"
    bid = _make_batch(auth["user_id"], [name])
    # Unique per run: identical bytes from an earlier run would be skipped as a duplicate and never reach embedding.
    body = (f"Python developer {auth['tag']} with FastAPI and many skills. " * 80).encode()
    ing.process_batch(bid, [(name, body)], auth["user_id"])
    assert sizes and all(n == 1 for n in sizes)
    assert _batch(bid)["status"] == "completed"


def test_final_file_statuses_come_from_one_constant():
    assert set(INGEST_FINAL_FILE_STATUSES) == {"indexed", "updated", "duplicate", "skipped", "failed"}
