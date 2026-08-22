"""
test_ingest.py — Tests for the Document Ingestion Module
==========================================================

Run with:
    pytest test_ingest.py -v

These tests use temporary files/directories created by pytest's tmp_path
fixture so they don't pollute your real data/ directory.
"""

import pytest
from pathlib import Path

from src.ingest import (
    clean_text,
    load_txt,
    load_markdown,
    load_single_file,
    load_documents,
    LOADERS,
)


# ── clean_text tests ──────────────────────────────────────────────────────────

class TestCleanText:
    """Test the text cleaning utility."""

    def test_removes_extra_spaces(self):
        raw = "Hello   world   this  is  text"
        cleaned = clean_text(raw)
        assert "  " not in cleaned  # No double spaces

    def test_removes_trailing_newlines(self):
        raw = "Some text\n\n\n\n\nMore text"
        cleaned = clean_text(raw)
        # Should be collapsed to at most two newlines
        assert "\n\n\n" not in cleaned

    def test_strips_leading_trailing_whitespace(self):
        raw = "   \n Hello World \n   "
        cleaned = clean_text(raw)
        assert cleaned == cleaned.strip()

    def test_empty_string_stays_empty(self):
        assert clean_text("") == ""

    def test_preserves_paragraph_breaks(self):
        raw = "Paragraph one.\n\nParagraph two."
        cleaned = clean_text(raw)
        # The double newline (paragraph break) should be preserved
        assert "\n\n" in cleaned


# ── load_txt tests ────────────────────────────────────────────────────────────

class TestLoadTxt:
    """Test TXT file loading."""

    def test_loads_txt_file(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello, this is a test document.", encoding="utf-8")

        docs = load_txt(txt_file)

        assert len(docs) == 1
        assert "Hello, this is a test document." in docs[0]["text"]

    def test_txt_metadata_has_source_and_page(self, tmp_path: Path):
        txt_file = tmp_path / "myfile.txt"
        txt_file.write_text("Some content here.", encoding="utf-8")

        docs = load_txt(txt_file)

        assert docs[0]["metadata"]["source"] == "myfile.txt"
        assert docs[0]["metadata"]["page"] == 1

    def test_empty_txt_returns_empty_list(self, tmp_path: Path):
        txt_file = tmp_path / "empty.txt"
        txt_file.write_text("", encoding="utf-8")

        docs = load_txt(txt_file)

        assert docs == []

    def test_txt_with_only_whitespace_returns_empty(self, tmp_path: Path):
        txt_file = tmp_path / "whitespace.txt"
        txt_file.write_text("   \n\n   \t   ", encoding="utf-8")

        docs = load_txt(txt_file)

        assert docs == []

    def test_txt_raises_on_nonexistent_file(self):
        with pytest.raises(RuntimeError, match="Failed to read TXT"):
            load_txt(Path("/nonexistent/path/file.txt"))


# ── load_markdown tests ───────────────────────────────────────────────────────

class TestLoadMarkdown:
    """Test Markdown file loading."""

    def test_loads_markdown_file(self, tmp_path: Path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n\nSome **bold** text here.", encoding="utf-8")

        docs = load_markdown(md_file)

        assert len(docs) == 1
        assert "Title" in docs[0]["text"]
        assert "bold" in docs[0]["text"]

    def test_markdown_metadata(self, tmp_path: Path):
        md_file = tmp_path / "notes.md"
        md_file.write_text("# Notes\n\nContent here.", encoding="utf-8")

        docs = load_markdown(md_file)

        assert docs[0]["metadata"]["source"] == "notes.md"
        assert docs[0]["metadata"]["page"] == 1

    def test_empty_markdown_returns_empty_list(self, tmp_path: Path):
        md_file = tmp_path / "empty.md"
        md_file.write_text("", encoding="utf-8")

        docs = load_markdown(md_file)

        assert docs == []


# ── load_single_file tests ────────────────────────────────────────────────────

class TestLoadSingleFile:
    """Test the file-type dispatcher."""

    def test_dispatches_to_txt_loader(self, tmp_path: Path):
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text("Sample text content.", encoding="utf-8")

        docs = load_single_file(txt_file)

        assert len(docs) >= 1
        assert "Sample text content." in docs[0]["text"]

    def test_dispatches_to_markdown_loader(self, tmp_path: Path):
        md_file = tmp_path / "sample.md"
        md_file.write_text("# Sample\n\nMarkdown content.", encoding="utf-8")

        docs = load_single_file(md_file)

        assert len(docs) >= 1

    def test_raises_on_unsupported_extension(self, tmp_path: Path):
        unknown_file = tmp_path / "file.xyz"
        unknown_file.write_text("Some content", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported file type"):
            load_single_file(unknown_file)

    def test_raises_on_csv_file(self, tmp_path: Path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1,col2\n1,2", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported file type"):
            load_single_file(csv_file)


# ── load_documents tests ──────────────────────────────────────────────────────

class TestLoadDocuments:
    """Test the folder scanning function."""

    def test_loads_all_txt_files_in_folder(self, tmp_path: Path):
        (tmp_path / "doc1.txt").write_text("Document one content.", encoding="utf-8")
        (tmp_path / "doc2.txt").write_text("Document two content.", encoding="utf-8")

        docs = load_documents(tmp_path)

        assert len(docs) == 2

    def test_loads_mixed_file_types(self, tmp_path: Path):
        (tmp_path / "doc.txt").write_text("TXT content.", encoding="utf-8")
        (tmp_path / "doc.md").write_text("# Markdown content.", encoding="utf-8")

        docs = load_documents(tmp_path)

        assert len(docs) == 2

    def test_ignores_unsupported_files(self, tmp_path: Path):
        (tmp_path / "supported.txt").write_text("Good content.", encoding="utf-8")
        (tmp_path / "ignored.csv").write_text("col1,col2", encoding="utf-8")
        (tmp_path / "ignored.jpg").write_bytes(b"\xff\xd8")  # fake JPEG bytes

        docs = load_documents(tmp_path)

        # Only the .txt file should be loaded
        assert len(docs) == 1

    def test_raises_if_folder_not_found(self, tmp_path: Path):
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError):
            load_documents(nonexistent)

    def test_raises_if_folder_empty(self, tmp_path: Path):
        with pytest.raises(RuntimeError, match="No supported documents found"):
            load_documents(tmp_path)

    def test_continues_on_single_file_error(self, tmp_path: Path):
        """Even if one file fails, the others should still load."""
        (tmp_path / "good.txt").write_text("Good content here.", encoding="utf-8")
        # Create an unreadable file by making a directory with that name
        bad_dir = tmp_path / "bad.txt"
        bad_dir.mkdir()  # directory named "bad.txt" — read_text will fail

        # Should still return the good document
        docs = load_documents(tmp_path)

        assert any("Good content" in d["text"] for d in docs)


# ── Supported types check ─────────────────────────────────────────────────────

def test_supported_file_types_include_pdf_txt_md():
    """Verify our dispatcher handles the three required formats."""
    assert ".pdf" in LOADERS
    assert ".txt" in LOADERS
    assert ".md" in LOADERS
