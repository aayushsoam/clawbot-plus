# 🤖 ClawBot Plus — AI-Powered Computer Control Agent

<p align="center">
  <strong>Your PC. Your AI. Full Control.</strong>
</p>

<p align="center">
  <a href="https://github.com/aayushsoam/clawbot-plus/releases"><img src="https://img.shields.io/github/v/release/aayushsoam/clawbot-plus?include_prereleases&style=for-the-badge" alt="GitHub release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
  <a href="https://github.com/aayushsoam/clawbot-plus/stargazers"><img src="https://img.shields.io/github/stars/aayushsoam/clawbot-plus?style=for-the-badge" alt="Stars"></a>
  <a href="https://pypi.org/project/clawbot-plus/"><img src="https://img.shields.io/badge/pip-clawbot--plus-orange?style=for-the-badge" alt="PyPI"></a>
</p>

**ClawBot Plus** is a _personal AI assistant_ that takes full control of your Windows PC. It can open apps, write code, browse the web, generate presentations, search the internet, control system settings, and talk to you — all from a single CLI. Connect it to Telegram, and you can control your PC from your phone too.

If you want a personal, single-user AI that feels local, fast, and always-on — this is it.

## Install (recommended)

Runtime: **Python 3.11+**

```bash
pip install clawbot-plus
clawbot
```

That's it. ClawBot will auto-detect your system, scan your apps, and set up its workspace on first run.

## Quick Start

```bash
# Start ClawBot
clawbot

# Choose your AI provider (Gemini, OpenAI, Groq, Ollama, GitHub Models, NVIDIA NIM, etc.)
# Choose your model
# Start giving commands!

❯ open chrome and go to youtube
❯ make a portfolio website
❯ what's the weather today
❯ /voice   # Start voice mode
❯ switch   # Change AI model
❯ quit     # Exit
```

## From Source (development)

```bash
git clone https://github.com/aayushsoam/clawbot-plus.git
cd clawbot-plus
pip install -e .
clawbot
```

## Supported AI Providers

| Provider | Models | Auth |
|---|---|---|
| 🔷 **Google Gemini** | gemini-3.1-pro, gemini-2.5-flash, gemini-2.0-flash, etc. | `GEMINI_API_KEY` |
| 🔵 **OpenAI** | gpt-4o, gpt-4.1-mini, o3-mini, o4-mini | `OPENAI_API_KEY` |
| 🟠 **Anthropic** | claude-3-7-sonnet, claude-3-5-sonnet, claude-3-opus | `ANTHROPIC_API_KEY` |
| ⚡ **Groq** | llama-3.3-70b-versatile, gemma2-9b-it | `GROQ_API_KEY` |
| 🐋 **DeepSeek** | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| 🟩 **NVIDIA NIM** | nemotron-120b, llama-3.3-70b, deepseek-r1, phi-4 | `NVIDIA_API_KEY` |
| 🌙 **Kimi (Moonshot)** | moonshot-v1-8k/32k/128k | `MOONSHOT_API_KEY` |
| 🐙 **GitHub Models** | gpt-4o, gpt-4.1, Codestral-2501, Llama-3.3-70B | `GITHUB_TOKEN` |
| 🦙 **Ollama (Local)** | qwen3-vl, llama3.3, deepseek-r1, mistral, phi3 | Free (local) |
| ☁️ **Ollama (Cloud)** | Same as local, custom host | `OLLAMA_BASE_URL` |

## Highlights

- **🖥️ Full Computer Control** — open apps, click, type, scroll, screenshot, drag & drop. ClawBot sees your screen and acts.
- **💻 Senior Developer Coding** — writes production-quality code with separate HTML/CSS/JS files, verifies via shell, and shows output.
- **🔊 Voice Mode** — `/voice` to talk to ClawBot using your microphone. It speaks back using Edge TTS.
- **📱 Telegram Bot** — connect your Telegram bot and control your PC from your phone.
- **🧠 Persistent Memory** — remembers your name, preferences, past sessions, and daily logs across restarts.
- **🛡️ Anti-Loop Engine** — detects when the AI is stuck and forces a different approach or graceful exit.
- **🔍 Web Search** — search the web and fetch pages without opening a browser.
- **📊 PPT Generation** — `generate_ppt` action creates professional PowerPoint presentations.
- **🎬 Video Generation** — local Python or cloud API video creation via Koda-Stack.
- **🤖 Multi-Agent Swarm** — spawn worker agents for complex projects (ClawTeam).
- **🔒 Security Layer** — dangerous commands are blocked. All shell commands are audited.
- **📦 Skills System** — extensible SKILL.md-based plugin architecture for CCTV, CapCut, LaTeX, Office docs, and more.

