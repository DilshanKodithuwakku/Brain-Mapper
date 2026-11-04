/**
 * DeepSeek Web Chat DOM Adapter
 * Resilient selectors and event synthesizers for chat.deepseek.com
 */

const DeepSeekDOM = {
  /**
   * Locate the chat text input or textarea
   */
  getInputElement() {
    const selectors = [
      'textarea#chat-input',
      'textarea[placeholder*="DeepSeek"]',
      'textarea[placeholder*="Send a message"]',
      'textarea[placeholder*="Ask"]',
      'div.chat-input textarea',
      'div[contenteditable="true"]',
      'textarea',
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent !== null) {
        return el;
      }
    }
    return null;
  },

  /**
   * Programmatically set input value and notify React synthetic events
   */
  setInputValue(inputEl, text) {
    inputEl.focus();

    if (inputEl.tagName && inputEl.tagName.toLowerCase() === 'textarea') {
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        'value'
      )?.set;

      if (nativeSetter) {
        nativeSetter.call(inputEl, text);
      } else {
        inputEl.value = text;
      }

      // Dispatch events so React state updates
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
      inputEl.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      // Contenteditable fallback
      inputEl.innerText = text;
      inputEl.dispatchEvent(new InputEvent('input', { bubbles: true }));
    }
  },

  /**
   * Programmatically attach image files to the chat input via File Input or ClipboardEvent
   * @param {Array<{blob: Blob, name: string}>} images
   */
  async attachImages(images) {
    if (!images || images.length === 0) return true;

    // Convert Blobs to File objects
    const files = images.map(img => new File([img.blob], img.name, { type: 'image/png' }));

    // Strategy 1: Find file upload input in the DOM
    const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'));
    for (const input of fileInputs) {
      try {
        const dt = new DataTransfer();
        files.forEach(f => dt.items.add(f));
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('input', { bubbles: true }));

        await this.waitForImagePreview(files.length);
        return true;
      } catch (e) {
        console.warn("[BrainMapper] File input attachment attempt failed:", e);
      }
    }

    // Strategy 2: Simulate paste event on textarea / chat input
    const inputEl = this.getInputElement();
    if (inputEl) {
      try {
        inputEl.focus();
        const dt = new DataTransfer();
        files.forEach(f => dt.items.add(f));
        const pasteEvent = new ClipboardEvent('paste', {
          bubbles: true,
          cancelable: true,
          clipboardData: dt,
        });
        inputEl.dispatchEvent(pasteEvent);
        await this.waitForImagePreview(files.length);
        return true;
      } catch (e) {
        console.warn("[BrainMapper] Clipboard paste attachment attempt failed:", e);
      }
    }

    return false;
  },

  /**
   * Wait for image upload thumbnail/chip to appear in the message composer
   */
  async waitForImagePreview(expectedCount, timeoutMs = 8000) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeoutMs) {
      const previews = document.querySelectorAll(
        '.chat-input img, div[class*="preview"] img, div[class*="upload"] img, div[class*="attachment"], [class*="file-item"], div[class*="image-card"]'
      );
      if (previews.length > 0) {
        // Wait a small moment for upload processing/thumbnail rendering
        await new Promise(r => setTimeout(r, 1000));
        return true;
      }
      await new Promise(r => setTimeout(r, 400));
    }
    // Fallback: wait a baseline 1.5s
    await new Promise(r => setTimeout(r, 1500));
    return true;
  },

  /**
   * Locate and click the send/submit button
   */
  clickSendButton() {
    const inputEl = this.getInputElement();
    
    // Look for submit/send button in the input container hierarchy
    const container = inputEl ? (inputEl.closest('form') || inputEl.closest('.chat-input') || inputEl.parentElement?.parentElement) : document;
    
    const buttonSelectors = [
      'button[aria-label="Send"]',
      'div[role="button"][aria-label="Send"]',
      'button[type="submit"]',
      'div[class*="send-button"]',
      'div[class*="sendBtn"]',
      'button:not([disabled]) svg',
    ];

    if (container) {
      for (const sel of buttonSelectors) {
        const btn = container.querySelector(sel);
        if (btn) {
          const target = btn.tagName.toLowerCase() === 'svg' ? btn.closest('button, div[role="button"]') : btn;
          if (target && !target.disabled && target.getAttribute('aria-disabled') !== 'true') {
            target.click();
            return true;
          }
        }
      }
    }

    // Fallback: Dispatch Enter keydown on the input field
    if (inputEl) {
      const enterDown = new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true,
        shiftKey: false,
      });
      inputEl.dispatchEvent(enterDown);
      return true;
    }

    return false;
  },

  /**
   * Check if the model is currently generating output
   */
  isGenerating() {
    // 1. Look specifically for active stop-generating elements or spinner in send button
    const stopSelectors = [
      'button[aria-label*="Stop"]',
      'div[role="button"][aria-label*="Stop"]',
      'button[aria-label*="stop"]',
      'div[role="button"][aria-label*="stop"]',
      '.ds-stop-button',
      'button svg.animate-spin',
      'div[role="button"] svg.animate-spin',
    ];

    for (const sel of stopSelectors) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent !== null) {
        return true;
      }
    }

    return false;
  },

  /**
   * Retrieve all assistant response message blocks
   */
  getAssistantMessages() {
    const selectors = [
      'div[class*="message"][class*="assistant"]',
      '.chat-message-assistant',
      'div[data-role="assistant"]',
      '.ds-markdown',
      'div[class*="markdown"]',
    ];

    for (const sel of selectors) {
      const nodes = Array.from(document.querySelectorAll(sel));
      if (nodes.length > 0) {
        return nodes;
      }
    }

    return [];
  },

  /**
   * Get the text content of the latest assistant message
   */
  getLastAssistantMessageText() {
    // 1. Try to find the latest assistant message container
    const assistantContainers = Array.from(document.querySelectorAll(
      'div[class*="message"][class*="assistant"], .chat-message-assistant, div[data-role="assistant"]'
    ));

    if (assistantContainers.length > 0) {
      const lastContainer = assistantContainers[assistantContainers.length - 1];
      const markdowns = lastContainer.querySelectorAll('.ds-markdown, div[class*="markdown"]');
      if (markdowns.length > 0) {
        // Return the last markdown block inside the assistant container
        const lastMd = markdowns[markdowns.length - 1];
        return lastMd.innerText || lastMd.textContent || '';
      }
      return lastContainer.innerText || lastContainer.textContent || '';
    }

    // 2. Fallback: take the very last .ds-markdown on the entire page
    const allMarkdowns = Array.from(document.querySelectorAll('.ds-markdown, div[class*="markdown"]'));
    if (allMarkdowns.length > 0) {
      const last = allMarkdowns[allMarkdowns.length - 1];
      return last.innerText || last.textContent || '';
    }

    return null;
  },

  /**
   * Wait for model generation to complete using anti-stale guards and fast-path JSON validation
   */
  waitForCompletion(optionsOrCount, maybeTimeout) {
    let initialMessageCount = 0;
    let baselineText = '';
    let expectedQuestionId = null;
    let timeoutMs = 180000;

    if (typeof optionsOrCount === 'object' && optionsOrCount !== null) {
      initialMessageCount = optionsOrCount.initialMessageCount || 0;
      baselineText = (optionsOrCount.baselineText || '').trim();
      expectedQuestionId = optionsOrCount.expectedQuestionId ?? null;
      timeoutMs = optionsOrCount.timeoutMs || 180000;
    } else {
      initialMessageCount = optionsOrCount || 0;
      timeoutMs = maybeTimeout || 180000;
    }

    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      let lastText = '';
      let stableTicks = 0;
      let checkInterval = null;

      const finish = (success, result) => {
        if (checkInterval) clearInterval(checkInterval);
        if (success) {
          resolve(result);
        } else {
          reject(new Error(result));
        }
      };

      checkInterval = setInterval(() => {
        // Timeout check
        if (Date.now() - startTime > timeoutMs) {
          finish(false, `Generation timed out after ${timeoutMs / 1000}s`);
          return;
        }

        const currentText = (this.getLastAssistantMessageText() || '').trim();
        if (!currentText) {
          return;
        }

        // ANTI-STALE GUARD 1: If currentText matches the previous question's output, ignore it!
        if (baselineText && currentText === baselineText) {
          return;
        }

        // ANTI-STALE GUARD 2: Must have at least initial message count
        const currentCount = this.getAssistantMessages().length;
        if (initialMessageCount > 0 && currentCount < initialMessageCount) {
          return;
        }

        // FAST PATH: Check if response already contains a complete, valid JSON for THIS question
        let hasValidJson = false;
        if (window.CognitiveParser) {
          try {
            window.CognitiveParser.parseAndValidate(currentText, expectedQuestionId);
            hasValidJson = true;
          } catch (_) {
            hasValidJson = false;
          }
        }

        const generating = this.isGenerating();

        if (hasValidJson && currentText === lastText) {
          stableTicks++;
          // 2 ticks (1.0 second) of stable valid JSON for this specific question -> resolve immediately!
          if (stableTicks >= 2) {
            console.log(`[BrainMapper] Completed valid JSON detected for Question #${expectedQuestionId}. Resolving!`);
            finish(true, currentText);
            return;
          }
        } else if (!generating && currentText !== baselineText && currentText.length > 0 && currentText === lastText) {
          // Standard path when not generating and text is stable for 2 seconds
          stableTicks++;
          if (stableTicks >= 4) {
            finish(true, currentText);
            return;
          }
        } else {
          stableTicks = 0;
          lastText = currentText;
        }
      }, 500);
    });
  }
};

window.DeepSeekDOM = DeepSeekDOM;
