# Prompt Baseline Offline Reassessment

## Hinweise
- Technischer Smoke Test auf fünf künstlichen Anzeigen
- Noch keine belastbare wissenschaftliche Evaluation
- Alte Marker-F1 von 0,000 entstand durch einen Validierungsfehler
  (Texttreueprüfung scheiterte an abschließendem Newline-Zeichen)
- Korrigierte Texttreueprüfung ignoriert genau einen abschließenden \n oder \r\n

## Ergebnisse

### JSON Prompt
- Micro Precision: 0.5758
- Micro Recall: 0.7308
- Micro F1: 0.6441
- TP: 19, FP: 14, FN: 7

### Marker Prompt
- Micro Precision: 0.5263
- Micro Recall: 0.3846
- Micro F1: 0.4444
- TP: 10, FP: 9, FN: 16

### F1 pro Entitätstyp
| Typ | JSON F1 | Marker F1 |
|-----|---------|-----------|
| JOB_TITLE | 0.8000 | 0.8000 |
| HARD_SKILL | 0.8333 | 0.2500 |
| SOFT_SKILL | 0.4444 | 0.2857 |
| EXPERIENCE | 0.0000 | 0.0000 |
| EDUCATION | 0.8000 | 0.5000 |
| LANGUAGE | 1.0000 | 1.0000 |
| WORK_MODE | 0.7143 | 0.3636 |

### F1 pro Anzeige
| Anzeige | JSON F1 | Marker F1 |
|---------|---------|-----------|
| job_ad_001 | 0.6154 | 0.2000 |
| job_ad_002 | 0.5455 | 0.2222 |
| job_ad_003 | 0.8571 | 0.5455 |
| job_ad_004 | 0.5455 | 0.5714 |
| job_ad_005 | 0.6000 | 0.7500 |

### Ungültige Ausgaben insgesamt: 0

### Häufigste Fehlerkategorien
- missed_entity: 23
- wrong_boundary: 11
- hallucinated_entity: 8
- wrong_type: 4

### Neu erstellte / geänderte Dateien
- artifacts/prompt_baseline_offline_reassessment/metrics.json
- artifacts/prompt_baseline_offline_reassessment/predictions_json.json
- artifacts/prompt_baseline_offline_reassessment/predictions_marker.json
- artifacts/prompt_baseline_offline_reassessment/errors.json
- artifacts/prompt_baseline_offline_reassessment/per_document_metrics.json
- artifacts/prompt_baseline_offline_reassessment/summary.md
- scripts/offline_reassessment.py
