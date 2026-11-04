# Cognitive analysis

This package creates question-level cognitive requirements for the six-skill
Brain Mapper taxonomy. It deliberately annotates questions without using
student correctness, answers, or knowledge-component labels.

## Pilot workflow

Run these commands from the repository root after activating `.venv`:

```powershell
brain-mapper-cognitive sample
brain-mapper-cognitive annotate-pilot --limit 5
brain-mapper-cognitive annotate-pilot
brain-mapper-cognitive quality
```

The annotator is resumable: successful IDs already in the output JSONL are
skipped. Each row stores the provider/model, taxonomy and prompt versions,
prompt hash, confidence, rationale, review status, and API usage metadata.

The `quality` command creates:

- `pilot_quality_report.json` for coverage, duplicates, confidence, and score distributions;
- `pilot_review.csv` for human review;
- `pilot_cognitive_features.csv` for a later join to interactions by `question_id`.

Do not run the full text or image batches until the pilot has been reviewed by
at least one domain expert. Image questions are supported by the lower-level
command once that gate is passed:

```powershell
brain-mapper-annotate-cognitive `
  --input data/processed/xes3g5m/cognitive_annotation_input_text_only.jsonl `
  --output data/annotations/xes3g5m/text_annotations.jsonl `
  --failures data/annotations/xes3g5m/text_failures.jsonl `
  --manifest data/annotations/xes3g5m/text_manifest.json
```

For the image-dependent questions:

```powershell
brain-mapper-annotate-cognitive `
  --input data/processed/xes3g5m/questions.csv `
  --input-mode image `
  --output data/annotations/xes3g5m/image_annotations.jsonl `
  --failures data/annotations/xes3g5m/image_failures.jsonl `
  --manifest data/annotations/xes3g5m/image_manifest.json
```

## Full dataset with Gemini Batch API

The full XES3G5M run uses one multimodal JSONL batch, which is asynchronous and
costs 50% of standard API inference. Google AI Pro is separate from Gemini API
billing; verify that the API project is on a paid tier before submission.

```powershell
brain-mapper-cognitive-batch prepare
brain-mapper-cognitive-batch submit
brain-mapper-cognitive-batch status
# After the state becomes JOB_STATE_SUCCEEDED:
brain-mapper-cognitive-batch collect
brain-mapper-cognitive-batch quality
```

The large base64 request file is reproducible and ignored by Git. The collected
annotations, QC report, review CSV, and question-level feature table are kept
under `data/annotations/xes3g5m/` for collaboration.
