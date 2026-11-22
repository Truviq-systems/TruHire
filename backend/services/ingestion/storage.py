import hashlib
import logging
import mimetypes
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote

from fastapi.responses import FileResponse, Response
from backend.config import settings

logger = logging.getLogger(__name__)


def ensure_resume_storage_dir() -> Path:
    storage_path = Path(settings.RESUME_STORAGE_DIR)
    storage_path.mkdir(parents=True, exist_ok=True)
    return storage_path


def ensure_jd_storage_dir() -> Path:
    storage_path = Path(settings.JD_STORAGE_DIR)
    storage_path.mkdir(parents=True, exist_ok=True)
    return storage_path


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file content for exact duplicate detection."""
    return hashlib.sha256(file_bytes).hexdigest()


def _uses_neon_storage() -> bool:
    return settings.OBJECT_STORAGE_BACKEND.lower() == "neon"


def _s3_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL_S3,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
        config=Config(s3={"addressing_style": "path"}),
    )


def _object_key(file_url: Optional[str]) -> Optional[str]:
    if not file_url:
        return None
    clean = file_url.replace("\\", "/").lstrip("/")
    if not clean.startswith("uploads/"):
        return None
    key = clean[len("uploads/"):]
    if not key or any(part in ("", ".", "..") for part in key.split("/")):
        return None
    if not (key.startswith("resumes/") or key.startswith("job_descriptions/")):
        return None
    return key


def save_upload_file(filename: str, file_bytes: bytes, category: str = "resumes") -> Tuple[str, str]:
    """Store an upload locally or in Neon Object Storage and return its stable URL and hash."""
    is_jd = category in ("job_descriptions", "jd", "jds")
    folder = "job_descriptions" if is_jd else "resumes"
    file_hash = compute_file_hash(file_bytes)

    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
    if not safe_filename:
        safe_filename = "document.bin"
    target_filename = f"{file_hash[:12]}_{safe_filename}"
    file_url = f"/uploads/{folder}/{target_filename}"

    if _uses_neon_storage():
        content_type = mimetypes.guess_type(safe_filename)[0] or "application/octet-stream"
        _s3_client().put_object(
            Bucket=settings.OBJECT_STORAGE_BUCKET,
            Key=f"{folder}/{target_filename}",
            Body=file_bytes,
            ContentType=content_type,
        )
        return file_url, file_hash

    target_dir = ensure_jd_storage_dir() if is_jd else ensure_resume_storage_dir()
    with open(target_dir / target_filename, "wb") as f:
        f.write(file_bytes)
    return file_url, file_hash


def resolve_stored_file(file_url: Optional[str]) -> Optional[Path]:
    """Resolve a legacy/local upload URL to a path confined to STORAGE_DIR."""
    if not file_url:
        return None
    clean = file_url.replace("\\", "/").lstrip("/")
    if not clean.startswith("uploads/"):
        return None
    root = Path(settings.STORAGE_DIR).resolve()
    target = (root / clean[len("uploads/"):]).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def stored_file_exists(file_url: Optional[str]) -> bool:
    if resolve_stored_file(file_url):
        return True
    key = _object_key(file_url)
    if not _uses_neon_storage() or not key:
        return False
    try:
        _s3_client().head_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
        return True
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _safe_content_disposition(disposition: str, filename: str) -> str:
    filename = Path(filename.replace("\\", "/")).name.replace("\r", "").replace("\n", "") or "document.bin"
    ascii_name = re.sub(r'[^A-Za-z0-9._ -]', "_", filename).replace('"', "_")
    return f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'


def stored_file_response(file_url: Optional[str], filename: Optional[str], download: bool = False):
    """Return an authenticated file response from local disk or private object storage."""
    disposition = "attachment" if download else "inline"
    path = resolve_stored_file(file_url)
    if path:
        return FileResponse(
            path,
            filename=filename or path.name,
            content_disposition_type=disposition,
            headers={"Cache-Control": "private, no-store"},
        )

    key = _object_key(file_url)
    if not _uses_neon_storage() or not key:
        return None
    try:
        response = _s3_client().get_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise

    file_name = filename or Path(key).name
    media_type = response.get("ContentType") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    return Response(
        content=response["Body"].read(),
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": _safe_content_disposition(disposition, file_name),
        },
    )


def delete_file_by_url_or_path(file_url_or_path: Optional[str]) -> bool:
    """Delete an upload from the selected store; continue accepting legacy local paths."""
    if not file_url_or_path:
        return False
    key = _object_key(file_url_or_path)
    if _uses_neon_storage() and key:
        try:
            _s3_client().delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=key)
            return True
        except Exception:
            logger.exception("Failed to delete object %s from Neon storage", key)
            return False

    try:
        clean = file_url_or_path.replace("\\", "/").lstrip("/")
        if clean.startswith("uploads/"):
            root = Path(settings.STORAGE_DIR).resolve()
            target_path = (root / clean[len("uploads/"):]).resolve()
            if not target_path.is_relative_to(root):
                return False
        else:
            target_path = Path(file_url_or_path)
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
            return True
    except Exception:
        logger.exception("Failed to delete stored file")
    return False
