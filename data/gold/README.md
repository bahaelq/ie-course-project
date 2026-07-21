# Gold Set

**Zweck:** Separat annotierte Stellenanzeigen ausschließlich für die Evaluation.

**Geplant:** 20–30 Anzeigen

**Struktur:**
- `texts/` – Rohtext der Stellenanzeigen (`.txt`, UTF-8)
- `annotations/` – Gold-Standard-Annotationen (`.json`, identischer Dateiname wie Text)

**Kriterien:**
- Keine Überschneidung mit `data/example_pool/` oder `data/smoke_test/`
- Stabile eindeutige IDs pro Datei
- Nur die sieben erlaubten Entitätstypen: JOB_TITLE, HARD_SKILL, SOFT_SKILL, EXPERIENCE, EDUCATION, LANGUAGE, WORK_MODE
