# 🤖 ClawBot Plus v2.0 (Formerly JARVIS)

ClawBot is an advanced, autonomous AI Agent that completely controls your Windows PC, browses the web, and executes complex programming tasks natively. With the v2.0 update, it has evolved from a simple computer-control script into a **Multi-Agent Productivity Framework**.

---

## 🏗️ System Architecture & Workflow

Below is the Mermaid flowchart showing exactly how your ClawBot project functions right now:

`flowchart TD

  %% Input Layer
  A["User Input (CLI or Voice)"] --> B["ClawBot Core Agent"]
  T["Telegram Bot"] <--> B

  %% Memory Layer
  B --> C["Memory System"]
  C --> C1["Obsidian Vault"]
  C --> C2["Daily Logs"]
  C --> C3["RAG Search"]
  C --> C4["Skills Library"]

  %% Planning Layer
  B --> D["Planner Agent"]

  %% Execution Layer
  D --> E1["Worker Agent 1"]
  D --> E2["Worker Agent 2"]

  %% Action Layer
  E1 --> F1["System Control"]
  E2 --> F2["Browser Automation"]

  %% Core Direct Actions
  B --> F3["Voice Engine"]
  B --> F4["Self-Healing Code Engine"]

  %% Background Layer
  G["Watcher (Notifications)"] --> B
  H["Daemon (Scheduler)"] --> B

## 🌟 The 7 Next-Generation Modules

Here is a breakdown of all the premium modules integrated into ClawBot:

### 1. 👁️ Proactive Context Awareness (`watcher.py`)
A background thread periodically takes a small screenshot and runs an LLM check. If it detects you are stuck on an error or crash, it sends a **Windows Toast Notification** offering immediate help.

### 2. 👥 Multi-Agent Orchestration (`orchestrator.py`)
ClawBot is no longer a single script. When you ask it to build a full project or app:
- It switches to the "Manager".
- Spawns a **Planner Agent** (reads `skills/agents/planner.md`).
- Spawns **Worker Agents** to do parallel chunks of work.

### 3. 🧠 Obsidian Second Brain (`skills/obsidian_brain/SKILL.md`)
ClawBot maintains a human-like memory. Instead of jumping straight into action, it dumps reasoning into `_scratchpad.md` inside its Vault, links files recursively like an Obsidian knowledge graph, and saves states so you can pick up exactly where you left off tomorrow.

### 4. 🛠️ Self-Healing Code Execution (`self_healing.py`)
When ClawBot writes custom Python scripts to solve a problem, it runs them directly in your environment. If the script throws a `Traceback` or `SyntaxError`, the agent catches the error, re-analyzes, and **iteratively fixes its own code** up to 5 times.

### 5. 🔊 Voice Interface (`voice.py`)
Native support for:
- **Speech-to-Text**: Give commands using your voice in English or Hindi.
- **Text-to-Speech**: If your prompt includes triggers like *bol*, *bata*, or *speak*, ClawBot will automatically narrate its response back to you using Neural Voices (`edge-tts`).

### 6. 🔍 Smart Local File Search / RAG (`rag.py`)
Uses the `local_search` action to instantly read across `.txt`, `.pdf`, `.docx`, and code files on your hard drive to find answers, instead of blindly guessing where things are.

### 7. ⏱️ Background Daemon (`daemon.py`)
Reads the `HEARTBEAT.md` file. You can schedule tasks (e.g., "Check emails every 1 hour"), and the daemon will secretly wake up ClawBot in the background to do them without disturbing your screen.

### 8. 🔁 Workflow Cloning (`workflows.py`)
*Demonstration Learning*: Tell ClawBot to start recording your actions, do a tedious task once (like formatting an excel sheet), and then ClawBot can "replay" that exact workflow autonomously in the future.

---

## 🧰 The Massive 175+ Skills Library

ClawBot comes pre-installed with over **175 specialized Skills** (`/skills/*`). You can ask ClawBot to use any of these skills organically during chat, empowering it with deep domain knowledge for specific tasks:

1. **💻 Coding & Architecture Patterns**: `python-patterns`, `django-patterns`, `golang-patterns`, `rust-patterns`, `cpp-coding-standards`, `laravel-patterns`, `api-design`, `mcp-server-patterns`
2. **🤖 AI & Agentic Engineering**: `autonomous-loops`, `continuous-agent-loop`, `agentic-engineering`, `eval-harness`
3. **🎬 Video & Media Processing**: `capcut` (Automated Video Execution), `video-editing`, `openai-image-gen`, `sherpa-onnx-tts`
4. **📱 App Integrations**: `obsidian`, `notion`, `apple-notes`, `slack`, `discord`, `trello`
5. **🔍 Deep Research**: `deep-research`, `gitnexus`, `market-research`

---

## 🚀 How to Run

1. **Standard CLI / Desktop Automation:**
   ```bash
   clawbot
   ```
2. **Setup Telegram:**
   In the CLI, choose "Connect Telegram Bot", paste your Token from `@BotFather`, and control your PC from your phone anywhere in the world!
