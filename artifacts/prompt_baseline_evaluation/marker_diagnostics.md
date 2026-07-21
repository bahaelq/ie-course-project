# Marker diagnostics

This report uses only the already stored artifacts from the previous evaluation run.

## Diagnosis table

| job_id | raw_output_present | marker_count | parsed_span_count | text_fidelity_valid | parser_valid | predicted_spans | gold_spans | exact_match_count | invalid_reason |
| --- | --- | ---: | ---: | --- | --- | --- | --- | ---: | --- |
| job_ad_001 | yes | 4 | 4 | no | yes | [{"type": "JOB_TITLE", "text": "Data Scientist (m/w/d)", "start": 0, "end": 22}, {"type": "HARD_SKILL", "text": "Python, SQL", "start": 103, "end": 114}, {"type": "HARD_SKILL", "text": "Machine Learning", "start": 119, "end": 135}, {"type": "WORK_MODE", "text": "Vollzeit und remote möglich", "start": 162, "end": 189}] | [{"type": "JOB_TITLE", "text": "Data Scientist", "start": 0, "end": 14}, {"type": "HARD_SKILL", "text": "Python", "start": 103, "end": 109}, {"type": "HARD_SKILL", "text": "SQL", "start": 111, "end": 114}, {"type": "HARD_SKILL", "text": "Machine Learning", "start": 119, "end": 135}, {"type": "WORK_MODE", "text": "Vollzeit", "start": 162, "end": 170}, {"type": "WORK_MODE", "text": "remote", "start": 175, "end": 181}] | 1 | Text fidelity mismatch after removing marker syntax |
| job_ad_002 | yes | 4 | 4 | no | yes | [{"type": "JOB_TITLE", "text": "Pflegefachkraft", "start": 16, "end": 31}, {"type": "EXPERIENCE", "text": "Erfahrung", "start": 89, "end": 98}, {"type": "SOFT_SKILL", "text": "empathischen, teamorientierten", "start": 153, "end": 183}, {"type": "WORK_MODE", "text": "Teilzeit und Hybrid", "start": 207, "end": 226}] | [{"type": "JOB_TITLE", "text": "Pflegefachkraft", "start": 16, "end": 31}, {"type": "SOFT_SKILL", "text": "empathischen", "start": 153, "end": 165}, {"type": "SOFT_SKILL", "text": "teamorientierten", "start": 167, "end": 183}, {"type": "WORK_MODE", "text": "Teilzeit", "start": 207, "end": 215}, {"type": "WORK_MODE", "text": "Hybrid", "start": 220, "end": 226}] | 1 | Text fidelity mismatch after removing marker syntax |
| job_ad_003 | yes | 4 | 4 | no | yes | [{"type": "JOB_TITLE", "text": "Softwareentwickler", "start": 17, "end": 35}, {"type": "SOFT_SKILL", "text": "Kommunikationsstärke", "start": 80, "end": 100}, {"type": "SOFT_SKILL", "text": "Arbeitsweise", "start": 120, "end": 132}, {"type": "WORK_MODE", "text": "Remote", "start": 182, "end": 188}] | [{"type": "JOB_TITLE", "text": "Softwareentwickler", "start": 17, "end": 35}, {"type": "HARD_SKILL", "text": "Java", "start": 53, "end": 57}, {"type": "HARD_SKILL", "text": "Spring Boot", "start": 62, "end": 73}, {"type": "SOFT_SKILL", "text": "Kommunikationsstärke", "start": 80, "end": 100}, {"type": "SOFT_SKILL", "text": "selbstständige Arbeitsweise", "start": 105, "end": 132}, {"type": "WORK_MODE", "text": "40 Wochenstunden", "start": 161, "end": 177}, {"type": "WORK_MODE", "text": "Remote", "start": 182, "end": 188}] | 3 | Text fidelity mismatch after removing marker syntax |
| job_ad_004 | yes | 3 | 3 | no | yes | [{"type": "JOB_TITLE", "text": "Vertriebler", "start": 17, "end": 28}, {"type": "LANGUAGE", "text": "Englisch B2", "start": 92, "end": 103}, {"type": "EDUCATION", "text": "Ausbildung im kaufmännischen Bereich", "start": 142, "end": 178}] | [{"type": "JOB_TITLE", "text": "Vertriebler", "start": 17, "end": 28}, {"type": "EXPERIENCE", "text": "Erfahrung im B2B-Verkauf", "start": 53, "end": 77}, {"type": "LANGUAGE", "text": "Englisch B2", "start": 92, "end": 103}, {"type": "EDUCATION", "text": "abgeschlossene Ausbildung", "start": 127, "end": 152}] | 2 | Text fidelity mismatch after removing marker syntax |
| job_ad_005 | yes | 4 | 4 | no | yes | [{"type": "JOB_TITLE", "text": "Verwaltungsfachkraft", "start": 16, "end": 36}, {"type": "EDUCATION", "text": "Bachelor in Informatik", "start": 106, "end": 128}, {"type": "WORK_MODE", "text": "Homeoffice", "start": 154, "end": 164}, {"type": "HARD_SKILL", "text": "Verwaltung von Dokumenten", "start": 183, "end": 208}] | [{"type": "JOB_TITLE", "text": "Verwaltungsfachkraft", "start": 16, "end": 36}, {"type": "EDUCATION", "text": "Bachelor in Informatik", "start": 106, "end": 128}, {"type": "WORK_MODE", "text": "Homeoffice", "start": 154, "end": 164}, {"type": "EXPERIENCE", "text": "Erfahrung in der Verwaltung von Dokumenten", "start": 166, "end": 208}] | 3 | Text fidelity mismatch after removing marker syntax |

