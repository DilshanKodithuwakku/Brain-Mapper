/**
 * Brain Mapper - DeepSeek Content Script Orchestrator
 * Connects DeepSeek Web Chat tab to the local bridge server (localhost:8765)
 */

(function () {
  console.log("[BrainMapper] DeepSeek content script initialized.");

  const BRIDGE_URL = "http://127.0.0.1:8765";

  let isRunning = false;
  let currentStep = "IDLE";
  let currentQuestionId = null;
  let pacingDelayMs = 6000;
  let loopTimeout = null;

  // Sync initial settings from storage
  chrome.storage.local.get(['isRunning', 'pacingDelaySec'], (data) => {
    if (data.isRunning) {
      console.log("[BrainMapper] Resuming active automation state.");
      isRunning = true;
      runNextCycle();
    }
    if (data.pacingDelaySec) {
      pacingDelayMs = data.pacingDelaySec * 1000;
    }
  });

  // Listen for control messages from popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "START") {
      console.log("[BrainMapper] Starting automation...");
      isRunning = true;
      chrome.storage.local.set({ isRunning: true });
      runNextCycle();
      sendResponse({ status: "STARTED" });
    } else if (message.action === "PAUSE") {
      console.log("[BrainMapper] Pausing automation...");
      isRunning = false;
      chrome.storage.local.set({ isRunning: false });
      if (loopTimeout) clearTimeout(loopTimeout);
      currentStep = "PAUSED";
      sendResponse({ status: "PAUSED" });
    } else if (message.action === "SKIP") {
      console.log("[BrainMapper] Skipping question:", currentQuestionId);
      if (currentQuestionId !== null) {
        fetch(`${BRIDGE_URL}/api/skip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question_id: currentQuestionId }),
        }).then(() => {
          runNextCycle();
        });
      }
      sendResponse({ status: "SKIPPED" });
    } else if (message.action === "GET_STATE") {
      sendResponse({
        isRunning,
        currentStep,
        currentQuestionId,
      });
    } else if (message.action === "SET_DELAY") {
      pacingDelayMs = (message.delaySec || 6) * 1000;
      chrome.storage.local.set({ pacingDelaySec: message.delaySec });
      sendResponse({ pacingDelayMs });
    }
    return true;
  });

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function notifyPopup(step, details = {}) {
    currentStep = step;
    chrome.runtime.sendMessage({
      action: "STATE_UPDATE",
      state: {
        isRunning,
        step,
        currentQuestionId,
        ...details,
      },
    }).catch(() => {
      // Popup might not be open, ignore harmless error
    });
  }

  async function runNextCycle() {
    if (!isRunning) {
      currentStep = "PAUSED";
      notifyPopup("PAUSED");
      return;
    }

    try {
      // 1. Fetch next question from bridge server
      notifyPopup("FETCHING_QUESTION");
      const resp = await fetch(`${BRIDGE_URL}/api/next_question`);
      if (!resp.ok) {
        throw new Error(`Bridge server responded with HTTP ${resp.status}`);
      }
      const data = await resp.json();

      if (data.done) {
        console.log("[BrainMapper] All questions completed!");
        isRunning = false;
        chrome.storage.local.set({ isRunning: false });
        notifyPopup("COMPLETED_ALL");
        return;
      }

      currentQuestionId = data.question_id;
      notifyPopup("INJECTING_PROMPT", { question_id: currentQuestionId });
      console.log(`[BrainMapper] Processing Question ID: ${currentQuestionId}`);

      // 2. Ensure chat input exists
      const inputEl = DeepSeekDOM.getInputElement();
      if (!inputEl) {
        throw new Error("Chat input element not found in DOM. Ensure you are logged into chat.deepseek.com.");
      }

      // Check if already generating
      if (DeepSeekDOM.isGenerating()) {
        console.warn("[BrainMapper] Model is currently generating. Waiting before injection...");
        await sleep(3000);
      }

      // Capture baseline state before injecting or sending to prevent reading stale previous outputs
      const baselineText = (DeepSeekDOM.getLastAssistantMessageText() || "").trim();
      const initialMessageCount = DeepSeekDOM.getAssistantMessages().length;

      // 3. Attach images if question is multimodal
      if (data.has_images && data.image_urls && data.image_urls.length > 0) {
        notifyPopup("UPLOADING_IMAGES", { question_id: currentQuestionId, count: data.image_urls.length });
        console.log(`[BrainMapper] Question #${currentQuestionId} has ${data.image_urls.length} image(s). Fetching from bridge...`);

        const imageFiles = [];
        for (let i = 0; i < data.image_urls.length; i++) {
          const imgRelUrl = data.image_urls[i];
          const fullImgUrl = imgRelUrl.startsWith("http") ? imgRelUrl : `${BRIDGE_URL}${imgRelUrl}`;
          const filename = (data.image_filenames && data.image_filenames[i]) || `question_${currentQuestionId}_img_${i}.png`;

          try {
            const imgResp = await fetch(fullImgUrl);
            if (imgResp.ok) {
              const blob = await imgResp.blob();
              imageFiles.push({ blob, name: filename });
            } else {
              console.warn(`[BrainMapper] Bridge returned HTTP ${imgResp.status} for image ${fullImgUrl}`);
            }
          } catch (fetchErr) {
            console.warn(`[BrainMapper] Failed to fetch image ${fullImgUrl}:`, fetchErr);
          }
        }

        if (imageFiles.length > 0) {
          console.log(`[BrainMapper] Attaching ${imageFiles.length} image(s) to DeepSeek chat input...`);
          await DeepSeekDOM.attachImages(imageFiles);
          await sleep(1200);
        }
      }

      // 4. Inject question prompt text
      notifyPopup("INJECTING_PROMPT", { question_id: currentQuestionId });
      DeepSeekDOM.setInputValue(inputEl, data.prompt);
      await sleep(800);

      // 5. Trigger send button
      const sent = DeepSeekDOM.clickSendButton();
      if (!sent) {
        throw new Error("Failed to trigger send action");
      }

      notifyPopup("GENERATING", { question_id: currentQuestionId });
      console.log(`[BrainMapper] Question ${currentQuestionId} submitted. Waiting for completion...`);

      // 6. Wait for model response to stream and complete with anti-stale guards
      const rawResponseText = await DeepSeekDOM.waitForCompletion({
        initialMessageCount,
        baselineText,
        expectedQuestionId: currentQuestionId,
        timeoutMs: 180000,
      });
      notifyPopup("PARSING", { question_id: currentQuestionId });

      // 7. Extract and validate JSON response (strictly verifying question_id)
      const parsedData = CognitiveParser.parseAndValidate(rawResponseText, currentQuestionId);
      console.log(`[BrainMapper] Question ${currentQuestionId} successfully parsed:`, parsedData.scores);

      // 7. Submit back to bridge server
      notifyPopup("SUBMITTING", { question_id: currentQuestionId });
      const submitResp = await fetch(`${BRIDGE_URL}/api/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: currentQuestionId,
          scores: parsedData.scores,
          confidence: parsedData.confidence,
          short_rationale: parsedData.short_rationale,
          raw_response: rawResponseText,
        }),
      });

      if (!submitResp.ok) {
        const errJson = await submitResp.json();
        throw new Error(errJson.error || "Bridge submit failed");
      }

      notifyPopup("SAVED", { question_id: currentQuestionId });

      // 8. Pacing delay with random jitter (+/- 1.5s) to stay safe from rate-limits
      if (isRunning) {
        const jitter = Math.floor(Math.random() * 2000) - 500;
        const delay = Math.max(2000, pacingDelayMs + jitter);
        console.log(`[BrainMapper] Pacing delay: ${(delay / 1000).toFixed(1)}s before next question...`);
        notifyPopup("PACING", { delaySec: (delay / 1000).toFixed(1) });
        loopTimeout = setTimeout(runNextCycle, delay);
      }
    } catch (err) {
      console.error(`[BrainMapper] Error on question ${currentQuestionId}:`, err);
      notifyPopup("ERROR", { error: err.message, question_id: currentQuestionId });

      // Record failure to bridge
      if (currentQuestionId !== null) {
        try {
          await fetch(`${BRIDGE_URL}/api/fail`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              question_id: currentQuestionId,
              error: err.message,
            }),
          });
        } catch (_) {}
      }

      // If running, wait 8 seconds before retrying or next cycle
      if (isRunning) {
        console.log("[BrainMapper] Cooling down for 8s after error before continuing...");
        loopTimeout = setTimeout(runNextCycle, 8000);
      }
    }
  }
})();
