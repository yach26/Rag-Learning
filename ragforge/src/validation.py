"""
src/validation.py — Upload and document safety checks
=======================================================

Limits size, type, and obvious malicious PDF payloads before ingestion.
This is not antivirus; production deployments should still run ClamAV
(or similar) at the edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import config

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
PDF_MAGIC = b"%PDF"
# Common PDF script / launch payloads
_PDF_SUSPICIOUS = (
    b"/JavaScript",
    b"/Launch",
    b"/RichMedia",
)


class ValidationError(ValueError):
    pass


@dataclass
class UploadedFile:
    name: str
    data: bytes


def sanitize_filename(name: str) -> str:
    raw = Path(name).name
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in raw).strip()
    if not cleaned or cleaned in {".", ".."}:
        raise ValidationError("Invalid filename.")
    if len(cleaned) > 180:
        cleaned = cleaned[:180]
    return cleaned


def _extension(name: str) -> str:
    return Path(name).suffix.lower()


def validate_upload(name: str, data: bytes) -> str:
    """
    Validate an uploaded file. Returns a sanitized filename.
    Raises ValidationError on rejection.
    """
    if not data:
        raise ValidationError("Empty file rejected.")

    filename = sanitize_filename(name)
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    max_bytes = config.MAX_UPLOAD_BYTES
    if len(data) > max_bytes:
        mb = max_bytes / (1024 * 1024)
        raise ValidationError(f"File exceeds {mb:.0f} MB size limit.")

    if ext == ".pdf":
        _validate_pdf(data)
    else:
        _validate_text(data)

    return filename


def _validate_pdf(data: bytes) -> None:
    if not data.startswith(PDF_MAGIC):
        raise ValidationError("File is not a valid PDF (missing %PDF header).")

    sample = data[: min(len(data), config.MAX_PDF_SCAN_BYTES)]
    for marker in _PDF_SUSPICIOUS:
        if marker in sample:
            raise ValidationError(
                f"PDF rejected: contains active content marker {marker.decode('latin-1')}."
            )

    page_hints = sample.count(b"/Type /Page")
    if page_hints > config.MAX_PDF_PAGES:
        raise ValidationError(f"PDF exceeds {config.MAX_PDF_PAGES} page limit.")


def _validate_text(data: bytes) -> None:
    if b"\x00" in data:
        raise ValidationError("Text file contains null bytes and was rejected.")
    # Reject high-entropy binary disguised as txt/md
    sample = data[:4096]
    if sample:
        non_text = sum(1 for b in sample if b < 9 or (13 < b < 32))
        if non_text / len(sample) > 0.15:
            raise ValidationError("File does not look like UTF-8/plain text.")


def write_validated_upload(dest_dir: Path, name: str, data: bytes) -> Path:
    filename = validate_upload(name, data)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)
    return dest


def validate_existing_file(path: Path) -> None:
    data = path.read_bytes()
    validate_upload(path.name, data)
