# Brain Mapper

> **Cognitive-Aware Learning Analytics & Explainable Knowledge Tracing**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey.svg)]()
[![Tests](https://img.shields.io/badge/tests-6%20passed-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/status-Phase%202%20Active%20(Annotation)-orange.svg)]()

**Brain Mapper** is a learning analytics research system that bridges **Large Language Models (LLMs)** with **Knowledge Tracing (KT)**. Traditional Knowledge Tracing models track student mastery based strictly on binary correctness and coarse concept tags (Knowledge Components). Brain Mapper extracts deep cognitive skill requirements from educational questions using multimodal LLMs and integrates these multi-dimensional cognitive vectors into deep Knowledge Tracing models, providing both accurate performance forecasting and interpretable cognitive learner profiles.

The project also features an offline Local Area Network (LAN) examination system designed to collect granular student response interactions and surface actionable learning analytics to educators without requiring an internet connection during exam delivery.

---

## Current Project Status

| Phase | Milestone | Status | Details |
|---|---|---|---|
| **Phase 1** | **Dataset & Data Preparation** | **Completed** | Curated XES3G5M dataset integrated. 7,652 questions, 50,000 student interactions, and 2,800+ diagram images processed and verified. |
| **Phase 2** | **Cognitive Skill Annotation** | **In Progress (Active)** | 6-skill taxonomy formulated; DeepSeek browser automation bridge deployed. **1,350+ / 7,652 questions annotated** with visual diagram support and anti-stale verification. |
| **Phase 3** | **Knowledge Tracing Modeling** | *Upcoming* | Baseline implementations (DKT, qDKT, QKT) and development of Cognitive-Aware KT (CA-KT). |
| **Phase 4** | **Learner Profiling & Explainability** | *Upcoming* | Cognitive radar profiles, misconception diagnosis, and educator dashboard. |
| **Phase 5** | **Offline LAN Exam Platform** | *Upcoming* | Lightweight local API and responsive web interface for secure offline testing. |

### Active Annotation Pipeline Highlights
- **Model Engine**: DeepSeek Web Chat Bridge (supporting DeepSeek-V3 and DeepSeek-R1) via Chrome extension and local bridge server.
- **Multimodal Support**: Diagram-dependent math problems stream local PNG images directly and attach them to DeepSeek chat via the `DataTransfer` / `File` API.
- **Quota-Free & High Speed**: Unlimited automated querying without strict API rate limits or daily quota lockouts.
- **Resilience**: Atomic progress tracking using `os.fsync`. Interrupted runs cleanly pause on `Ctrl+C` or extension toggle, and resume without duplicate annotations.
- **Verification**: In-band question ID validation, baseline response differential guards, and `<think>` token stripping.

---

## Research Objectives

1. **Multimodal Cognitive Skill Estimation**: Leverage vision-language models to score the cognitive demands of educational questions across 6 core dimensions.
2. **Cognitive Feature Integration**: Augment sequential student interaction histories with question-level cognitive requirement vectors.
3. **Cognitive-Aware Knowledge Tracing (CA-KT)**: Design deep recurrent/attention architectures that track student mastery across underlying cognitive faculties rather than memorized question types.
4. **Baseline Benchmarking**: Empirically benchmark CA-KT against standard KT baselines (DKT, qDKT, QKT) across AUC, Accuracy, and RMSE.
5. **Explainable Learner Profiles**: Provide educators with clear, actionable diagnostics on student cognitive strengths (e.g., strong logical reasoning but constrained working memory).

---

## Cognitive-Skill Taxonomy

Questions are annotated on an integer scale from `0` to `3`:
- **0 - Not Required**: The question does not rely on this cognitive skill.
- **1 - Low Requirement**: Baseline familiarity or simple application.
- **2 - Moderate Requirement**: Multi-step deduction, intermediate memory load, or targeted analysis.
- **3 - High Requirement**: Deep abstract reasoning, multi-constraint tracking, or synthesis.

| Cognitive Skill | Definition & Indicators |
|---|---|
| **Attention** | Selective focus on key problem elements, visual diagram parsing, filtering extraneous distractors. |
| **Working Memory** | Retaining and manipulating intermediate computations, variables, and multi-clause constraints concurrently. |
| **Logical Reasoning** | Step-by-step deductive or inductive thinking, pattern discovery, geometric proofs, and combinatorial rules. |
| **Language Processing** | Decoding domain-specific mathematical phrasing, complex multi-clause problems, and linguistic nuances. |
| **Critical Thinking** | Evaluating alternate solution pathways, verifying assumptions, checking boundary cases, and counterexample analysis. |
| **Metacognition** | Strategy planning, error self-monitoring, constraint satisfaction verification, and solution reflection. |

Configuration definitions and rubric prompts are version-controlled in `configs/cognitive_skills.yaml` and `configs/cognitive_annotation.yaml`.

---

## Repository Structure

```text
Brain-Mapper/
|-- apps/                         # Application interfaces
|   |-- exam_api/                 # Offline LAN examination backend
|   |-- exam_web/                 # Student examination web interface
|   `-- analytics_dashboard/      # Educator analytics dashboard
|-- artifacts/                    # Trained model weights, ROC curves, and reports
|-- configs/                      # Configuration files (taxonomy, pipeline settings)
|   |-- cognitive_annotation.yaml # Annotation parameters, models, and file paths
|   `-- cognitive_skills.yaml     # 6-skill taxonomy definitions and grading rubric
|-- data/
|   |-- raw/xes3g5m/              # Raw XES3G5M dataset and metadata images
|   |-- processed/xes3g5m/        # Cleaned questions.csv and interactions.csv
|   |-- annotations/xes3g5m/      # LLM annotation outputs (destination for final export)
|   `-- DATASET.md                # Dataset provenance, exclusions, and licensing
|-- database/                     # Offline exam database schema and migrations
|-- deployment/                   # Docker and LAN deployment configurations
|-- docs/                         # Research design documents and architecture specifications
|-- notebooks/                    # Exploratory data analysis and experimental notebooks
|-- pipelines/                    # End-to-end data and training pipeline scripts
|-- prompts/                      # Version-controlled LLM prompt templates
|   `-- cognitive_annotation_v1.txt
|-- src/brain_mapper/             # Core Python package
|   |-- cognitive_analysis/       # Cognitive taxonomy schemas, sampling, and quality auditing
|   |-- data/                     # Dataset loading, cleaning, validation, and preparation
|   |-- explainability/           # Cognitive profiling and interpretation modules
|   |-- inference/                # Production model inference
|   |-- models/                   # DKT, qDKT, QKT, and CA-KT architectures
|   `-- training/                 # Training loops, loss functions, metrics, and logging
|-- tests/                        # Automated unit and integration test suite
|-- tools/                        # Annotation tools and extensions
|   `-- deepseek_extension/       # Isolated browser extension & bridge server for DeepSeek annotation
|-- pyproject.toml                # Project metadata, dependencies, and entrypoints
`-- README.md                     # Project overview and documentation
```

---

## Getting Started

### Prerequisites
- **Python**: 3.11 or higher
- **Git LFS**: Required for large dataset CSV files
- **Google Chrome**: For running the DeepSeek annotation extension

### 1. Clone the Repository
```bash
git lfs install
git clone https://github.com/waruna-2003/Brain-Mapper.git
cd Brain-Mapper
git lfs pull
```

### 2. Virtual Environment & Dependencies
Create and activate a virtual environment:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

---

## Workflow & Usage

### 1. Data Preparation
Prepare and validate the XES3G5M questions and interaction sequences:
```powershell
brain-mapper-prepare-xes3g5m
```
This generates `questions.csv` (7,652 questions) and `interactions.csv` (50,000 records) in `data/processed/xes3g5m/`.

### 2. Running Cognitive Annotation (DeepSeek Extension)
The project annotates the full dataset using the isolated DeepSeek browser extension:

1. **Start the Local Bridge Server**:
   ```powershell
   python tools/deepseek_extension/bridge_server.py
   ```
2. **Load the Extension into Chrome**:
   - Navigate to `chrome://extensions` and enable **Developer mode**.
   - Click **Load unpacked** and select `tools/deepseek_extension/extension`.
3. **Run Automation**:
   - Open [https://chat.deepseek.com](https://chat.deepseek.com) and log in.
   - Click the **Brain Mapper** extension icon and click **Start Automation**.

### 3. Checking Progress & Quality Audit
To audit progress or verify cognitive score distributions:
```powershell
# Check live DeepSeek annotation progress
python tools/deepseek_extension/scripts/check_progress.py

# Sample questions for validation
brain-mapper-cognitive sample
```

---

## Testing

Run the automated test suite with `pytest`:
```powershell
pytest tests
```
All unit tests verify:
- Data preparation and question formatting integrity
- Schema validation for cognitive scores (0–3 bounds, required fields)
- Prompt template rendering and hashing
- Batch request generation and response parsing

---

## Data & Research Privacy

- **Anonymization**: All student IDs in experimental datasets are synthetic or de-identified; no PII is retained or processed.
- **Responsible AI**: Cognitive scores are produced to model question complexity and support educators, never for automated or high-stakes punitive decisions.
- **Auditability**: Every generated annotation logs the provider, model name, prompt SHA-256 hash, taxonomy version, response confidence, and API token usage.

---

## License

This project is currently under research and development. All rights are reserved by the authors until an open-source license is officially designated.
