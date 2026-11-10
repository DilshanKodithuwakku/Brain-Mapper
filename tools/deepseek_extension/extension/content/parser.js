/**
 * Cognitive Response Parser
 * Strips reasoning tokens, markdown code blocks, extracts and validates JSON.
 */

const CognitiveParser = {
  REQUIRED_SKILLS: [
    'attention',
    'working_memory',
    'logical_reasoning',
    'language_processing',
    'critical_thinking',
    'metacognition',
  ],

  /**
   * Remove <think> ... </think> blocks from DeepSeek-R1 reasoning outputs
   */
  stripThinkBlocks(text) {
    if (!text) return '';
    // Strip complete <think>...</think> blocks across newlines
    let cleaned = text.replace(/<think>[\s\S]*?<\/think>/gi, '');
    // Also strip unclosed <think> if response truncated
    cleaned = cleaned.replace(/<think>[\s\S]*$/gi, '');
    return cleaned.trim();
  },

  /**
   * Extract JSON string from raw text (handles markdown fences or free text)
   */
  extractJsonString(rawText) {
    const textWithoutThink = this.stripThinkBlocks(rawText);

    // 1. Try markdown code block ```json ... ```
    const codeBlockMatch = textWithoutThink.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
    if (codeBlockMatch && codeBlockMatch[1]) {
      return codeBlockMatch[1].trim();
    }

    // 2. Try to find the outermost curly braces { ... }
    const firstBrace = textWithoutThink.indexOf('{');
    const lastBrace = textWithoutThink.lastIndexOf('}');
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      return textWithoutThink.substring(firstBrace, lastBrace + 1).trim();
    }

    return textWithoutThink;
  },

  /**
   * Parse and validate scores against the 6-skill taxonomy rubric
   */
  parseAndValidate(rawText, expectedQuestionId = null) {
    const jsonStr = this.extractJsonString(rawText);
    if (!jsonStr) {
      throw new Error("No JSON structure found in response text");
    }

    let parsed;
    try {
      parsed = JSON.parse(jsonStr);
    } catch (err) {
      throw new Error(`Failed to parse JSON: ${err.message}. Snippet: ${jsonStr.slice(0, 100)}`);
    }

    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new Error("Parsed JSON is not an object");
    }

    // Verify question_id match if present to prevent accepting previous turn output
    if (expectedQuestionId !== null && 'question_id' in parsed) {
      const parsedId = parseInt(parsed.question_id, 10);
      if (!isNaN(parsedId) && parsedId !== expectedQuestionId) {
        throw new Error(`Stale output detected: response specifies question_id ${parsedId}, but currently expecting #${expectedQuestionId}`);
      }
    }

    const validatedScores = {};
    for (const skill of this.REQUIRED_SKILLS) {
      if (!(skill in parsed)) {
        throw new Error(`Missing required cognitive skill: '${skill}'`);
      }
      let val = parsed[skill];
      // Coerce string or float numbers like "2" or 2.0 to int
      if (typeof val === 'string') {
        val = parseInt(val, 10);
      } else if (typeof val === 'number') {
        val = Math.round(val);
      } else {
        throw new Error(`Invalid score type for '${skill}': ${typeof val}`);
      }

      if (isNaN(val) || val < 0 || val > 3) {
        throw new Error(`Score for '${skill}' must be between 0 and 3, got: ${val}`);
      }
      validatedScores[skill] = val;
    }

    // Validate confidence
    let confidence = 0.95;
    if ('confidence' in parsed) {
      const confVal = parseFloat(parsed.confidence);
      if (!isNaN(confVal) && confVal >= 0.0 && confVal <= 1.0) {
        confidence = confVal;
      }
    }

    // Validate short rationale
    let rationale = "DeepSeek Web Chat annotation";
    if (parsed.short_rationale && typeof parsed.short_rationale === 'string') {
      rationale = parsed.short_rationale.trim();
    }

    return {
      scores: validatedScores,
      confidence,
      short_rationale: rationale,
    };
  }
};

window.CognitiveParser = CognitiveParser;