## Raw marker outputs

### job_ad_001

```text
@@JOB_TITLE{Data Scientist (m/w/d)}## gesucht für ein wachsendes Analytics-Team. Wir suchen eine erfahrene Person mit @@HARD_SKILL{Python, SQL}## und @@HARD_SKILL{Machine Learning}## Erfahrung. Die Stelle ist @@WORK_MODE{Vollzeit und remote möglich}##.
```

### job_ad_002

```text
Wir suchen eine @@JOB_TITLE{Pflegefachkraft}## für die stationäre Versorgung im Krankenhaus. Sie bringt @@EXPERIENCE{Erfahrung}## in der Betreuung von Patienten und arbeitet mit einem @@SOFT_SKILL{empathischen, teamorientierten}## Umgang. Die Stelle ist @@WORK_MODE{Teilzeit und Hybrid}##.
```

### job_ad_003

```text
Wir suchen einen @@JOB_TITLE{Softwareentwickler}## mit Erfahrung in Java und Spring Boot. Gute @@SOFT_SKILL{Kommunikationsstärke}## und selbstständige @@SOFT_SKILL{Arbeitsweise}## sind wichtig. Die Rolle ist 40 Wochenstunden und @@WORK_MODE{Remote}##.
```

### job_ad_004

```text
Wir suchen einen @@JOB_TITLE{Vertriebler}## für den Außendienst mit Erfahrung im B2B-Verkauf. Sie sprechen @@LANGUAGE{Englisch B2}## und verfügen über eine abgeschlossene @@EDUCATION{Ausbildung im kaufmännischen Bereich}##.
```

### job_ad_005

```text
Wir suchen eine @@JOB_TITLE{Verwaltungsfachkraft}## für die Kundenbetreuung und die Bearbeitung von Anträgen. Sie bringt @@EDUCATION{Bachelor in Informatik}## mit und arbeitet gern im @@WORK_MODE{Homeoffice}##. Erfahrung in der @@HARD_SKILL{Verwaltung von Dokumenten}## ist hilfreich.
```

## Summary

- Main cause: the marker validator expects the full original text to be preserved after stripping marker syntax, but the model outputs only a shortened form with markers inserted. That causes every example to be rejected as a global format mismatch.
- The parser itself is not the main failure; it recognizes the marker syntax in all five cases.
- The model also produced span-content mismatches (different boundaries or combined spans), which are genuine model errors.
- Minimal fix: align the prompt and validator on the same output contract, or relax the validator to accept the model’s output style. The least invasive correction is to make the marker prompt explicitly require a full-text-with-markers output and keep the validator unchanged.
