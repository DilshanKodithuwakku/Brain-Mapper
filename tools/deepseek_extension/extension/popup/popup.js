/**
 * Brain Mapper - DeepSeek Extension Popup Controller
 */

const BRIDGE_URL = "http://127.0.0.1:8765";

document.addEventListener("DOMContentLoaded", async () => {
  const bridgeStatusEl = document.getElementById("bridge-status");
  const tabStatusEl = document.getElementById("tab-status");
  const progressPercentEl = document.getElementById("progress-percent");
  const progressBarFillEl = document.getElementById("progress-bar-fill");
  const completedCountEl = document.getElementById("completed-count");
  const remainingCountEl = document.getElementById("remaining-count");
  const failedCountEl = document.getElementById("failed-count");
  const liveStepEl = document.getElementById("live-step");
  const activityDetailTextEl = document.getElementById("activity-detail-text");
  const btnToggle = document.getElementById("btn-toggle");
  const btnSkip = document.getElementById("btn-skip");
  const delaySlider = document.getElementById("delay-slider");
  const delayVal = document.getElementById("delay-val");
  const logList = document.getElementById("log-list");

  let isRunning = false;
  let activeDeepSeekTabId = null;

  function addLog(msg) {
    const time = new Date().toLocaleTimeString();
    const item = document.createElement("div");
    item.className = "log-item";
    item.innerText = `[${time}] ${msg}`;
    logList.prepend(item);
    // Keep max 15 log items
    while (logList.children.length > 15) {
      logList.removeChild(logList.lastChild);
    }
  }

  // Check DeepSeek active tab
  async function checkActiveTab() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.url && tab.url.includes("chat.deepseek.com")) {
        activeDeepSeekTabId = tab.id;
        tabStatusEl.innerText = "Detected";
        tabStatusEl.className = "pill pill-online";
        return true;
      } else {
        activeDeepSeekTabId = null;
        tabStatusEl.innerText = "Not Active";
        tabStatusEl.className = "pill pill-offline";
        return false;
      }
    } catch (_) {
      tabStatusEl.innerText = "Unknown";
      tabStatusEl.className = "pill pill-offline";
      return false;
    }
  }

  // Poll Bridge Server status
  async function pollBridgeStatus() {
    try {
      const res = await fetch(`${BRIDGE_URL}/api/status`);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();

      bridgeStatusEl.innerText = "Connected";
      bridgeStatusEl.className = "pill pill-online";

      // Update metrics
      progressPercentEl.innerText = `${data.progress_percent}%`;
      progressBarFillEl.style.width = `${data.progress_percent}%`;
      completedCountEl.innerText = data.completed_count.toLocaleString();
      remainingCountEl.innerText = data.remaining_count.toLocaleString();
      failedCountEl.innerText = data.failed_count.toLocaleString();

      if (data.done) {
        liveStepEl.innerText = "DONE";
        activityDetailTextEl.innerText = "All 7,652 questions annotated!";
      }
    } catch (err) {
      bridgeStatusEl.innerText = "Offline";
      bridgeStatusEl.className = "pill pill-offline";
    }
  }

  // Load stored state
  chrome.storage.local.get(["isRunning", "pacingDelaySec"], (data) => {
    isRunning = !!data.isRunning;
    updateToggleButton();
    if (data.pacingDelaySec) {
      delaySlider.value = data.pacingDelaySec;
      delayVal.innerText = `${data.pacingDelaySec}s`;
    }
  });

  function updateToggleButton() {
    if (isRunning) {
      btnToggle.innerText = "Pause Automation";
      btnToggle.className = "btn btn-primary btn-pause";
    } else {
      btnToggle.innerText = "Start Automation";
      btnToggle.className = "btn btn-primary";
    }
  }

  // Send message to active DeepSeek tab
  async function sendMessageToTab(msg) {
    await checkActiveTab();
    if (!activeDeepSeekTabId) {
      addLog("Please switch to a chat.deepseek.com tab first!");
      return null;
    }
    try {
      return await chrome.tabs.sendMessage(activeDeepSeekTabId, msg);
    } catch (err) {
      addLog("Error contacting tab: " + err.message);
      return null;
    }
  }

  // Toggle button handler
  btnToggle.addEventListener("click", async () => {
    if (!isRunning) {
      const res = await sendMessageToTab({ action: "START" });
      if (res) {
        isRunning = true;
        chrome.storage.local.set({ isRunning: true });
        updateToggleButton();
        addLog("Automation started.");
      }
    } else {
      const res = await sendMessageToTab({ action: "PAUSE" });
      if (res) {
        isRunning = false;
        chrome.storage.local.set({ isRunning: false });
        updateToggleButton();
        addLog("Automation paused.");
        liveStepEl.innerText = "PAUSED";
      }
    }
  });

  // Skip button handler
  btnSkip.addEventListener("click", async () => {
    addLog("Skipping current question...");
    await sendMessageToTab({ action: "SKIP" });
  });

  // Delay slider handler
  delaySlider.addEventListener("input", (e) => {
    const val = e.target.value;
    delayVal.innerText = `${val}s`;
    chrome.storage.local.set({ pacingDelaySec: parseInt(val, 10) });
    if (activeDeepSeekTabId) {
      sendMessageToTab({ action: "SET_DELAY", delaySec: parseInt(val, 10) });
    }
  });

  // Listen for live updates from content script
  chrome.runtime.onMessage.addListener((message) => {
    if (message.action === "STATE_UPDATE" && message.state) {
      const state = message.state;
      liveStepEl.innerText = state.step || "RUNNING";

      if (state.step === "UPLOADING_IMAGES" && state.question_id !== undefined) {
        activityDetailTextEl.innerText = `Uploading ${state.count} diagram image(s) for #${state.question_id}...`;
        addLog(`Uploading ${state.count} diagram(s) for #${state.question_id}`);
      } else if (state.step === "INJECTING_PROMPT" && state.question_id !== undefined) {
        activityDetailTextEl.innerText = `Injecting Question #${state.question_id}`;
        addLog(`Injecting Question #${state.question_id}`);
      } else if (state.step === "GENERATING") {
        activityDetailTextEl.innerText = `Generating Question #${state.question_id}...`;
      } else if (state.step === "PARSING") {
        activityDetailTextEl.innerText = `Parsing Question #${state.question_id} response`;
      } else if (state.step === "SAVED") {
        activityDetailTextEl.innerText = `Question #${state.question_id} saved to disk!`;
        addLog(`Question #${state.question_id} successfully saved`);
        pollBridgeStatus();
      } else if (state.step === "PACING") {
        activityDetailTextEl.innerText = `Waiting ${state.delaySec}s before next...`;
      } else if (state.step === "ERROR") {
        activityDetailTextEl.innerText = `Error: ${state.error}`;
        addLog(`Error on #${state.question_id}: ${state.error}`);
        pollBridgeStatus();
      } else if (state.step === "COMPLETED_ALL") {
        activityDetailTextEl.innerText = "Dataset 100% complete!";
        addLog("Dataset completed!");
        isRunning = false;
        updateToggleButton();
      }
    }
  });

  // Initial checks and polling interval
  await checkActiveTab();
  await pollBridgeStatus();
  setInterval(pollBridgeStatus, 3000);
});
