---
name: persistent-memory
description: Use when needing to recall past decisions or keep a session log. Instructs ClawBot on how to manage knowledge.
---

# Persistent Context Memory Protocol

1. **Context injection:** In multi-step tasks, always maintain an ongoing memory log in `task.md` or a `.memory/` state file. This simulates an observation timeline.
2. Every tool use (bash, write, read) should be internally logged as an 'Observation'.
3. **Session Lifecycle:**
   - Before Agent Start: Review `task.md` or similar context artifacts.
   - During Turn: Check if previous hypotheses were proven false. Accumulate failure modes so you don't repeat mistakes.
   - Agent End: Create a summary report of what was achieved and what the architecture looks like now so the next session doesn't start blind.
4. **Knowledge Retrieval:** Do not guess the structure of a system you built previously. Read the artifacts you created.

This behavior turns isolated chat turns into a continuous workflow akin to claude-mem SSE streams.
