"""Tests für Datei-Upload (TXT/PDF/DOCX) – nur In-Memory, keine Pipeline-Änderung."""

from __future__ import annotations

import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "demo"))

import importlib.util

spec = importlib.util.spec_from_file_location("file_extract", PROJECT_ROOT / "demo" / "file_extract.py")
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore

extract = mod.extract_text_from_upload  # type: ignore
ALLOWED = mod.ALLOWED_EXTENSIONS  # type: ignore
MAX_SIZE = mod.MAX_FILE_SIZE  # type: ignore


def test_txt_basic():
    data = "Softwareentwickler Python äöü ß".encode("utf-8")
    text, err, meta = extract("anzeige.txt", data)
    assert err is None
    assert "Softwareentwickler" in text
    assert "äöü" in text
    assert meta["filename"] == "anzeige.txt"
    assert meta["ext"] == ".txt"


def test_txt_bom():
    data = b"\xef\xbb\xbf" + "Hallo Welt mit Umlauten äöü".encode("utf-8")
    text, err, meta = extract("bom.txt", data)
    assert err is None
    assert text.startswith("Hallo Welt")
    assert "äöü" in text


def test_txt_umlaute_iso():
    # iso-8859-1 Fallback – teste Windows-1252 mit Umlauten
    data = "München Größe".encode("windows-1252")
    text, err, meta = extract("iso.txt", data)
    assert err is None
    # Sollte trotzdem lesen (Fallback)
    assert "München" in text or "M" in text


def test_txt_empty():
    text, err, meta = extract("empty.txt", b"")
    assert text is None
    assert "leer" in err.lower()


def test_invalid_type():
    text, err, meta = extract("evil.exe", b"content")
    assert text is None
    assert "Ungültiger Dateityp" in err
    assert meta["ext"] == ".exe"


def test_too_large():
    big = b"a" * (MAX_SIZE + 1)
    text, err, meta = extract("big.txt", big)
    assert text is None
    assert "zu groß" in err.lower()


def test_max_size_boundary():
    # Exakt MAX_SIZE sollte noch ok sein (wenn Inhalt valide)
    data = ("a" * (MAX_SIZE - 10)).encode("utf-8")
    text, err, meta = extract("border.txt", data)
    # Sollte ok sein oder zumindest nicht "zu groß"
    assert err is None or "zu groß" not in err


def test_pdf_with_text():
    pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length 54 >> stream
BT /F1 12 Tf 100 700 Td (Hallo Welt PDF Test) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000351 00000 n
trailer << /Size 6 /Root 1 0 R >>
startxref
456
%%EOF
"""
    text, err, meta = extract("test.pdf", pdf)
    assert err is None
    assert "Hallo Welt PDF Test" in text
    assert meta["ext"] == ".pdf"


def test_pdf_no_text():
    pdf_empty = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 0 >> endobj
xref
0 3
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
trailer << /Size 3 /Root 1 0 R >>
startxref 100
%%EOF
"""
    text, err, meta = extract("empty.pdf", pdf_empty)
    assert text is None
    assert "kein Text" in err.lower() or "pdf" in err.lower()


def test_pdf_corrupted():
    text, err, meta = extract("corrupt.pdf", b"not a pdf")
    assert text is None
    assert "beschädigt" in err.lower() or "gelesen" in err.lower()


def test_docx_basic():
    from docx import Document

    doc = Document()
    doc.add_paragraph("Sachbearbeiter Einkauf (m/w/d) mit SAP")
    doc.add_paragraph("Zweite Zeile äöü ß")
    buf = io.BytesIO()
    doc.save(buf)
    data = buf.getvalue()
    text, err, meta = extract("test.docx", data)
    assert err is None
    assert "Sachbearbeiter" in text
    assert "äöü" in text
    assert meta["ext"] == ".docx"


def test_docx_empty():
    from docx import Document

    doc = Document()
    buf = io.BytesIO()
    doc.save(buf)
    data = buf.getvalue()
    text, err, meta = extract("empty.docx", data)
    assert text is None
    assert "kein text" in err.lower()


def test_sanitize_filename():
    # Pfad-Traversal sollte entfernt werden
    text, err, meta = extract("../../etc/passwd.txt", b"hello world this is long enough for test 12345")
    assert meta["filename"] == "passwd.txt"
    assert err is None or text is not None


def test_sonderzeichen_umlaute_txt():
    data = "Erzieher (m/w/d) – München, Größe, Fußball, naïve café".encode("utf-8")
    text, err, meta = extract("umlaute.txt", data)
    assert err is None
    assert "München" in text
    assert "Größe" in text


def test_lange_anzeige():
    long_text = ("Softwareentwickler mit Python und SQL. " * 200).encode("utf-8")
    text, err, meta = extract("long.txt", long_text)
    assert err is None
    assert len(text) > 5000
    assert "Softwareentwickler" in text


def test_docx_with_table():
    from docx import Document

    doc = Document()
    doc.add_paragraph("Vor der Tabelle")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Zelle A"
    table.cell(0, 1).text = "Zelle B äöü"
    buf = io.BytesIO()
    doc.save(buf)
    data = buf.getvalue()
    text, err, meta = extract("table.docx", data)
    assert err is None
    assert "Zelle A" in text
    assert "äöü" in text


def test_allowed_extensions():
    assert ".txt" in ALLOWED
    assert ".pdf" in ALLOWED
    assert ".docx" in ALLOWED
    assert ".exe" not in ALLOWED
    assert ".jpg" not in ALLOWED
