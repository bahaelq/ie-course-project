# Data Collection Protocol

## Ziel

Kontrolliertes Sammeln und Importieren realer deutscher Stellenanzeigen
für die Information-Extraction-Forschung. Sämtliche Daten werden lokal
gespeichert, versioniert und ohne externe API-Aufrufe verarbeitet.

## Erlaubte Quellen

- Öffentlich zugängliche Jobbörsen (z. B. StepStone, Indeed, BA,
  Monster, LinkedIn)
- Unternehmenswebseiten mit frei sichtbaren Stellenanzeigen
- Von Kursleitern bereitgestellte Beispielanzeigen

## Verbotene Daten

- Personenbezogene Kontaktdaten (Name, E‑Mail, Telefon, Anschrift)
  werden nach Möglichkeit entfernt oder pseudonymisiert
- Keine Bewerberdaten (Lebensläufe, Anschreiben, Zeugnisse)
- Keine nicht-öffentlichen oder hinter Paywalls gesperrten Anzeigen

## Erlaubte Eingabeformate

- **Reine Textdateien** (`.txt`, UTF‑8)
- Die Anzeige wird als durchgehender Fließtext mit maximal einem
  abschließenden Zeilenumbruch gespeichert
- Zeilenumbrüche innerhalb der Anzeige werden beim Import durch
  Leerzeichen ersetzt (keine inhaltliche Veränderung)

## Speicherung

Jede Anzeige wird gespeichert unter:

    data/<split>/texts/<id>.txt

Die Textdatei enthält:

- Nur den sichtbaren Text der Stellenanzeige
- Keine Metadaten, kein HTML, kein Markdown
- Keine Formatierung außer maximal einem abschließenden `\n`
- UTF-8-Kodierung

Zur Laufzeit wird pro Anzeige eine Metadatenzeile in

    data/<split>/metadata.jsonl

ergänzt. Metadaten werden nicht in die Textdatei geschrieben.

## Metadatenstruktur

Jede JSONL-Zeile enthält:

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `id` | str | Eindeutige ID (`job_ad_XXXX`) |
| `split` | str | Einer von `example_pool`, `gold`, `unlabeled` |
| `source_name` | str | Name der Quelle (z. B. `StepStone`) |
| `source_url` | str | Vollständige URL der Anzeige |
| `retrieved_at` | str | Abrufdatum im ISO-Format (`YYYY-MM-DD`) |
| `job_title_original` | str | Originale Stellenbezeichnung |
| `company_anonymized` | str | Unternehmen (leerbar oder anonymisiert) |
| `notes` | str | Optionale Notizen |

## Splits und Überschneidungsverbot

- **Example Pool** (15–20 Anzeigen): Manuell annotiert für Few-Shot-Retrieval
- **Gold Set** (20–30 Anzeigen): Separat annotiert, nur für Evaluation
- **Unlabeled Corpus** (≥50 Anzeigen): Ohne Annotation, für Weak Labeling

Ein identischer Anzeigentext darf nicht in mehreren Splits vorkommen.
Eine ID darf nicht in mehreren Splits vorkommen.
Eine URL darf nicht in mehreren Splits vorkommen.

## Import-Workflow

1. Anzeigentext als `.txt` lokal speichern (Quelle und Datum notieren)
2. Personenbezogene Kontaktdaten entfernen
3. Import mit `scripts/import_job_ad.py`:

       python scripts/import_job_ad.py \
           --input /pfad/zur/anzeige.txt \
           --split <split> \
           --id job_ad_XXXX \
           --source-name "<Quelle>" \
           --source-url "<URL>" \
           --retrieved-at YYYY-MM-DD

4. Bei Bedarf Annotation manuell erstellen und im Split ablegen

Das Import-Skript prüft Duplikate, kodiert UTF-8, normalisiert
Zeilenumbrüche und erstellt die Metadaten. Es überschreibt niemals
vorhandene Dateien und hinterlässt bei Fehlern keine halbfertigen Dateien.
