from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Final

# Validation for uploaded files
ALLOWED_EXTENSIONS: Final[set[str]] = {".txt", ".pdf", ".docx"}
MAX_FILE_SIZE: Final[int] = 8 * 1024 * 1024  # 8 MB is enough for typical job ads.

# User-facing upload error messages
ERROR_MESSAGES: Final[dict[str, str]] = {
    "invalid_type": "Invalid file type. PDF, TXT, and DOCX are supported.",
    "too_large": "The file is too large. Maximum size: 8 MB.",
    "no_text": "No text could be extracted from this file. Use a text-based file or paste the text manually.",
    "pdf_no_text": "No text could be extracted from this PDF. Use a text-based PDF or paste the text manually.",
    "corrupted": "The file could not be read. It may be corrupted or not a valid format.",
    "empty": "The file is empty.",
}


def _sanitize_filename(name: str) -> str:
    # Keep only the base name, never directories.
    base = Path(name).name
    # Strip problematic whitespace while preserving Unicode in file names.
    base = base.strip()
    if not base:
        return "upload"
    # Shorten very long names.
    if len(base) > 100:
        ext = Path(base).suffix
        base = base[: 100 - len(ext)] + ext
    return base


def _extract_txt(data: bytes) -> str:
    # Try UTF-8 first, then common Western encodings as fallback.
    for enc in ("utf-8-sig", "utf-8", "iso-8859-1", "windows-1252"):
        try:
            text = data.decode(enc)
            # Normalize line endings only.
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            return text.strip()
        except UnicodeDecodeError:
            continue
    # Final fallback: UTF-8 with replacement characters.
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_pdf(data: bytes) -> tuple[str | None, str | None]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return None, "corrupted"

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return None, "corrupted"

    # Encrypted?
    try:
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return None, "corrupted"
    except Exception:
        pass

    # No pages?
    if not reader.pages:
        return None, "pdf_no_text"

    parts: list[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt:
            parts.append(txt)

    if not parts:
        return None, "pdf_no_text"

    # Join and normalize without changing the text content.
    text = "\n\n".join(p.strip() for p in parts if p.strip())
    # Collapse excessive blank lines, preserving paragraphs.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if not text:
        return None, "pdf_no_text"
    return text, None


def _extract_docx(data: bytes) -> tuple[str | None, str | None]:
    try:
        from docx import Document  # type: ignore
    except ImportError:
        return None, "corrupted"

    try:
        doc = Document(io.BytesIO(data))
    except Exception:
        return None, "corrupted"

    parts = []
    for para in doc.paragraphs:
        txt = para.text or ""
        if txt.strip():
            parts.append(txt.strip())
    # Also include tables.
    try:
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    txt = cell.text or ""
                    if txt.strip():
                        parts.append(txt.strip())
    except Exception:
        pass

    if not parts:
        return None, "no_text"

    text = "\n".join(parts).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not text:
        return None, "no_text"
    return text, None


def extract_text_from_upload(filename: str, data: bytes) -> tuple[str | None, str | None, dict]:
    
    safe_name = _sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()
    size = len(data)

    meta = {
        "filename": safe_name,
        "size": size,
        "ext": ext,
        "size_human": _human_size(size),
    }

    # 1. Check type.
    if ext not in ALLOWED_EXTENSIONS:
        return None, ERROR_MESSAGES["invalid_type"], meta

    # 2. Check size.
    if size > MAX_FILE_SIZE:
        return None, ERROR_MESSAGES["too_large"], meta

    if size == 0:
        return None, ERROR_MESSAGES["empty"], meta

    # 3. Extract by type.
    if ext == ".txt":
        text = _extract_txt(data)
        if not text:
            return None, ERROR_MESSAGES["no_text"], meta
        return text, None, meta

    if ext == ".pdf":
        text, err_key = _extract_pdf(data)
        if err_key:
            return None, ERROR_MESSAGES.get(err_key, ERROR_MESSAGES["corrupted"]), meta
        assert text is not None
        return text, None, meta

    if ext == ".docx":
        text, err_key = _extract_docx(data)
        if err_key:
            return None, ERROR_MESSAGES.get(err_key, ERROR_MESSAGES["corrupted"]), meta
        assert text is not None
        return text, None, meta

    return None, ERROR_MESSAGES["invalid_type"], meta


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


# Export direct functions for tests.
__all__ = [
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_SIZE",
    "ERROR_MESSAGES",
    "extract_text_from_upload",
]
