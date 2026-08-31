# LLM Few-Shot Evaluation (gold, k=2)

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
- job_ad_1006: job_ad_1003 (0.457), job_ad_1005 (0.409)
- job_ad_1007: job_ad_1005 (0.452), job_ad_1003 (0.446)
- job_ad_1008: job_ad_1005 (0.501), job_ad_1003 (0.484)
- job_ad_1009: job_ad_1003 (0.388), job_ad_1002 (0.345)
- job_ad_1010: job_ad_1003 (0.490), job_ad_1005 (0.472)
- job_ad_1011: job_ad_1003 (0.406), job_ad_1005 (0.389)
- job_ad_1012: job_ad_1005 (0.433), job_ad_1003 (0.404)
- job_ad_1013: job_ad_1003 (0.341), job_ad_1005 (0.323)
- job_ad_1014: job_ad_1003 (0.321), job_ad_1004 (0.321)
- job_ad_1015: job_ad_1002 (0.277), job_ad_1005 (0.276)
- job_ad_1016: job_ad_1002 (0.314), job_ad_1003 (0.243)
- job_ad_1017: job_ad_1003 (0.339), job_ad_1005 (0.287)
- job_ad_1018: job_ad_1005 (0.372), job_ad_1003 (0.355)
- job_ad_1019: job_ad_1003 (0.375), job_ad_1005 (0.373)
- job_ad_1020: job_ad_1004 (0.311), job_ad_1003 (0.255)

## JSON Prompt
- Micro precision: 0.511
- Micro recall: 0.441
- Micro F1: 0.474

## Marker Prompt
- Micro precision: 0.282
- Micro recall: 0.196
- Micro F1: 0.231

## Per example
- job_ad_1006: JSON F1=0.667 Marker F1=0.000
- job_ad_1007: JSON F1=0.000 Marker F1=0.267
- job_ad_1008: JSON F1=0.000 Marker F1=0.000
- job_ad_1009: JSON F1=0.000 Marker F1=0.000
- job_ad_1010: JSON F1=0.476 Marker F1=0.000
- job_ad_1011: JSON F1=0.364 Marker F1=0.308
- job_ad_1012: JSON F1=0.200 Marker F1=0.000
- job_ad_1013: JSON F1=0.455 Marker F1=0.000
- job_ad_1014: JSON F1=0.444 Marker F1=0.400
- job_ad_1015: JSON F1=0.316 Marker F1=0.167
- job_ad_1016: JSON F1=0.909 Marker F1=0.500
- job_ad_1017: JSON F1=1.000 Marker F1=0.667
- job_ad_1018: JSON F1=0.400 Marker F1=0.000
- job_ad_1019: JSON F1=0.667 Marker F1=0.421
- job_ad_1020: JSON F1=0.727 Marker F1=0.000

## Comparison to Baseline
- Baseline JSON F1: 0.319 Few-Shot JSON F1: 0.474 Delta: +0.155
- Baseline Marker F1: 0.000 Few-Shot Marker F1: 0.231 Delta: +0.231
- JSON Precision delta: +0.234 Recall delta: +0.066
- Marker Precision delta: +0.282 Recall delta: +0.196

### By-type F1 delta (Few-Shot - Baseline)
| Type | JSON ΔF1 | Marker ΔF1 |
|------|----------|------------|
| JOB_TITLE | -0.536 | +0.133 |
| HARD_SKILL | -0.113 | +0.114 |
| SOFT_SKILL | -0.114 | +0.211 |
| EXPERIENCE | +0.573 | +0.348 |
| EDUCATION | +0.560 | +0.222 |
| LANGUAGE | +0.667 | +0.316 |
| WORK_MODE | +0.395 | +0.320 |

## Errors
- Total errors: 222
