# Offline reassessment for job_ad_001

- text_fidelity_valid: True
- tp: 4
- fp: 4
- fn: 2
- precision: 0.500
- recall: 0.667
- f1: 0.571

## Exact matches
- HARD_SKILL: Python -> (103, 109)
- HARD_SKILL: SQL -> (111, 114)
- HARD_SKILL: Machine Learning -> (119, 135)
- WORK_MODE: Vollzeit -> (162, 170)

## Errors
- missed_entity: JOB_TITLE -> Data Scientist
- missed_entity: WORK_MODE -> remote
- unexpected_entity: JOB_TITLE -> Analytics-Team
- unexpected_entity: EXPERIENCE -> erfahrene Person
- unexpected_entity: EXPERIENCE -> Erfahrung
- unexpected_entity: WORK_MODE -> remote möglich
