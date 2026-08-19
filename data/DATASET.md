# XES3G5M collaboration dataset

## Sources

- XES3G5M official repository: https://github.com/ai4ed/XES3G5M
- XES3G5M official download: https://drive.google.com/file/d/1eFiIYyh5O2V90RA0brammGH6EpHvPDQe/view
- ExRec English question metadata: https://github.com/oezyurty/ExRec

The student identifiers in the published XES3G5M files are internal anonymized identifiers. This
repository does not contain names, contact information, or student answer text.

## Included raw files

- `raw/xes3g5m/question_level/train_valid_sequences_quelevel.csv`
- `raw/xes3g5m/question_level/test_quelevel.csv`
- `raw/xes3g5m/metadata/questions_translated.json`
- `raw/xes3g5m/metadata/images/question_*-image_*.png`

Only question images are included. Chinese-only metadata, pretrained embeddings, KC-level expanded
sequences, generated ExRec annotations, analysis images, and overlapping test-window sequences are
excluded because Brain Mapper does not use them.

## Processed files

- `processed/xes3g5m/interactions.csv`: flattened question-level interaction events.
- `processed/xes3g5m/questions.csv`: English model inputs and image references without answers or
  curriculum labels.
- `processed/xes3g5m/question_reference.csv`: correct answers and KC routes, isolated to prevent
  cognitive-annotation leakage.
- `processed/xes3g5m/cognitive_annotation_input_text_only.jsonl`: text-only LLM input records.
- `processed/xes3g5m/processing_summary.json`: data lineage and validation statistics.

Regenerate processed files with:

```powershell
brain-mapper-prepare-xes3g5m
```

## Limitations

- XES3G5M provides binary correctness, not the answer written or selected by each student.
- The dataset authors truncated training sequences, so complete original histories cannot be
  reconstructed.
- Question ID `6232` is present in metadata but absent from the canonical question-level train/test
  sequences used here.
- The ExRec repository publishes the English translation but does not currently contain an explicit
  license file. Confirm redistribution terms with its authors before making a repository containing
  that translation public. A private research repository should still retain this attribution.

## License and citation

The official XES3G5M repository declares the MIT License; its license notice is retained as
`raw/xes3g5m/LICENSE_XES3G5M`. Cite the original XES3G5M and ExRec publications in research outputs.
