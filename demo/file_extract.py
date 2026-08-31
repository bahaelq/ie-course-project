"""Datei-Upload Text-Extraktion – ausschließlich UX-Erweiterung, keine NLP-Pipeline.

Unterstützt TXT, PDF, DOCX via bereits vorhandener Dependencies (pypdf, python-docx).
Keine Datei wird gespeichert, kein externer Aufruf, nur In-Memory-Verarbeitung.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Final

# Konfiguration – muss mit app.py synchron sein
ALLOWED_EXTENSIONS: Final[set[str]] = {".txt", ".pdf", ".docx"}
MAX_FILE_SIZE: Final[int] = 8 * 1024 * 1024  # 8 MB – sinnvoll für Stellenanzeigen (typisch <500KB)
MIN_TEXT_LENGTH: Final[int] = 20  # wie extractor.py

# Fehlermeldungen – professionell, deutsch, wie im Auftrag vorgegeben
ERROR_MESSAGES: Final[dict[str, str]] = {
    "invalid_type": "Ungültiger Dateityp. Erlaubt sind PDF, TXT und DOCX.",
    "too_large": "Datei zu groß. Maximale Größe: 8 MB.",
    "no_text": "Aus dieser Datei konnte kein Text extrahiert werden. Bitte verwende eine textbasierte Datei oder füge den Text manuell ein.",
    "pdf_no_text": "Aus dieser PDF konnte kein Text extrahiert werden. Bitte verwende eine textbasierte PDF oder füge den Text manuell ein.",
    "corrupted": "Datei konnte nicht gelesen werden. Die Datei ist möglicherweise beschädigt oder kein gültiges Format.",
    "empty": "Datei ist leer.",
}


def _sanitize_filename(name: str) -> str:
    """Entfernt Pfadanteile, behält nur Basisnamen, limitiert Länge."""
    # Nur Basisnamen, keine Verzeichnisse
    base = Path(name).name
    # Entferne problematische Zeichen, behalte aber Umlaute/Unicode
    base = base.strip()
    if not base:
        return "upload"
    # Kürzen
    if len(base) > 100:
        ext = Path(base).suffix
        base = base[: 100 - len(ext)] + ext
    return base


def _extract_txt(data: bytes) -> str:
    """TXT mit robustem Encoding-Handling (Umlaute!)."""
    # Versuche UTF-8 (mit/ohne BOM), dann ISO-8859-1 als Fallback
    for enc in ("utf-8-sig", "utf-8", "iso-8859-1", "windows-1252"):
        try:
            text = data.decode(enc)
            # Normalisiere nur \r\n → \n, behalte sonst alles
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            return text.strip()
        except UnicodeDecodeError:
            continue
    # Letzter Fallback: utf-8 mit replace
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_pdf(data: bytes) -> tuple[str | None, str | None]:
    """PDF via pypdf. Returns (text, error_key)."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return None, "corrupted"

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return None, "corrupted"

    # Verschlüsselt?
    try:
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return None, "corrupted"
    except Exception:
        pass

    # Keine Seiten?
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

    # Zusammenfügen, normalisieren, aber keine NLP-Veränderung
    text = "\n\n".join(p.strip() for p in parts if p.strip())
    # Bereinige übermäßige Leerzeilen, behalte Absätze
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if not text:
        return None, "pdf_no_text"
    if len(text) < MIN_TEXT_LENGTH:
        # Zu wenig Text gilt als kein extrahierbarer Inhalt
        # Aber wir geben ihn trotzdem zurück, Frontend validiert später
        # Für Konsistenz: wenn <20 Zeichen, trotzdem zurück, aber Frontend zeigt Hinweis
        pass
    return text, None


def _extract_docx(data: bytes) -> tuple[str | None, str | None]:
    """DOCX via python-docx."""
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
    # Auch Tabellen
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
    """Hauptfunktion für Upload. Validiert und extrahiert.

    Returns (text, error_message, meta). Bei Erfolg ist error_message None.
    Meta enthält filename, size, ext für UI.
    """
    safe_name = _sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()
    size = len(data)

    meta = {
        "filename": safe_name,
        "size": size,
        "ext": ext,
        "size_human": _human_size(size),
    }

    # 1. Typ prüfen
    if ext not in ALLOWED_EXTENSIONS:
        return None, ERROR_MESSAGES["invalid_type"], meta

    # 2. Größe prüfen
    if size > MAX_FILE_SIZE:
        return None, ERROR_MESSAGES["too_large"], meta

    if size == 0:
        return None, ERROR_MESSAGES["empty"], meta

    # 3. Extraktion je Typ
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
        return f"{n/1024:.1f} KB"
    return f"{n/(1024*1024):.1f} MB"


# Für Tests: direkte Funktionen exportieren
__all__ = [
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_SIZE",
    "ERROR_MESSAGES",
    "extract_text_from_upload",
]
