# Brain Mapper - DeepSeek Web Chat Annotation Bridge

An isolated, crash-resilient browser extension and local bridge server system to automate cognitive-skill annotation of the complete 7,652-question XES3G5M dataset via the **DeepSeek Web Chat** interface (`chat.deepseek.com`).

---

## Architecture & Isolation Guarantee

This entire subsystem is strictly separated into `tools/deepseek_extension/`:
- **Zero Core Contamination**: Does not modify or depend on files in `src/brain_mapper/`.
- **No Early Aggregation**: Annotations are written to `tools/deepseek_extension/data/deepseek_annotations.jsonl`. They will **not** be merged into the main dataset until the entire corpus (all 7,652 questions) is completed and verified.
- **Crash-Resilient Atomic Writes**: Every successfully parsed question is flushed immediately to disk using `os.fsync`. If your browser tab refreshes, Chrome crashes, or your internet disconnects, simply resume without duplicate entries.
- **DeepSeek-R1 Support**: Built-in parser automatically strips `<think>...</think>` reasoning tokens and extracts the clean JSON cognitive rubric.

```text
tools/deepseek_extension/
|-- README.md                         # This documentation
|-- bridge_server.py                  # Local Python server (localhost:8765)
|-- config.yaml                       # Isolated configuration
|-- data/                             # Isolated outputs & state checkpoint
|   |-- deepseek_annotations.jsonl    # Canonical output records (Q0 to Q7651)
|   |-- deepseek_failures.jsonl       # Error log (timeouts, unparseable responses)
|   `-- state.json                    # Checkpoint state
|-- extension/                        # Chrome Extension (Manifest V3)
|   |-- manifest.json                 # Manifest V3 file
|   |-- popup/                        # Extension popup UI (Start, Pause, Delay, Progress)
|   |   |-- popup.html
|   |   |-- popup.css
|   |   `-- popup.js
|   `-- content/                      # Injected DOM controllers
|       |-- deepseek_dom.js           # Selectors and synthetic event dispatchers
|       |-- parser.js                 # Strips <think> tokens, extracts & validates JSON
|       `-- content.js                # Queue coordinator & pacing loop
|-- scripts/
|   |-- check_progress.py             # CLI auditor for progress and score distributions
|   `-- export_to_brain_mapper.py     # Aggregation script (enforces 100% completion before export)
`-- tests/
    |-- test_bridge_server.py         # Unit tests for queue and validator
    `-- test_parser.py                # Unit tests for parsing and <think> stripping
```

---

## Quickstart Guide

### Step 1: Start the Local Bridge Server
From the project root with your Python environment activated:

```powershell
python tools/deepseek_extension/bridge_server.py
```

The bridge server will load `data/processed/xes3g5m/questions.csv` and output:
```text
=================================================================
  DeepSeek Isolated Annotation Bridge Server
=================================================================
  Server URL      : http://127.0.0.1:8765
  Total Questions : 7652
  Completed       : 0 (0.0%)
  Remaining       : 7652
  Failed Logged   : 0
  Next Question ID: 0
=================================================================
```
Leave this terminal window running.

---

### Step 2: Install the Chrome Extension

1. Open Google Chrome.
2. In the URL bar, go to `chrome://extensions`.
3. Enable the **Developer mode** toggle in the top-right corner.
4. Click the **Load unpacked** button in the top-left corner.
5. Select the directory:
   ```text
   d:\Brain Mapper\tools\deepseek_extension\extension
   ```
6. The extension **Brain Mapper - DeepSeek Annotator** will appear in your extensions list.

---

### Step 3: Run the Annotation Loop

1. In Chrome, open [https://chat.deepseek.com](https://chat.deepseek.com) and log in to your account.
2. Ensure you are on a new chat session. You may use standard **DeepSeek-V3** or **DeepSeek-R1**.
3. Click the **Brain Mapper** extension icon in your Chrome toolbar.
4. In the popup:
   - Verify that **Bridge Server** says `Connected` and **DeepSeek Tab** says `Detected`.
   - Set your preferred **Pacing Delay** (recommended: 6s–10s to stay comfortably within rate limits).
   - Click **Start Automation**.
5. The extension will automatically:
   - Fetch the next unannotated question from the bridge server.
   - For **image-dependent questions (2,214 questions)**: Automatically fetches the diagram PNG file(s) from the bridge server and attaches them directly into the DeepSeek chat input via the `DataTransfer` / `File` API.
   - Injects the cognitive evaluation prompt into the DeepSeek chat input.
   - Clicks Send.
   - Monitors the response stream until generation completes.
   - Extracts and validates the 6-skill JSON schema (automatically stripping `<think>` tags if using DeepSeek-R1).
   - Posts the validated result to the bridge server, which flushes it atomically to disk with `os.fsync`.
   - Waits the configured pacing delay, and seamlessly repeats!

---

### Step 4: Monitoring Progress & Quality

At any time, open a separate terminal and run:

```powershell
python tools/deepseek_extension/scripts/check_progress.py
```

This prints:
- Total unique questions completed out of 7,652.
- Percentage progress.
- Average confidence.
- Distribution breakdown (counts of 0, 1, 2, 3) across all 6 cognitive skills (`attention`, `working_memory`, `logical_reasoning`, `language_processing`, `critical_thinking`, `metacognition`).

---

### Step 5: Exporting into Brain Mapper (After 100% Completion)

Once all 7,652 questions have been successfully annotated, run:

```powershell
python tools/deepseek_extension/scripts/export_to_brain_mapper.py
```

> [!NOTE]
> By design, this script will strictly block execution if any questions are missing to protect the integrity of the Brain Mapper dataset.
