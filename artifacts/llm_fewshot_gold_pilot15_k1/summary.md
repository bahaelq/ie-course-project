# LLM Few-Shot Evaluation (gold, k=1)

- Split: gold
- Gold dir: data/gold
- Example pool: data/example_pool (5 examples)
- Model: meta-llama-3.1-8b-instruct
- Base URL: https://chat-ai.academiccloud.de/v1
- Temperature: 0.0
- Embedding: tfidf-sklearn
- Examples: 15 (job_ad_1006, job_ad_1007, job_ad_1008, job_ad_1009, job_ad_1010, job_ad_1011, job_ad_1012, job_ad_1013, job_ad_1014, job_ad_1015, job_ad_1016, job_ad_1017, job_ad_1018, job_ad_1019, job_ad_1020)
- API calls: 30

## Retrieval
- job_ad_1006: job_ad_1003 (0.457)
- job_ad_1007: job_ad_1005 (0.452)
- job_ad_1008: job_ad_1005 (0.501)
- job_ad_1009: job_ad_1003 (0.388)
- job_ad_1010: job_ad_1003 (0.490)
- job_ad_1011: job_ad_1003 (0.406)
- job_ad_1012: job_ad_1005 (0.433)
- job_ad_1013: job_ad_1003 (0.341)
- job_ad_1014: job_ad_1003 (0.321)
- job_ad_1015: job_ad_1002 (0.277)
- job_ad_1016: job_ad_1002 (0.314)
- job_ad_1017: job_ad_1003 (0.339)
- job_ad_1018: job_ad_1005 (0.372)
- job_ad_1019: job_ad_1003 (0.375)
- job_ad_1020: job_ad_1004 (0.311)

## JSON Prompt
- Micro precision: 0.483
- Micro recall: 0.422
- Micro F1: 0.450

## Marker Prompt
- Micro precision: 0.311
- Micro recall: 0.314
- Micro F1: 0.312

## Per example
- job_ad_1006: JSON F1=0.400 Marker F1=0.182
- job_ad_1007: JSON F1=0.000 Marker F1=0.333
- job_ad_1008: JSON F1=0.316 Marker F1=0.222
- job_ad_1009: JSON F1=0.000 Marker F1=0.000
- job_ad_1010: JSON F1=0.444 Marker F1=0.182
- job_ad_1011: JSON F1=0.462 Marker F1=0.600
- job_ad_1012: JSON F1=0.167 Marker F1=0.000
- job_ad_1013: JSON F1=0.000 Marker F1=0.261
- job_ad_1014: JSON F1=0.600 Marker F1=0.308
- job_ad_1015: JSON F1=0.273 Marker F1=0.083
- job_ad_1016: JSON F1=0.833 Marker F1=0.444
- job_ad_1017: JSON F1=0.909 Marker F1=0.923
- job_ad_1018: JSON F1=0.364 Marker F1=0.182
- job_ad_1019: JSON F1=0.600 Marker F1=0.300
- job_ad_1020: JSON F1=0.909 Marker F1=0.533

## Comparison to Baseline
- Baseline JSON F1: 0.319 Few-Shot JSON F1: 0.450 Delta: +0.131
- Baseline Marker F1: 0.000 Few-Shot Marker F1: 0.312 Delta: +0.312
- JSON Precision delta: +0.205 Recall delta: +0.047
- Marker Precision delta: +0.311 Recall delta: +0.314

### By-type F1 delta (Few-Shot - Baseline)
| Type | JSON ΔF1 | Marker ΔF1 |
|------|----------|------------|
| JOB_TITLE | -0.536 | +0.400 |
| HARD_SKILL | -0.086 | +0.270 |
| SOFT_SKILL | -0.096 | +0.136 |
| EXPERIENCE | +0.583 | +0.467 |
| EDUCATION | +0.400 | +0.545 |
| LANGUAGE | +0.857 | +0.348 |
| WORK_MODE | +0.266 | +0.207 |

## Errors
- Total errors: 264
