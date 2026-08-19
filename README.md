# Brain Mapper

Brain Mapper is a cognitive-aware learning analytics research project that combines Large Language Models (LLMs) with Knowledge Tracing (KT). It aims to predict student performance and generate explainable profiles of learners' cognitive strengths and weaknesses.

The project also includes an offline Local Area Network (LAN) examination platform for collecting question-level responses and presenting analytics to educators without requiring an internet connection during examinations.

## Research objectives

- Use an LLM to estimate the cognitive skills required by each educational question.
- Integrate cognitive-skill profiles with student interaction sequences.
- Develop a Cognitive-Aware Knowledge Tracing model.
- Compare the proposed model with DKT, qDKT, and QKT baselines.
- Generate interpretable learner profiles for educators.
- Evaluate prediction quality using AUC, accuracy, RMSE, and related metrics.

## Cognitive-skill taxonomy

Questions are scored from `0` (not required) to `3` (high requirement) for:

- Attention
- Working memory
- Logical reasoning
- Language processing
- Critical thinking
- Metacognition

The taxonomy and its versioned configuration will be maintained in `configs/cognitive_skills.yaml`.

## Repository structure

```text
Brain-Mapper/
|-- apps/
|   |-- exam_api/                 # Offline LAN examination backend
|   |-- exam_web/                 # Student and examiner web interface
|   `-- analytics_dashboard/      # Educator-facing learner analytics
|-- artifacts/                    # Generated models, metrics, and figures
|-- configs/                      # Dataset, model, and skill configurations
|-- data/
|   |-- raw/xes3g5m/              # Minimal reproducible XES3G5M source package
|   |-- processed/xes3g5m/        # Model-ready collaboration data
|   `-- DATASET.md                # Provenance, exclusions, license, limitations
|-- database/                     # Schema and migrations for the exam platform
|-- deployment/                   # LAN and container deployment files
|-- docs/                         # Architecture, ethics, dataset, and experiment docs
|-- notebooks/                    # Numbered exploratory notebooks
|-- pipelines/                    # Reproducible data and training entry points
|-- src/brain_mapper/
|   |-- cognitive_analysis/       # LLM annotation and expert validation
|   |-- data/                     # Loading, validation, and preprocessing
|   |-- explainability/           # Cognitive learner profiles
|   |-- inference/                # Model loading and prediction
|   |-- models/                   # Baselines and Cognitive-Aware KT
|   `-- training/                 # Training, evaluation, and experiment tracking
|-- tests/                        # Unit, integration, data, and model tests
`-- params.yaml                  # Versioned experiment parameters
```

Each main directory contains a short README describing its intended contents.

## Dataset and Git LFS

The repository includes the curated XES3G5M collaboration dataset. Large CSV files use Git LFS,
while question metadata and images are regular Git files. Install Git LFS before cloning:

```bash
git lfs install
git clone https://github.com/waruna-2003/Brain-Mapper.git
cd Brain-Mapper
git lfs pull
```

Dataset provenance and limitations are documented in `data/DATASET.md`. In particular, XES3G5M
contains binary correctness labels rather than each student's written or selected answer.

Rebuild the processed data after installing the project:

```bash
brain-mapper-prepare-xes3g5m
```

## GitHub workflow

Never commit student identities, answer scripts containing personal information, API keys, access tokens, or local environment files.

### Typical collaboration cycle

```bash
git checkout -b feature/short-description
# Make and test changes
git add .
git commit -m "Add short description"
git push -u origin feature/short-description
```

Open a pull request into `main`. Git LFS objects are uploaded automatically by `git push`.

## Local setup

The implementation dependencies will be added as the individual components are developed. A typical Python setup is:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project after dependencies have been defined:

```bash
python -m pip install -e ".[dev]"
```

## Data and privacy

- Replace student identities with generated identifiers before research processing.
- Keep the re-identification key at the participating school, outside this repository.
- Keep large approved collaboration files under the existing Git LFS paths.
- Confirm dataset and translation redistribution terms before making the repository public.
- Use LLMs for question analysis, not automated educational decisions.
- Record the LLM, prompt version, taxonomy version, and expert-review status for every annotation batch.

## Project status

Initial research and platform scaffolding. The first planned milestone covers dataset schemas, cognitive annotation, and baseline Knowledge Tracing experiments.

## License

No license has been selected yet. Until a license is added, all rights are reserved by the project authors.
