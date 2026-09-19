# IE Course Project: Job Ad Information Extraction

This repository contains a small Python information-extraction system for German
job advertisements. It provides a Streamlit app, reusable extraction modules,
annotated example data, and an evaluation script for a local GBERT
token-classification model.

The main use case is to turn unstructured job ads into structured entities such
as job titles, hard skills, soft skills, experience requirements, education,
languages, and work mode.

## What the Code Does

The project supports two extraction paths:

1. **Streamlit job-ad analyzer**
   - Accepts pasted text or uploaded TXT, PDF, and DOCX files.
   - Optionally accepts a CV upload and asks the configured language model whether
     the CV is a good fit for the job.
   - Uses a local GBERT model, when available, to propose entity spans.
   - Sends the job ad and candidates to an OpenAI-compatible chat API for strict
     JSON structuring.
   - Displays grouped entities, highlighted source text, diagnostics, and a JSON
     download.

2. **Local GBERT evaluation**
   - Loads a fine-tuned German BERT token-classification model from
     `artifacts/gbert_model/`.
   - Runs entity prediction over an annotated data split.
   - Writes predictions and precision/recall/F1 metrics to `artifacts/`.

The allowed entity types are:

- `JOB_TITLE`
- `HARD_SKILL`
- `SOFT_SKILL`
- `EXPERIENCE`
- `EDUCATION`
- `LANGUAGE`
- `WORK_MODE`

## Project Structure

```text
.
|-- streamlit_app.py                  # Web UI for job-ad extraction and CV matching
|-- pyproject.toml                    # Python dependencies and project metadata
|-- uv.lock                           # Locked dependency versions for uv
|-- .env.example                      # API configuration template
|-- src/ie_course/
|   |-- extractor.py                  # Main extraction and CV-matching workflow
|   |-- strict_json.py                # Prompt/schema rules and span normalization
|   |-- llm_client.py                 # OpenAI-compatible API configuration/client helpers
|   |-- file_extract.py               # TXT/PDF/DOCX text extraction for uploads
|   |-- gbert_infer.py                # Local GBERT inference
|   |-- gbert_data.py                 # Loading annotated data splits
|   |-- metrics.py                    # Entity-level evaluation metrics
|   |-- examples.py                   # Built-in UI examples
|   |-- job_url.py                    # CLI extractor for job postings at URLs
|   `-- ocr.py                        # OCR helper code
|-- scripts/experiments/
|   `-- evaluate_gbert.py             # Evaluate local GBERT predictions
|-- data/
|   |-- examples/                     # Small built-in examples and gold annotations
|   |-- smoke_test/                   # Tiny test split
|   |-- example_pool/                 # Manually annotated validation/few-shot pool
|   `-- gold/                         # Held-out manually annotated evaluation set
|-- exercises/
|   `-- 01_exercise.ipynb             # Course exercise notebook
`-- artifacts/
    |-- gbert_model/                  # Local fine-tuned model files
    `-- gbert_eval_gold/              # Existing evaluation outputs
```

## Setup

The project uses Python 3.11+ and `uv`.

Install `uv` if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install dependencies:

```bash
uv sync
```

This creates `.venv/` and installs the dependencies from `pyproject.toml` and
`uv.lock`.

## API Configuration

The Streamlit app and URL extractor need an OpenAI-compatible chat API. Copy the
template and fill in one provider:

```bash
cp .env.example .env
```

For AcademicCloud Chat AI:

```dotenv
AI_PROVIDER=academiccloud
CHAT_AI_API_KEY=your-chat-ai-api-key
CHAT_AI_MODEL=qwen3.5-122b-a10b
```

For OpenAI:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
```

Environment variables override values in `.env`. API keys are read locally and
are not displayed by the app.

## Run the Streamlit App

```bash
uv run streamlit run streamlit_app.py
```

Streamlit prints a local URL, usually `http://localhost:8501`.

In the app you can:

- choose one of the built-in sample job ads,
- paste a job ad directly,
- upload a TXT, PDF, or DOCX job ad up to 8 MB,
- run extraction into the seven supported entity types,
- inspect highlighted spans and the raw JSON response,
- download the JSON result,
- optionally upload a CV and get a short fit assessment.

If `artifacts/gbert_model/model.safetensors` exists, the app uses the local
GBERT model to propose candidate spans before the LLM call. If the model is not
present, the app still works using only the configured LLM.

## Evaluate the Local GBERT Model

Run evaluation on the held-out gold split:

```bash
uv run python scripts/experiments/evaluate_gbert.py --model-dir artifacts/gbert_model --split gold
```

Useful alternatives:

```bash
uv run python scripts/experiments/evaluate_gbert.py --split example_pool
uv run python scripts/experiments/evaluate_gbert.py --split smoke_test
```

The script writes:

- `artifacts/gbert_eval_<split>/predictions.json`
- `artifacts/gbert_eval_<split>/metrics.json`

Matching is entity-level and offset-based: a prediction is correct only when
document id, entity type, start offset, and end offset match the annotation.

## Extract a Job Posting from a URL

The URL helper downloads a public page, removes scripts/styles/navigation/footer
content, truncates the visible text, and asks the configured LLM for structured
job fields:

```bash
uv run python -m ie_course.job_url https://example.com/jobs/123
```

This command requires a configured `.env`.

## Data

The repository contains several local data splits:

- `data/examples/`: small examples used by the UI and course material.
- `data/smoke_test/`: tiny annotated split for quick checks.
- `data/example_pool/`: manually annotated validation/few-shot pool.
- `data/gold/`: held-out annotated evaluation set.

Annotated splits follow the same structure:

```text
data/<split>/
|-- texts/
|   `-- job_ad_XXXX.txt
|-- annotations/
|   `-- job_ad_XXXX.json
`-- metadata.jsonl
```

## Notes and Limitations

- The Streamlit app sends job-ad text to the configured LLM only after clicking
  **Analyze Job Ad**.
- Uploaded files are read in memory by the app; they are not saved permanently by
  the upload workflow.
- Local GBERT inference is offline once `artifacts/gbert_model/` exists.
- The LLM is instructed to copy exact spans from the job ad. Values that cannot
  be found in the original text, or that occur ambiguously, are counted in the
  technical diagnostics and are not highlighted.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `uv: command not found` | Install `uv` and restart the terminal. |
| `ModuleNotFoundError: ie_course` | Run commands through `uv run` from the project root. |
| Missing API configuration in Streamlit | Copy `.env.example` to `.env` and set the provider, key, and model. |
| API errors such as 401/403 | Check the configured API key and model name. |
| API error 429 | Wait briefly and retry; the provider rate limit was reached. |
| No GBERT model found | The app can still run with the LLM only, or place model files in `artifacts/gbert_model/`. |
| PDF upload has no text | Use a text-based PDF, TXT, or DOCX file, or paste the text manually. |
