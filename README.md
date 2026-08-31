# Information Extraction in Python 🐍

Course materials for the **Information Extraction in Python** seminar.

---

## 🛠️ Setup (do this once)

### 1. Install `uv`

`uv` is a fast Python package manager. Install it with one command:

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal after installing, then verify:
```bash
uv --version
```

---

### 2. Clone the repository

```bash
git clone https://github.com/LTluttmann/ie_course_material.git
cd ie_course_material
```

---

### 3. Create the environment & install dependencies

```bash
uv sync
```

This will:
- Create a virtual environment in `.venv/`
- Install all dependencies from `pyproject.toml`
- Install dev tools (pytest, ruff, etc.)

No need to manually `pip install` anything.

---

### 4. Download required NLP models

Run the setup script to download spaCy models and NLTK data:

```bash
uv run python scripts/download_models.py
```

---

### 5. Activate the environment (optional)

`uv run` handles this automatically, but if you want a traditional shell activation:

**macOS / Linux:**
```bash
source .venv/bin/activate
```

**Windows:**
```powershell
.venv\Scripts\activate
```

---

## 📓 Running Notebooks

```bash
uv run jupyter lab
```

Notebooks are in the `notebooks/` directory.

---

## ✅ Verify your setup

```bash
uv run python scripts/check_setup.py
```

All checks should show ✅.

---

## 🗂️ Repository Structure

```
ie_course_material/
├── pyproject.toml          # Dependencies & project config
├── notebooks/              # Lecture notebooks (01_, 02_, ...)
├── exercises/              # Starter code for exercises
├── solutions/              # Exercise solutions (released weekly)
├── src/
│   └── ie_course/          # Shared helper library
│       ├── __init__.py
│       └── utils.py
├── data/                   # data we might use
└── scripts/
    ├── check_setup.py      # Environment verification
    └── download_models.py  # Model downloader
```

---

## 🔑 API Keys (OPTIONAL)
NOTE: we are working on a solution to use LLMs running on universiy hardware.

Some exercises use LLM APIs. Set your keys as environment variables:


```bash
# macOS / Linux — add to ~/.zshrc or ~/.bashrc
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY = "sk-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Or create a `.env` file in the project root (already in `.gitignore`):
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 🔄 Updating dependencies

If new packages are added during the course, just run:
```bash
uv sync
```

---

## 🖥️ Demo UI — Job Information Extractor

Professionelle Demo-Oberfläche für die bestehende Information-Extraction-Pipeline (LLM, KISSKI).

**Funktion:** Stellenanzeige einfügen → *Analysieren* → 7 Entitätstypen als Chips + JSON + markierter Text.

Die UI nutzt ausschließlich die vorhandene Pipeline (`src/ie_course/kisski_client.py`,
`scripts/evaluate_llm_baseline.py` – strict JSON-Prompt, `src/ie_course/retrieval.py`,
`src/ie_course/bio.py`). Keine wissenschaftliche Pipeline wurde verändert; die UI ist eine reine Präsentationsschicht.

### Start (einfach, ohne neue Abhängigkeiten)

```bash
# 1. Umgebung aktivieren (oder uv run verwenden)
source .venv/bin/activate
# Alternativ: .venv/bin/python verwenden

# 2. API-Konfiguration setzen (siehe .env.example)
cp .env.example .env
# → KISSKI_API_KEY, KISSKI_BASE_URL, KISSKI_MODEL eintragen
# .env wird nie committet (in .gitignore)

# 3. UI starten (Standard: http://127.0.0.1:8000)
.venv/bin/python demo/app.py
# oder mit uv:
# uv run python demo/app.py
# eigener Port:
# .venv/bin/python demo/app.py --port 8501 --host 127.0.0.1
```

Nach dem Start erscheint ein Link in der Konsole. Browser öffnen.

### Bedienung

1. Link öffnen (z. B. `http://127.0.0.1:8000`)
2. **Beispiel** als Karte wählen (Software, Pflege, Kaufmännisch) – oder eigene Anzeige einfügen:
   - **Datei hochladen:** `Datei hierher ziehen oder auswählen` → PDF/TXT/DOCX (max. 8 MB, Drag & Drop) → Text wird extrahiert und erscheint im Editor
   - **Text einfügen:** direkt in den Editor tippen/einfügen (`Einfügen`/`⌘V`)
