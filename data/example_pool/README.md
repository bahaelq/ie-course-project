# Example Pool

**Zweck:** Manuell annotierte Stellenanzeigen für Few-Shot-Retrieval.

**Geplant:** 15–20 Anzeigen

**Struktur:**
- `texts/` – Rohtext der Stellenanzeigen (`.txt`, UTF-8)
- `annotations/` – Gold-Standard-Annotationen (`.json`, identischer Dateiname wie Text)

**Kriterien:**
- Keine Überschneidung mit `data/gold/` oder `data/smoke_test/`
- Stabile eindeutige IDs pro Datei
- Nur die sieben erlaubten Entitätstypen: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE
