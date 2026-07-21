# Marker Prompt Evaluation v2

## Summary
- Examples: job_ad_001
- Micro precision: 0.000
- Micro recall: 0.000
- Micro F1: 0.000

## Invalid format outputs
- job_ad_001: Text fidelity mismatch after removing marker syntax

## Errors
- job_ad_001: invalid_output -> Data Scientist (m/w/d) gesucht für ein wachsendes @@JOB_TITLE{Analytics-Team}##. Wir suchen eine @@EXPERIENCE{erfahrene Person}## mit @@HARD_SKILL{Python}##, @@HARD_SKILL{SQL}## und @@HARD_SKILL{Machine Learning}## @@EXPERIENCE{Erfahrung}##. Die Stelle ist @@WORK_MODE{Vollzeit}## und @@WORK_MODE{remote möglich}##.
- job_ad_001: missed_entity -> Data Scientist
- job_ad_001: missed_entity -> Python
- job_ad_001: missed_entity -> SQL
- job_ad_001: missed_entity -> Machine Learning
- job_ad_001: missed_entity -> Vollzeit
- job_ad_001: missed_entity -> remote
