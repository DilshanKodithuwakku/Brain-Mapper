# Data processing

Dataset loaders, schema validation, anonymization, preprocessing, and sequence building.

## XES3G5M

Prepare the official question-level sequences together with ExRec's English question text:

```powershell
brain-mapper-prepare-xes3g5m
```

The default input is the collaboration package under `data/raw/xes3g5m`. Outputs are written to
`data/processed/xes3g5m`:

- `questions.csv`: model-safe English question text, options, and image references.
- `question_reference.csv`: correct answers and curriculum KC routes, kept separate to prevent
  cognitive-annotation leakage.
- `cognitive_annotation_input_text_only.jsonl`: text-only questions ready for LLM annotation.
- `interactions.csv`: flattened train/validation and original test interactions.
- `processing_summary.json`: provenance, data-quality statistics, and known limitations.

The overlapping `test_window_sequences_quelevel.csv` file is intentionally excluded because its
sliding histories would duplicate events in a canonical interaction table.
