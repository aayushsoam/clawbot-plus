---
name: systematic-debugging
description: Use when encountering any error, bug, test failure, or unexpected behavior while writing code. Ensures root-cause analysis before proposing fixes.
---

# Systematic Debugging

## Core Principle
ALWAYS find the root cause before attempting fixes. Random guess-and-check patches waste time and create new bugs. NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.

## The Four Phases of Debugging

### Phase 1: Root Cause Investigation
**BEFORE attempting ANY fix:**
1. **Read Error Messages Carefully:** Do not skip past stack traces. Look for file paths and specific line numbers.
2. **Reproduce Consistently:** Understand exactly what triggers the error.
3. **Trace Data Flow:** Trace the error backward through the call stack to find the original bad value.

### Phase 2: Pattern Analysis
1. Find working examples in the same codebase.
2. Determine what is different between the working code and the broken code.

### Phase 3: Hypothesis and Testing
1. Form a Single Hypothesis: "I think X is the root cause because Y."
2. Make the SMALLEST possible change to test the hypothesis. One variable at a time.

### Phase 4: Implementation
1. Fix the root cause, not the symptom. Do not lump refactoring in with a bug fix.
2. Verify the fix.
3. **Red Flag:** If you try 3 different fixes and none work, STOP. Question the architecture. Do not attempt a 4th fix without re-evaluating the foundational pattern.

## Red Flags - STOP and rethink if you find yourself:
- Thinking "Quick fix for now, investigate later"
- Saying "I don't fully understand but this might work"
- Attempting to fix multiple unrelated things in one go
- Adding random `try/except` blocks to just hide errors
