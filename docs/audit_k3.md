# P0 Audit k=3 — Read-Only Analyse

**Datum:** 2026-08-24  
**Modell:** `meta-llama-3.1-8b-instruct` via `https://chat-ai.academiccloud.de/v1`  
**Temperatur:** `0.0` für alle Runs  
**Splits:** `example_pool 5` (`job_ad_1001-1005`) als Retrieval-Pool, `gold 5` (`job_ad_1006-1010`) als Pilot-Test (40 Entities)  
**Artefakte geprüft:** `artifacts/llm_baseline_gold/`, `artifacts/llm_baseline_gold_reparsed/` (offline 0 API, gleiche Raw Outputs), `artifacts/llm_baseline_gold_corrected/`, `artifacts/llm_fewshot_gold_k1/`, `artifacts/llm_fewshot_gold_k2/` (`artifacts/llm_fewshot_gold/`), `artifacts/llm_fewshot_gold_k3/`, `src/ie_course/retrieval.py`, `scripts/evaluate_llm_baseline.py`, `scripts/evaluate_llm_fewshot.py`, `scripts/check_dataset_splits.py`

## 1. Leakage-Check

**Kein Leakage.**

* Pool-IDs: `1001,1002,1003,1004,1005` (StepStone Hamburg, `data/example_pool/metadata.jsonl`)
* Gold-IDs: `1006 (DIENES), 1007,1008,1009,1010` (StepStone Hamburg + DIENES, `data/gold/metadata.jsonl`)
* `src/ie_course/retrieval.py:58` `if gold_id in pool_ids: raise ValueError` — kein Fehler geworfen in allen Runs
* `retrieval.json` Top-k je Query:
  * `1006: 1003 (0.457), 1005 (0.409) [,1002 (0.383) bei k=3]`
  * `1007: 1005 (0.452), 1003 (0.446)`
  * `1008: 1005 (0.501), 1003 (0.484)`
  * `1009: 1003 (0.388), 1002 (0.345)`
  * `1010: 1003 (0.490), 1005 (0.472)`
* Kein `gold` je als Retrieval-Ergebnis, alle Hits ∈ `{1002,1003,1005}`. `1001,1004` nie gerankt — TF-IDF Bias, aber kein Leakage.

## 2. Fairness k=1/2/3

* **Nur `k` variiert.** Modell, Temperatur, Sampling, Gold-Texte, Evaluationslogik `scripts/evaluate_llm_baseline.py:177` `compute_metrics` Exact-Match `(type,start,end)` identisch. `parse_args` `--k` deterministisch, `retrieve_for_queries` sortiert `(-score, id)` — Tie-Break deterministisch.
* `max_tokens` JSON `400` vs Few-Shot `600`, Marker `800` vs `1200` — minimaler Unterschied, fair.
* **Historischer vs korrigierter Baseline:** `llm_baseline_gold` JSON `F1 0.319` identisch zu `llm_baseline_gold_reparsed` JSON `0.319` (0 neue API, gleiche Raw Outputs, nur Parser partiell). Korrigierter API-Run `llm_baseline_gold_corrected` JSON `0.370` enthält Run-Varianz — für fairen Vergleich muss **reparsed** verwendet werden.

## 3. Vergleich k=1/2/3 (JSON primär, Gold n=5)

| Variante | JSON P | JSON R | JSON F1 | Marker P | Marker R | Marker F1 | API |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline historisch | 0.278 | 0.375 | 0.319 | 0.000 | 0.000 | 0.000 | 10 |
| Baseline reparsed (fair) | 0.278 | 0.375 | **0.319** | 0.042 | 0.100 | **0.059** | 0 |
| Few-Shot k=1 | 0.355 | 0.275 | 0.310 | 0.385 | 0.250 | 0.303 | 10 |
| Few-Shot k=2 | 0.371 | 0.325 | 0.347 | 0.429 | 0.075 | 0.128 | 10 |
| Few-Shot k=3 | **0.636** | **0.525** | **0.575** | 0.087 | 0.050 | 0.063 | 10 |
| Strict Baseline | 0.241 | 0.350 | 0.286 | 0.052 | 0.075 | 0.061 | 10 |

`Δ vs reparsed:` `k=1 -0.009`, `k=2 +0.028`, `k=3 +0.256`.

## 4. Ursache k=3-Sprung 0.319→0.575

* **Verteilt, nicht Einzel-Dokument dominiert:** k3 per-example JSON `1006 0.833 (+0.08), 1007 0.667 (+0.13), 1008 0.235 (+0.11), 1009 0.615 (+0.615), 1010 0.632 (+0.35)` — alle 5 besser als Baseline.
* **By-Type:** `WORK_MODE 0.250→0.833 (+0.583)`, `LANGUAGE 0.000→1.000 (+1.0)`, `EXPERIENCE 0.154→0.500`, `EDUCATION 0.000→0.286` — 3. Beispiel `1002` (Verkäufer, `Teilzeit`) als Rank 3 liefert fehlende `WORK_MODE`/`LANG` Vorbilder, die `k=2` (nur `1003/1005`) nicht hatte.
* **Kein Prompt/Parsing-Effekt:** JSON-Prompt identisch außer Anzahl Beispiele, Parser identisch. Sprung ist **Retrieval-Menge**, nicht Modell-Varianz (reparsed beweist Varianz nur 0.051).

## 5. Methodische Risiken

* **n=5/40 Entities** → 95% CI ±0.18, per-example `0.00-0.75` instabil, `LANGUAGE n=2` `F1 1.0` anekdotisch.
* **Marker kollabiert** auf Real-Gold (`reparsed 0.059`, k3 0.063) vs Smoke `0.667` — lange reale Texte halluzinieren `LOCATION/COMPANY`, partielle Validierung rettet nur 6 TP.
* **Small-sample Overfitting:** Gold=5 gleichzeitig Tuning-Set für k-Wahl — finale Evaluation darf nicht auf selbem Gold erfolgen.
* **TF-IDF Bias:** Nur `1003/1005` in allen 15 Queries Top1/2, `1001/1004` nie — geringe Pool-Diversität (5).
* **Prompt-Overfitting:** `strict` Prompt `0.319→0.286` zeigt kleine Prompt-Änderung Δ0.03-0.08.

## 6. Nächster Schritt

Gold 5→15 (10 neue reale, diverse Branchen, `LANGUAGE/EDU` anreichern), danach Gold Freeze als Pilot-Entscheidungs-Split, dann finale faire Evaluation `k=1/2/3 + Strict` auf Gold 15 — nicht auf finalem Test 20-30 optimieren. Danach Go/No-Go Few-Shot (kleinste praktisch gleich gute k, nicht signifikant-erzwingen) vor Self-Verification.

**Reproduzierbarkeit:** Alle Artefakte versioniert unter `artifacts/llm_baseline_gold*` und `artifacts/llm_fewshot_gold_k*/` mit `metrics.json:config` (`model, temperature, k, embedding_model, gold_dir`), `retrieval.json`, `raw_outputs/`.