3. **Stellenanzeige analysieren** drücken (ehrlicher Loading-State *Stellenanzeige wird analysiert …*, Editor deaktiviert)
4. Dashboard erscheint unter dem Editor:
   - **7 Entity-Cards** mit deutscher Beschreibung, englischem Key, Count und Chips (leere Typen: *Keine Entität erkannt*)
   - **Markierter Originaltext** als zentrales Highlight – exakte `start`/`end`-Spans, dezente Hervorhebungen, interaktive Legende (Typen ein-/ausblenden), *Alle ausblenden*, *Text kopieren*
   - **Technische Ansicht** (kollabierbar) → unverändertes Pipeline-JSON, `Kopieren` + `Download`, validiert
5. Bei Bedarf *Leeren* oder anderes Beispiel laden. Hochgeladene Datei kann via *Entfernen* ausgeblendet werden – Text bleibt editierbar.

Hinweise:
- Leere/zu kurze (<20) / zu lange (>20k) Eingaben → verständliche Fehlermeldung, kein Traceback.
- **Datei-Upload:** nur `.txt`, `.pdf`, `.docx` (max. 8 MB), keine dauerhafte Speicherung, kein externer Versand vor *Analysieren*, Dateiname/Größe werden angezeigt, Fehler wie *„Aus dieser PDF konnte kein Text extrahiert werden“* als Banner.
- Fehlende `.env`-Konfiguration → 503-Banner, kein Secret im Frontend.
- API-Fehler (401/429/500/Timeout) abgefangen, `429/500` mit automatischem Retry (exponentielles Backoff), sonst Banner.
- Halluzinierte/ambiguous Spans bleiben im JSON sichtbar, werden aber nicht markiert – keine falschen Markierungen.

### Architektur (kurz)

```
demo/
  app.py            # ThreadingHTTPServer (stdlib), dient static/ + POST /api/extract + POST /api/upload
  extractor.py      # Wrapper um ie_course.kisski_client + strict Prompt + Normalisierung (retry)
  file_extract.py   # UX-Erweiterung: TXT/PDF/DOCX → Text (pypdf, python-docx, bereits in pyproject)
  examples.py       # 3 synthetische, PII-freie Beispiel-Anzeigen
  static/
    index.html      # Premium SaaS – Hero, Example-Cards, Upload-Zone (Drag&Drop), Editor, Dashboard
    style.css       # Ruhig/seriös: viel Whitespace, Karten, subtile Shadows, gute Typografie, Upload-Styles
    app.js          # Fetch, Upload, States, Entity-Cards, Highlighting, Legende, Copy/Download, A11y
```

Keine neuen Pflicht-Abhängigkeiten – `pypdf` und `python-docx` waren bereits in `pyproject.toml`. `demo/file_extract.py` und `demo/app.py:/api/upload` sind reine Input-Erweiterungen, keine zweite NLP-Pipeline.

### Fehlerbehandlung & Secrets

- `.env` nie committen, nie im Frontend oder Logs ausgeben. Upload-Dateien nie speichern, nie loggen.
- Endpunkte: `GET /health`, `GET /api/config` (ohne Key), `GET /api/examples`, `POST /api/extract`, `POST /api/upload` (multipart).
- Input-Guards: leer, zu kurz, zu lang (>20k), ungültiges JSON, Timeouts. Upload-Guards: ungültiger Typ, zu groß (>8 MB), leer, kein Text, beschädigt.

### Tests

```bash
.venv/bin/python -m pytest -q --no-cov
# erwartet: 210 passed (183 original + 10 Demo-Parsing + 17 Upload)
```

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `uv: command not found` | Restart your terminal after install |
| `ModuleNotFoundError` | Run `uv sync` then `uv run python ...` |
| Jupyter kernel issues | `uv run python -m ipykernel install --user` |
| spaCy model missing | `uv run python scripts/download_models.py spacy` |
| Slow `uv sync` on first run | Normal — it's downloading ~2 GB of ML libraries |
| Demo zeigt „API nicht konfiguriert“ | `.env` nach `.env.example` einrichten und Server neu starten |
| Demo 429/500 | KISSKI ist temporär überlastet – 1–2× erneut *Analysieren* drücken (Auto-Retry) |

