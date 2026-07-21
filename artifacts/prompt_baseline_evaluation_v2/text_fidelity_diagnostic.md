# Text fidelity diagnostic for job_ad_001

## Exact comparison

```text
original_text_repr = 'Data Scientist (m/w/d) gesucht für ein wachsendes Analytics-Team. Wir suchen eine erfahrene Person mit Python, SQL und Machine Learning Erfahrung. Die Stelle ist Vollzeit und remote möglich.\n'
stripped_marker_text_repr = 'Data Scientist (m/w/d) gesucht für ein wachsendes Analytics-Team. Wir suchen eine erfahrene Person mit Python, SQL und Machine Learning Erfahrung. Die Stelle ist Vollzeit und remote möglich.'
original_text_length = 191
stripped_marker_text_length = 190
first_difference_index = 190
difference_only_trailing_newline = True
rstrip_equal = True
original_has_trailing_newline = True
stripped_has_trailing_newline = False
```

## Result

- The text-fidelity failure is caused solely by the trailing newline present in the original file text and absent from the stripped marker output.
- The validator should therefore not be blamed for a substantive content mismatch here.
- The marker parser still finds spans, but the stored output also contains genuine extraction errors such as wrong types and boundaries.
