"""tests/test_validation.py"""

import pytest

from src.validation import ValidationError, sanitize_filename, validate_upload


def test_sanitize_strips_path_components():
    assert sanitize_filename("../etc/passwd.txt") == "passwd.txt"


def test_rejects_empty():
    with pytest.raises(ValidationError):
        validate_upload("a.txt", b"")


def test_rejects_exe_extension():
    with pytest.raises(ValidationError):
        validate_upload("malware.exe", b"MZ")


def test_accepts_plain_text():
    name = validate_upload("notes.txt", b"Hello RAG world")
    assert name == "notes.txt"


def test_rejects_pdf_without_magic():
    with pytest.raises(ValidationError, match="valid PDF"):
        validate_upload("doc.pdf", b"not a pdf")


def test_rejects_pdf_javascript():
    payload = b"%PDF-1.4\n1 0 obj\n<< /JavaScript (alert(1)) >>\nendobj\n"
    with pytest.raises(ValidationError, match="active content"):
        validate_upload("doc.pdf", payload)


def test_accepts_minimal_pdf():
    payload = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    assert validate_upload("ok.pdf", payload) == "ok.pdf"


def test_rejects_null_bytes_in_text():
    with pytest.raises(ValidationError):
        validate_upload("bad.txt", b"hello\x00world")
