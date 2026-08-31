# LLM Few-Shot Evaluation (gold, k=3)

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
- job_ad_1006: job_ad_1003 (0.457), job_ad_1005 (0.409), job_ad_1002 (0.383)
- job_ad_1007: job_ad_1005 (0.452), job_ad_1003 (0.446), job_ad_1002 (0.403)
- job_ad_1008: job_ad_1005 (0.501), job_ad_1003 (0.484), job_ad_1002 (0.431)
- job_ad_1009: job_ad_1003 (0.388), job_ad_1002 (0.345), job_ad_1005 (0.337)
- job_ad_1010: job_ad_1003 (0.490), job_ad_1005 (0.472), job_ad_1002 (0.407)
- job_ad_1011: job_ad_1003 (0.406), job_ad_1005 (0.389), job_ad_1002 (0.364)
- job_ad_1012: job_ad_1005 (0.433), job_ad_1003 (0.404), job_ad_1002 (0.369)
- job_ad_1013: job_ad_1003 (0.341), job_ad_1005 (0.323), job_ad_1002 (0.289)
- job_ad_1014: job_ad_1003 (0.321), job_ad_1004 (0.321), job_ad_1005 (0.290)
- job_ad_1015: job_ad_1002 (0.277), job_ad_1005 (0.276), job_ad_1003 (0.272)
- job_ad_1016: job_ad_1002 (0.314), job_ad_1003 (0.243), job_ad_1005 (0.220)
- job_ad_1017: job_ad_1003 (0.339), job_ad_1005 (0.287), job_ad_1002 (0.258)
- job_ad_1018: job_ad_1005 (0.372), job_ad_1003 (0.355), job_ad_1002 (0.302)
- job_ad_1019: job_ad_1003 (0.375), job_ad_1005 (0.373), job_ad_1002 (0.326)
- job_ad_1020: job_ad_1004 (0.311), job_ad_1003 (0.255), job_ad_1002 (0.226)

## JSON Prompt
- Micro precision: 0.562
- Micro recall: 0.441
- Micro F1: 0.495

## Marker Prompt
- Micro precision: 0.378
- Micro recall: 0.167
- Micro F1: 0.231

## Per example
- job_ad_1006: JSON F1=0.600 Marker F1=0.000
- job_ad_1007: JSON F1=0.714 Marker F1=0.000
- job_ad_1008: JSON F1=0.333 Marker F1=0.222
- job_ad_1009: JSON F1=0.000 Marker F1=0.000
- job_ad_1010: JSON F1=0.632 Marker F1=0.000
- job_ad_1011: JSON F1=0.308 Marker F1=0.250
- job_ad_1012: JSON F1=0.167 Marker F1=0.000
- job_ad_1013: JSON F1=0.600 Marker F1=0.000
- job_ad_1014: JSON F1=0.727 Marker F1=0.400
- job_ad_1015: JSON F1=0.000 Marker F1=0.320
- job_ad_1016: JSON F1=0.909 Marker F1=0.588
- job_ad_1017: JSON F1=0.909 Marker F1=0.727
- job_ad_1018: JSON F1=0.000 Marker F1=0.000
- job_ad_1019: JSON F1=0.625 Marker F1=0.000
- job_ad_1020: JSON F1=0.000 Marker F1=0.000

## Comparison to Baseline
- Baseline JSON F1: 0.319 Few-Shot JSON F1: 0.495 Delta: +0.175
- Baseline Marker F1: 0.000 Few-Shot Marker F1: 0.231 Delta: +0.231
- JSON Precision delta: +0.285 Recall delta: +0.066
- Marker Precision delta: +0.378 Recall delta: +0.167

### By-type F1 delta (Few-Shot - Baseline)
| Type | JSON ΔF1 | Marker ΔF1 |
|------|----------|------------|
| JOB_TITLE | -0.289 | +0.235 |
| HARD_SKILL | -0.033 | +0.000 |
| SOFT_SKILL | -0.095 | +0.258 |
| EXPERIENCE | +0.513 | +0.400 |
| EDUCATION | +0.348 | +0.316 |
| LANGUAGE | +0.700 | +0.316 |
| WORK_MODE | +0.440 | +0.100 |

## Errors
- Total errors: 212
