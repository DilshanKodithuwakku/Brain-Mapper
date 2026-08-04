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
|-- artifacts/                    # Generated models, metrics, and figures (DVC)
|-- configs/                      # Dataset, model, and skill configurations
|-- data/
|   |-- raw/                      # Original private/public datasets (DVC)
|   |-- interim/                  # Cleaned intermediate datasets (DVC)
|   |-- processed/                # Model-ready datasets (DVC)
|   |-- annotations/              # LLM and expert cognitive labels (DVC)
|   `-- sample/                   # Small anonymized examples safe for Git
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
|-- dvc.yaml                     # Reproducible ML pipeline definition
`-- params.yaml                  # Versioned experiment parameters
```

Each main directory contains a short README describing its intended contents.

## GitHub and DagsHub workflow

- **GitHub:** source code, configuration, issues, branches, pull requests, and CI.
- **DagsHub/DVC:** large datasets, processed datasets, and trained model artifacts.
- **DagsHub/MLflow:** experiment parameters, metrics, artifacts, and model versions.

Never commit student identities, answer scripts containing personal information, API keys, access tokens, or local environment files.

### Typical collaboration cycle

```bash
git checkout -b feature/short-description
# Make and test changes
git add .
git commit -m "Add short description"
git push -u origin feature/short-description
```

Open a pull request into `main`. If the work changes DVC-tracked data, run `dvc push` in addition to `git push`.

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
- Commit only small, anonymized sample data to Git.
- Track approved large datasets with DVC and confirm their licenses permit storage and use.
- Use LLMs for question analysis, not automated educational decisions.
- Record the LLM, prompt version, taxonomy version, and expert-review status for every annotation batch.

## Project status

Initial research and platform scaffolding. The first planned milestone covers dataset schemas, cognitive annotation, and baseline Knowledge Tracing experiments.

## License

No license has been selected yet. Until a license is added, all rights are reserved by the project authors.
