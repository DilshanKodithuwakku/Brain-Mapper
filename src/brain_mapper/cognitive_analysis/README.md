# Cognitive Analysis

This package defines the six-skill cognitive taxonomy, validation schemas, sampling tools, and quality control auditing for Brain Mapper.

## Cognitive Taxonomy

Questions are scored from `0` (not required) to `3` (high requirement) across:
- **attention**: Select and maintain focus on relevant details, constraints, symbols, options, or visual elements while ignoring distractions.
- **working_memory**: Hold and manipulate multiple pieces of information or intermediate results simultaneously.
- **logical_reasoning**: Apply rules, step-by-step deductions, patterns, or multi-step operations to reach a conclusion.
- **language_processing**: Comprehend text complexity, sentence structure, terminology, and instructional phrasing.
- **critical_thinking**: Evaluate strategies, compare options, detect assumptions, or select optimal approaches.
- **metacognition**: Monitor understanding, verify solutions, identify errors, or adjust approaches.

## Dataset Annotation

The full 7,652-question XES3G5M dataset is annotated using the isolated **DeepSeek Web Chat Extension** located in [`tools/deepseek_extension/`](../../../tools/deepseek_extension/).

Refer to [DeepSeek Extension README](../../../tools/deepseek_extension/README.md) for instructions on starting the local bridge server and running the browser automation.

## Quality Control & Export

Once annotations are completed, the export and quality verification tools can be run:

```powershell
# Export and validate the full completed DeepSeek annotations
python tools/deepseek_extension/scripts/export_to_brain_mapper.py

# Run quality checks (coverage, distributions, score sanity)
brain-mapper-cognitive quality
```
