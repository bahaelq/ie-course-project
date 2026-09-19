# IE Course Project: Job Ad Information Extraction

This repository contains a small Python information-extraction system for German
job advertisements. It provides a Streamlit app, reusable extraction modules,
annotated example data, and scripts to train and evaluate a local GBERT
token-classification model.

The main use case is to turn unstructured job ads into structured entities such
as job titles, hard skills, soft skills, experience requirements, education,
languages, and work mode.

## What the Code Does

The project supports two extraction paths:

1. **Streamlit job-ad analyzer**
   - Accepts pasted text, uploaded TXT, PDF, and DOCX files, or a link to a
     public job posting.
   - Optionally accepts a CV upload and asks the configured language model whether
     the CV is a good fit for the job.
   - Uses a local GBERT model, when available, to propose entity spans.
   - Sends the job ad and candidates to an OpenAI-compatible chat API for strict
     JSON structuring.
   - Displays grouped entities, highlighted source text, diagnostics, and a JSON
     download.

2. **Local GBERT training and evaluation**
   - Fine-tunes `deepset/gbert-base` with `scripts/train_gbert.py`.
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

The Streamlit app needs an OpenAI-compatible chat API. Copy the
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
- paste a link to a public job posting and load its text with **Load from link**,
- run extraction into the seven supported entity types,
- inspect highlighted spans and the raw JSON response,
- download the JSON result,
- optionally upload a CV and get a short fit assessment.

If `artifacts/gbert_model/model.safetensors` exists, the app uses the local
GBERT model to propose candidate spans before the LLM call. If the model is not
present, the app still works using only the configured LLM.

## Train the Local GBERT Model

The model weights are not stored in git, so train the model once before using
it (a GPU is used automatically if available; the first run downloads
`deepset/gbert-base`):

```bash
uv run python scripts/train_gbert.py
```

This fine-tunes GBERT on `data/example_pool/` and writes the model, including
`model.safetensors`, to `artifacts/gbert_model/`.

## Evaluate the Local GBERT Model

Run evaluation on the held-out gold split:

```bash
uv run python scripts/experiments/evaluate_gbert.py --model-dir artifacts/gbert_model --split gold
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `uv: command not found` | Install `uv` and restart the terminal. |
| `ModuleNotFoundError: ie_course` | Run commands through `uv run` from the project root. |
| Missing API configuration in Streamlit | Copy `.env.example` to `.env` and set the provider, key, and model. |
| API errors such as 401/403 | Check the configured API key and model name. |
| API error 429 | Wait briefly and retry; the provider rate limit was reached. |
| No GBERT model found | Run `uv run python scripts/train_gbert.py`. Without it the app still runs with the LLM only. |
| "Could not load the page" or "too little text" | The site blocks downloads or needs JavaScript/login. Copy the job text and paste it into the Job Ad box. |
| PDF upload has no text | Use a text-based PDF, TXT, or DOCX file, or paste the text manually. |
