# LLM Baseline Evaluation (gold)

- Split: gold
- Gold dir: data/gold
- Model: meta-llama-3.1-8b-instruct
- Base URL: https://chat-ai.academiccloud.de/v1
- Temperature: 0.0
- Examples: 15 (job_ad_1006, job_ad_1007, job_ad_1008, job_ad_1009, job_ad_1010, job_ad_1011, job_ad_1012, job_ad_1013, job_ad_1014, job_ad_1015, job_ad_1016, job_ad_1017, job_ad_1018, job_ad_1019, job_ad_1020)
- API calls: 30

## JSON Prompt
- Micro precision: 0.262
- Micro recall: 0.363
- Micro F1: 0.305

## Marker Prompt
- Micro precision: 0.174
- Micro recall: 0.186
- Micro F1: 0.180

## Per example
- job_ad_1006: JSON F1=0.000 Marker F1=0.143
- job_ad_1007: JSON F1=0.533 Marker F1=0.067
- job_ad_1008: JSON F1=0.125 Marker F1=0.000
- job_ad_1009: JSON F1=0.000 Marker F1=0.000
- job_ad_1010: JSON F1=0.333 Marker F1=0.000
- job_ad_1011: JSON F1=0.333 Marker F1=0.000
- job_ad_1012: JSON F1=0.000 Marker F1=0.000
- job_ad_1013: JSON F1=0.240 Marker F1=0.000
- job_ad_1014: JSON F1=0.500 Marker F1=0.333
- job_ad_1015: JSON F1=0.526 Marker F1=0.000
- job_ad_1016: JSON F1=0.250 Marker F1=0.400
- job_ad_1017: JSON F1=0.714 Marker F1=0.500
- job_ad_1018: JSON F1=0.000 Marker F1=0.000
- job_ad_1019: JSON F1=0.261 Marker F1=0.273
- job_ad_1020: JSON F1=0.462 Marker F1=0.429

## Errors
- Total errors: 378