## How It Works

```
         You (CLI / Telegram / Voice)
                    │
                    ▼
         ┌──────────────────┐
         │   ClawBot Agent   │
         │  (Python + LLM)   │
         └────────┬─────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
 🖥️ System    💻 Code       🌐 Browser
 Control      Engine        Automation
 (PyAutoGUI   (write_file   (browser-use
  + Win32)     read_file     Agent)
               shell)
```

## Key Subsystems

- **Computer Agent** (`clawbot/computer/agent.py`) — the brain. Receives tasks, plans actions, executes them, and learns.
- **CLI** (`clawbot/cli.py`) — the face. Interactive prompt with model selection, mode switching, and live task execution.
- **Telegram Bot** (`clawbot/computer/telegram_bot.py`) — remote control from your phone.
- **Voice Engine** (`clawbot/computer/voice.py`) — speech-to-text + text-to-speech loop.
- **Skills** (`skills/`) — modular capabilities loaded on-demand based on task keywords.
- **Memory** (`~/.clawbot/`) — sessions, daily logs, preferences, and persona files.

## Workspace & Persona

- Workspace root: `~/.clawbot/workspace/`
- Persona files: `IDENTITY.md`, `SOUL.md`, `USER.md`, `AGENTS.md`, `BOOTSTRAP.md`
- Skills: `skills/<skill_name>/SKILL.md`
- Sessions: `~/.clawbot/sessions/` (one `.md` per task)
- Daily memory: `~/.clawbot/memory/` (one `.md` per day)

## Configuration

Minimal `~/.clawbot/clawbot.json`:

```json
{
  "default_provider": "🔷 Google Gemini (Free)",
  "default_model": "gemini-2.5-flash"
}
```

## CLI Commands

| Command | Action |
|---|---|
| `clawbot` | Start the interactive CLI |
| `clawbot --version` | Show version |
| `clawbot devices` | Manage Claw3D device connections |
| `clawbot tunnel` | Setup remote access tunnel |
| `/voice` | Start voice control mode |
| `/video` | Switch to video generation mode |
| `/code` | Route tasks to OpenCode |
| `/normal` | Back to standard agent mode |
| `switch` | Change AI provider/model |
| `quit` | Exit ClawBot |

## Chat Commands (Telegram)

Send these from Telegram when connected:

- Any text → executes as a task on your PC
- Images → analyzed by vision models
- Voice messages → transcribed and executed

## Tech Stack

- **Python 3.11+** — core runtime
- **browser-use** — LLM classes and browser automation
- **PyAutoGUI** — screen control, clicks, typing
- **pywin32** — Windows native API (UIAutomation)
- **Rich** — beautiful terminal UI
- **InquirerPy** — interactive prompts
- **edge-tts** — text-to-speech
- **SpeechRecognition** — voice input
- **python-telegram-bot** — Telegram integration
- **Pillow** — image processing for vision
- **httpx** — async HTTP client

## Project Structure

```
clawbot/
  __init__.py
  cli.py              # Main CLI entry point
  computer/
    agent.py           # Core AI agent loop
    telegram_bot.py    # Telegram integration
    voice.py           # Voice mode
    actions.py         # System actions
    system_control.py  # OS-level controls
    window_manager.py  # Window focus/snap
    security.py        # Command auditing
    gateway.py         # Claw3D WebSocket gateway
    memory_search.py   # RAG-based memory search
    self_healing.py    # Auto-fix failed code
    workflows.py       # Macro recording/replay
    orchestrator.py    # Multi-agent coordination
  clawteam/            # Multi-agent swarm system
skills/                # Extensible skill plugins
workspace/             # Persona & identity files
agents/                # AI reviewer/planner agents
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=aayushsoam/clawbot-plus&type=date&legend=top-left)](https://www.star-history.com/#aayushsoam/clawbot-plus&type=date&legend=top-left)

## Built By

**ClawBot Plus** was built by **Aayush Soam** with significant contributions from **Claude** (Anthropic) — pair-programmed from architecture to deployment.

- 👤 [Aayush Soam](https://github.com/aayushsoam) — Creator, Vision & Product
- 🤖 [Claude](https://claude.ai) (Anthropic) — Co-Developer, Architecture & Agent Engineering

## License

MIT
