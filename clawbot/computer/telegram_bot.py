"""
🤖 ClawBot Telegram Bot — Remote Control via Telegram
Lets you control ClawBot Computer Agent from anywhere via Telegram.
Shows step-by-step progress + screenshots in Telegram chat.

Setup:
1. Talk to @BotFather on Telegram → /newbot → get TOKEN
2. Set environment variables:
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   OLLAMA_BASE_URL=http://your-ollama-url:11434
3. Run: python telegram_bot.py

To get your Chat ID:
   - Send /start to your bot
   - Open https://api.telegram.org/bot<TOKEN>/getUpdates
   - Find "chat":{"id": XXXXXXXX}
"""

import os
import sys
import asyncio
import base64
import logging
import time
from io import BytesIO
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load env from ~/.clawbot/.env
env_file = Path.home() / '.clawbot' / '.env'
if env_file.exists():
    load_dotenv(env_file)

# Also load from current directory .env if exists
load_dotenv()

# Force load variables explicitly just in case
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip().strip("'").strip('"')

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ── Setup paths ──
COMPUTER_DIR = Path(__file__).parent.parent / "computer"
if str(COMPUTER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPUTER_DIR))

# ── Logging ──
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ──
# We must load these AFTER the env_file parsing is complete.
def get_bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN", "")

def get_authorized_chat_id():
    return os.getenv("TELEGRAM_CHAT_ID", "")

# ════════════════════════════════════════════════════════
# 🤖 LLM SETUP — Same as ClawBot CLI
# ════════════════════════════════════════════════════════

import json
CHAT_HISTORY_FILE = Path.home() / '.clawbot' / 'workspace' / 'telegram_history.json'

def load_chat_history() -> list[str]:
    if CHAT_HISTORY_FILE.exists():
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_chat_history(history: list[str]):
    try:
        CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

CHAT_HISTORY: list[str] = load_chat_history()

def create_default_llm():
    """Create LLM instance using environment variables from CLI."""
    provider_name = os.getenv("CLAWBOT_TELEGRAM_PROVIDER")
    model = os.getenv("CLAWBOT_TELEGRAM_MODEL")
    api_key = os.getenv("CLAWBOT_TELEGRAM_API_KEY")

    if provider_name and model:
        try:
            # Import providers dictionary and factory from cli
            from clawbot.cli import PROVIDERS, create_llm
            if provider_name in PROVIDERS:
                provider_info = PROVIDERS[provider_name]
                logger.info(f"🤖 Linked CLI LLM: {model} @ {provider_name}")
                return create_llm(provider_info, model, api_key)
        except Exception as e:
            logger.error(f"Failed to load CLI LLM: {e}")
            
    # Fallback if env vars not found
    from browser_use.llm import ChatOllama
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_fallback = os.getenv("TELEGRAM_BOT_MODEL", "qwen3.5:cloud")
    logger.info(f"🤖 Default LLM: {model_fallback} @ {base_url}")
    return ChatOllama(model=model_fallback, host=base_url)


# ════════════════════════════════════════════════════════
# 📨 TELEGRAM OUTPUT — Replaces console.print for Telegram
# ════════════════════════════════════════════════════════

class TelegramOutput:
    """
    Captures ClawBot agent output and sends to Telegram.
    Batches messages to avoid Telegram rate limits.
    """
    
    def __init__(self, bot: Bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self.buffer: list[str] = []
        self.last_flush = time.time()
        self.message_id = None  # For editing existing message
        self.step_count = 0
    
    async def send(self, text: str):
        """Send a message to Telegram."""
        try:
            # Clean rich markup
            clean = self._clean_markup(text)
            if not clean.strip():
                return
            
            self.buffer.append(clean)
            
            # Flush every 2 seconds or every 5 lines
            if time.time() - self.last_flush > 2 or len(self.buffer) >= 5:
                await self.flush()
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
    
    async def flush(self):
        """Flush buffer to Telegram."""
        if not self.buffer:
            return
        
        text = "\n".join(self.buffer)
        self.buffer = []
        self.last_flush = time.time()
        
        try:
            # Truncate if too long (Telegram limit is 4096)
            if len(text) > 3900:
                text = text[:3900] + "\n... (truncated)"
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=None  # Plain text to avoid markdown issues
            )
        except Exception as e:
            logger.error(f"Telegram flush error: {e}")
    
    async def send_photo(self, image_bytes: bytes, caption: str = ""):
        """Send a screenshot to Telegram."""
        try:
            await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=image_bytes,
                caption=caption[:200] if caption else "📸 Screenshot"
            )
        except Exception as e:
            logger.error(f"Telegram photo error: {e}")
    
    def _clean_markup(self, text: str) -> str:
        """Remove Rich markup tags from text."""
        import re
        # Remove [color], [bold], [dim], etc.
        clean = re.sub(r'\[/?[a-zA-Z\s#0-9_]+\]', '', text)
        # Remove ╭╰╮╯│─ box characters
        clean = re.sub(r'[╭╰╮╯│─═]+', '', clean)
        return clean.strip()


# ════════════════════════════════════════════════════════
# 🚀 ClawBot RUNNER — Runs tasks with Telegram output
# ════════════════════════════════════════════════════════

is_task_running = False
cancel_task = False

async def run_ClawBot_task(task: str, tg_output: TelegramOutput):
    """Run a ClawBot computer agent task with Telegram output."""
    from agent import run_computer_task as _original_run
    from agent import (
        load_memory, discover_apps, build_app_context, get_relevant_learnings,
        get_system_context, take_full_screenshot_b64, take_active_window_screenshot_b64,
        run_shell, _ask_llm, _parse_json, record_task, extract_file_paths,
        get_skills_context, get_openclaw_memory, append_daily_memory
    )
    from actions import reliable_click, reliable_type, smart_wait, ensure_window_focus, drag_and_drop
    from security import is_command_safe, log_action
    from system_control import (
        set_volume, mute_toggle, set_brightness, wifi_toggle, bluetooth_toggle,
        get_system_info, get_running_processes, kill_process,
        lock_screen, shutdown, restart, sleep_pc, create_file
    )
    from window_manager import (
        list_windows, focus_window, minimize_window, maximize_window,
        close_window, snap_window
    )
    import pyautogui
    
    # Setup
    llm = create_default_llm()
    sys_context = get_system_context()
    mem = load_memory()
    app_data = discover_apps()
    app_context = build_app_context(app_data)
    skills_context = get_skills_context()
    learnings = get_relevant_learnings(mem, task)
    openclaw_memory = get_openclaw_memory()
    
    append_daily_memory("TELEGRAM", task)
    
    width, height = pyautogui.size()
    memory: list[dict] = []
    needs_screenshot = False
    extra_images = extract_file_paths(task)
    task_success = False
    
    await tg_output.send(
        f"🤖 ClawBot — Task Started\n"
        f"📋 {task}\n"
        f"📱 Apps: {app_data.get('app_count', 0)} | 🧠 Memory: {len(mem.get('tasks', []))} tasks\n"
        f"🔒 Security: Active"
    )
    
    video_engine = os.environ.get('CLAWBOT_VIDEO_ENGINE', 'cloud')
    video_engine_rule = ""
    if video_engine == 'local':
        video_engine_rule = "- **VIDEO GENERATION:** The user has strictly chosen LOCAL PYTHON. Do NOT use fal.ai or prompt the user for paid cloud services. ALWAYS write local python scripts to generate videos."
    elif video_engine == 'cloud':
        video_engine_rule = "- **VIDEO GENERATION:** The user has chosen CLOUD APIs."

    # System Prompt (same as agent.py)
    SYSTEM = f"""You are ClawBot — an intelligent AI assistant with FULL CONTROL of this Windows {width}x{height} PC.
You are precise, efficient, and never repeat failing actions.

{f"{chr(10)}{openclaw_memory}{chr(10)}" if openclaw_memory else ""}

{sys_context}

You know every app installed and how humans use them.

{app_context}

{f"{chr(10)}{skills_context}" if skills_context else ""}

{f"MEMORY (learn from past):{chr(10)}{learnings}" if learnings else ""}

STRATEGY (follow in order of preference):
1. Direct system commands FIRST — shell, system_control actions (instant, most reliable)
2. Keyboard shortcuts next — hotkeys, Ctrl+shortcuts (fast, reliable)
3. Focus the target app BEFORE any GUI interaction
4. GUI clicks ONLY as last resort (after 1-3 fail)

ACTIONS — Return ONE JSON per step with "thought":

--- SYSTEM CONTROL (preferred — instant, no GUI needed) ---
Shell:            {{"thought":"...", "action":"shell",            "command":"start chrome"}}
Volume:           {{"thought":"...", "action":"set_volume",       "level":50}}
Mute:             {{"thought":"...", "action":"mute_toggle"}}
Brightness:       {{"thought":"...", "action":"set_brightness",   "level":80}}
WiFi:             {{"thought":"...", "action":"wifi",             "enable":true}}
Bluetooth:        {{"thought":"...", "action":"bluetooth",        "enable":true}}
System info:      {{"thought":"...", "action":"system_info"}}
Running apps:     {{"thought":"...", "action":"list_processes"}}
Kill app:         {{"thought":"...", "action":"kill_process",     "name":"notepad"}}
Lock screen:      {{"thought":"...", "action":"lock_screen"}}
Shutdown:         {{"thought":"...", "action":"shutdown",         "delay":30}}
Restart:          {{"thought":"...", "action":"restart",          "delay":10}}
Sleep:            {{"thought":"...", "action":"sleep"}}
File create:      {{"thought":"...", "action":"create_file",      "path":"C:/test.txt", "content":"hello"}}
Open file/folder: {{"thought":"...", "action":"shell",            "command":"start explorer C:\\Users"}}

--- WINDOW MANAGEMENT ---
Focus app:        {{"thought":"...", "action":"focus_app",        "window_title":"WhatsApp"}}
Minimize:         {{"thought":"...", "action":"minimize_window",  "window_title":"Notepad"}}
Maximize:         {{"thought":"...", "action":"maximize_window",  "window_title":"Chrome"}}
Close window:     {{"thought":"...", "action":"close_window",     "window_title":"Calculator"}}
Snap window:      {{"thought":"...", "action":"snap_window",      "window_title":"Chrome", "position":"left"}}
List windows:     {{"thought":"...", "action":"list_windows"}}

--- GUI INTERACTIONS (use only when system commands won't work) ---
Click:            {{"thought":"...", "action":"click",            "x":500, "y":300}}
Double-click:     {{"thought":"...", "action":"double_click",     "x":500, "y":300}}
Right-click:      {{"thought":"...", "action":"right_click",      "x":500, "y":300}}
Type:             {{"thought":"...", "action":"type",             "text":"hello"}}
Hotkey:           {{"thought":"...", "action":"hotkey",           "keys":["ctrl","c"]}}
Press key:        {{"thought":"...", "action":"press",            "key":"enter"}}
Scroll:           {{"thought":"...", "action":"scroll",           "direction":"down", "amount":3, "x":640, "y":400}}
Drag:             {{"thought":"...", "action":"drag",             "x1":100, "y1":100, "x2":500, "y2":500}}

--- WEB SEARCH (instant info without browser) ---
Web search:       {{"thought":"...", "action":"web_search",       "query":"latest news about AI"}}
Web fetch:        {{"thought":"...", "action":"web_fetch",        "url":"https://example.com"}}

--- FLOW CONTROL ---
Done:             {{"thought":"...", "action":"done",             "result":"what was accomplished"}}
Screenshot:       {{"thought":"...", "action":"take_screenshot"}}

--- CODE EXECUTION (self-healing — auto-fixes errors up to 5 times) ---
Run code:         {{"thought":"...", "action":"run_code",          "language":"python", "code":"print('hello')", "task_context":"what this code should do"}}

--- KNOWLEDGE & MEMORY RETRIEVAL ---
Local file search:    {{"thought":"...", "action":"local_search",      "query":"electricity bill amount"}}
Memory search:    {{"thought":"...", "action":"memory_search",     "query":"user preferred programming topics"}}
--- WORKFLOW MACROS (record and replay action sequences) ---
List workflows:   {{"thought":"...", "action":"list_workflows"}}
Replay workflow:  {{"thought":"...", "action":"replay_workflow",   "name":"daily_backup"}}
Orchestrate:      {{"thought":"...", "action":"orchestrate",       "task":"build a complete portfolio website with 4 pages"}}
Speak:            {{"thought":"...", "action":"speak",             "text":"Hello", "voice":"hi-IN-MadhurNeural"}}

--- ADVANCED CAPABILITIES ---
Generate PPT:     {{"thought":"...", "action":"generate_ppt", "slides":[{{"title":"Slide 1", "points":["Point 1", "Point 2"]}}], "theme":"dark"}}
Coding Mode:      {{"thought":"...", "action":"coding_mode", "task":"write a calculator string parsing logic"}}

CRITICAL RULES:
- SECURITY: All shell commands are checked. Dangerous commands are BLOCKED.
- If the user asks to build a project, app, or website: ALWAYS create a dedicated folder for it first.
- **BINARY FILES:** NEVER use `create_file` to generate `.pptx`, `.xlsx`, `.docx`, or `.pdf`. Use `generate_ppt` for PowerPoint, and `run_code` for others.
- If task output was already produced, call `done` IMMEDIATELY instead of re-running.
- After clicking a text field, IMMEDIATELY type in the next step.
- NEVER repeat the same action more than 2 times. If it fails, use a COMPLETELY DIFFERENT approach.
- Before any GUI click/type, use "focus_app" first.
- For information/search tasks, use "web_search" FIRST before opening a browser.
- Output ONLY valid JSON.
{video_engine_rule}"""

    win_offset = (0, 0)
    log_action("telegram_task_start", task)
    
    for step in range(1, 41):
        global cancel_task
        if cancel_task:
            await tg_output.send("🛑 **Task stopped by user.**")
            cancel_task = False
            task_success = False
            break
            
        mem_text = ""
        if memory:
            mem_text = "\nSession history:\n" + "\n".join(
                f"  {m['step']}. {m['summary']}" for m in memory[-8:]
            )
        
        prompt = f"{SYSTEM}{mem_text}\n\nTask: {task}\n"
        
        # Loop detection
        if len(memory) >= 3:
            last_3 = [m['summary'] for m in memory[-3:]]
            if len(set(last_3)) == 1 or all('screen(' in s for s in last_3):
                prompt += "\n⚠️ CRITICAL: Same action 3x! Use COMPLETELY DIFFERENT approach.\n"
                await tg_output.send("🔄 Loop detected! Switching strategy...")
            elif len(memory) >= 2 and memory[-1]['summary'] == memory[-2]['summary']:
                prompt += "\n⚠️ Same action twice. Switch strategy if fails again.\n"
        
        # Completion detection (anti-repeat) — same as agent.py
        completion_signals = ['web search', 'web fetch', 'Self-Healing: Success', 'Created:', 'opened', 'Task Complete', 'saved', 'Code (', 'SUCCESS after', 'success after']
        if len(memory) >= 1:
            recent_summaries = ' '.join(m['summary'] for m in memory[-6:])
            if any(sig.lower() in recent_summaries.lower() for sig in completion_signals):
                prompt += "\n✅ CRITICAL: Your session history shows the task output was already produced (code ran successfully / file created / search done). You MUST call `done` IMMEDIATELY with a summary. Do NOT run any more code or search again!\n"
        
        if needs_screenshot:
            prompt += "Screenshot attached. Analyze and decide."
        else:
            prompt += "No screenshot. Use system commands first."
        
        # Take screenshot if needed
        b64 = None
        if needs_screenshot:
            if step == 1 or len(memory) == 0:
                b64 = take_full_screenshot_b64()
                win_offset = (0, 0)
            else:
                time.sleep(0.6)
                b64, win_offset = take_active_window_screenshot_b64()
            needs_screenshot = False
            
            # Send screenshot to Telegram
            if b64:
                try:
                    img_bytes = base64.b64decode(b64)
                    await tg_output.send_photo(img_bytes, f"📸 Step {step}")
                except Exception:
                    pass
        
        try:
            raw = await _ask_llm(llm, prompt, b64_img=b64, extra_images=extra_images)
            action = _parse_json(raw)
            act = action.get('action')
            thought = action.get('thought', '')
            
            step_msg = f"📍 Step {step}"
            if thought:
                step_msg += f"\n🧠 {thought}"
            
            # ══════ EXECUTE ══════
            
            # --- System Control ---
            if act == 'set_volume':
                level = int(action.get('level', 50))
                set_volume(level)
                step_msg += f"\n🔊 Volume → {level}%"
                memory.append({"step": step, "summary": f"Volume: {level}%"})
            
            elif act == 'mute_toggle':
                mute_toggle()
                step_msg += "\n🔇 Mute toggled"
                memory.append({"step": step, "summary": "Mute toggled"})
            
            elif act == 'set_brightness':
                level = int(action.get('level', 50))
                out = set_brightness(level)
                step_msg += f"\n💡 Brightness → {level}%"
                memory.append({"step": step, "summary": f"Brightness: {level}%"})
            
            elif act == 'wifi':
                enable = action.get('enable', True)
                out = wifi_toggle(enable)
                step_msg += f"\n📡 WiFi → {'ON' if enable else 'OFF'}: {out[:50]}"
                memory.append({"step": step, "summary": f"WiFi: {'ON' if enable else 'OFF'}"})
            
            elif act == 'bluetooth':
                enable = action.get('enable', True)
                out = bluetooth_toggle(enable)
                step_msg += f"\n🔵 Bluetooth → {'ON' if enable else 'OFF'}: {out[:50]}"
                memory.append({"step": step, "summary": f"BT: {'ON' if enable else 'OFF'}"})
            
            elif act == 'system_info':
                out = get_system_info()
                step_msg += f"\n📊 {out[:200]}"
                memory.append({"step": step, "summary": "System info retrieved"})
            
            elif act == 'list_processes':
                out = get_running_processes()
                step_msg += f"\n📋 {out[:300]}"
                memory.append({"step": step, "summary": "Listed processes"})
            
            elif act == 'kill_process':
                name = action.get('name', '')
                out = kill_process(name)
                step_msg += f"\n💀 Kill {name}: {out}"
                memory.append({"step": step, "summary": f"Kill: {name}"})
            
            elif act == 'lock_screen':
                lock_screen()
                step_msg += "\n🔒 Screen locked"
                memory.append({"step": step, "summary": "Locked"})
            
            elif act == 'shutdown':
                delay = int(action.get('delay', 30))
                shutdown(delay)
                step_msg += f"\n⚡ Shutdown in {delay}s"
                memory.append({"step": step, "summary": f"Shutdown: {delay}s"})
            
            elif act == 'restart':
                delay = int(action.get('delay', 10))
                restart(delay)
                step_msg += f"\n🔄 Restart in {delay}s"
                memory.append({"step": step, "summary": f"Restart: {delay}s"})
            
            elif act == 'sleep':
                sleep_pc()
                step_msg += "\n😴 Sleeping..."
                memory.append({"step": step, "summary": "Sleep"})
            
            elif act == 'create_file':
                fpath = action.get('path', '')
                content = action.get('content', '')
                create_file(fpath, content)
                step_msg += f"\n📄 Created: {fpath}"
                memory.append({"step": step, "summary": f"File: {fpath}"})
            
            # --- Window Management ---
            elif act == 'focus_app':
                title = action.get('window_title', '')
                result = focus_window(title)
                step_msg += f"\n🪟 Focus: {title} → {result}"
                memory.append({"step": step, "summary": f"Focused: {title}"})
                needs_screenshot = True
            
            elif act == 'minimize_window':
                title = action.get('window_title', '')
                result = minimize_window(title)
                step_msg += f"\n⬇️ Minimize: {title}"
                memory.append({"step": step, "summary": f"Minimized: {title}"})
            
            elif act == 'maximize_window':
                title = action.get('window_title', '')
                result = maximize_window(title)
                step_msg += f"\n⬆️ Maximize: {title}"
                memory.append({"step": step, "summary": f"Maximized: {title}"})
            
            elif act == 'close_window':
                title = action.get('window_title', '')
                close_window(title)
                step_msg += f"\n❌ Closed: {title}"
                memory.append({"step": step, "summary": f"Closed: {title}"})
            
            elif act == 'snap_window':
                title = action.get('window_title', '')
                pos = action.get('position', 'left')
                snap_window(title, pos)
                step_msg += f"\n📐 Snap: {title} → {pos}"
                memory.append({"step": step, "summary": f"Snap: {title} {pos}"})
            
            elif act == 'list_windows':
                windows = list_windows()
                win_text = "\n".join(f"  • {w.get('title', '?')}" for w in windows[:6])
                step_msg += f"\n🪟 Windows:\n{win_text}"
                memory.append({"step": step, "summary": f"{len(windows)} windows"})
            
            # --- GUI Actions ---
            elif act in ('click', 'double_click', 'right_click'):
                raw_x, raw_y = int(action.get('x', 0)), int(action.get('y', 0))
                ox, oy = win_offset
                x, y = raw_x + ox, raw_y + oy
                label = {'click': '🖱️', 'double_click': '🖱️🖱️', 'right_click': '🖱️R'}[act]
                reliable_click(x, y, click_type=act)
                step_msg += f"\n{label} Click ({x},{y})"
                memory.append({"step": step, "summary": f"{label} screen({x},{y})"})
                smart_wait(act)
                needs_screenshot = True
            
            elif act == 'type':
                text = action.get('text', '')
                ensure_window_focus()
                reliable_type(text)
                step_msg += f"\n⌨️ Typed: '{text[:40]}'"
                memory.append({"step": step, "summary": f"Typed: '{text[:40]}'"})
                smart_wait('type')
                needs_screenshot = True
            
            elif act == 'press':
                key = action.get('key', 'enter')
                ensure_window_focus()
                pyautogui.press(key)
                step_msg += f"\n⌨️ Press: {key}"
                memory.append({"step": step, "summary": f"Pressed: {key}"})
                smart_wait('press')
                needs_screenshot = True
            
            elif act == 'hotkey':
                keys = action.get('keys', [])
                ensure_window_focus()
                pyautogui.hotkey(*keys)
                step_msg += f"\n⌨️ Hotkey: {'+'.join(keys)}"
                memory.append({"step": step, "summary": f"Hotkey: {'+'.join(keys)}"})
                smart_wait('hotkey')
                needs_screenshot = True
            
            elif act == 'scroll':
                direction = action.get('direction', 'down')
                amount = int(action.get('amount', 3))
                if 'x' in action and 'y' in action:
                    ox, oy = win_offset
                    sx, sy = int(action['x']) + ox, int(action['y']) + oy
                    pyautogui.moveTo(sx, sy, duration=0.2)
                pyautogui.scroll(-amount if direction == 'down' else amount)
                step_msg += f"\n🔄 Scroll {direction} ×{amount}"
                memory.append({"step": step, "summary": f"Scroll {direction} ×{amount}"})
                smart_wait('scroll')
                needs_screenshot = True
            
            elif act == 'drag':
                x1, y1 = int(action.get('x1', 0)), int(action.get('y1', 0))
                x2, y2 = int(action.get('x2', 0)), int(action.get('y2', 0))
                ox, oy = win_offset
                drag_and_drop(x1 + ox, y1 + oy, x2 + ox, y2 + oy)
                step_msg += f"\n↕️ Drag ({x1+ox},{y1+oy}) → ({x2+ox},{y2+oy})"
                memory.append({"step": step, "summary": f"Drag"})
                needs_screenshot = True
            
            elif act == 'take_screenshot':
                step_msg += "\n📸 Screenshot requested"
                needs_screenshot = True
                memory.append({"step": step, "summary": "Screenshot"})
            
            elif act == 'shell':
                cmd = action.get('command', '')
                out = run_shell(cmd)
                step_msg += f"\n⚡ Shell: `{cmd}`\n   → {out[:100]}"
                memory.append({"step": step, "summary": f"Shell: `{cmd[:30]}` → {out[:30]}"})
                smart_wait('shell')
                if cmd.strip().lower().startswith('start '):
                    needs_screenshot = True

            elif act == 'run_code':
                lang = action.get('language', 'python')
                code = action.get('code', '')
                ctx = action.get('task_context', task)
                step_msg += f"\n🔧 Self-Healing Code ({lang}):\n{code[:100]}..."
                try:
                    from self_healing import _run_code_with_healing_async
                    heal_result = await _run_code_with_healing_async(
                        lambda p, img=None: _ask_llm(llm, p), lang, code, ctx
                    )
                    if heal_result['success']:
                        output_text = heal_result.get('output', '')
                        step_msg += f"\n✅ Success (Attempts: {heal_result['attempts']})"
                        if output_text:
                            step_msg += f"\nOutput: {output_text[:120]}"
                        memory.append({"step": step, "summary": f"Code ({lang}) SUCCESS after {heal_result['attempts']} attempt(s): {output_text[:200]}"})
                        
                        # ── Auto-done: if code created a file, task is complete ──
                        file_signals = ['.pdf', '.pptx', '.xlsx', '.docx', '.mp4', '.png', 'saved', 'created', 'written']
                        if any(sig in output_text.lower() for sig in file_signals):
                            await tg_output.send(step_msg)
                            await tg_output.send(f"✅ Task Complete!\n\n📄 Output: {output_text[:300]}")
                            task_success = True
                            log_action("telegram_task_done", output_text[:200])
                            break
                    else:
                        step_msg += f"\n❌ Failed after {heal_result['attempts']} attempts"
                        memory.append({"step": step, "summary": f"Code ({lang}) FAILED after {heal_result['attempts']} attempts"})
                except Exception as e:
                    step_msg += f"\n❌ Self-healing error: {e}"
                    memory.append({"step": step, "summary": f"Self-healing error: {str(e)[:80]}"})

            elif act == 'generate_ppt':
                slides_data = action.get('slides', [])
                theme = action.get('theme', 'dark')
                out_path = action.get('output_path', None)
                ppt_title = action.get('title', 'Presentation')
                step_msg += f"\n🎨 Generating PPT: {ppt_title} ({theme} theme, {len(slides_data)} slides)"
                try:
                    from ppt_generator import create_ppt
                    saved_path = create_ppt(slides_data, output_path=out_path, theme=theme)
                    step_msg += f"\n✅ PPT Created: {saved_path}"
                    # Auto-open on PC
                    import subprocess as _sp
                    _sp.Popen(['start', '', saved_path], shell=True)
                    memory.append({"step": step, "summary": f"PPT Created: {saved_path}"})
                    # Auto-done
                    await tg_output.send(step_msg)
                    await tg_output.send(f"✅ PPT Ready!\n\n📊 {ppt_title}\n📁 Saved: {saved_path}\n🖥️ Opening in PowerPoint...")
                    task_success = True
                    log_action("telegram_task_done", f"PPT: {saved_path}")
                    break
                except ImportError:
                    import subprocess as _sp
                    _sp.run(['pip', 'install', 'python-pptx', '-q'], check=False)
                    from ppt_generator import create_ppt
                    saved_path = create_ppt(slides_data, output_path=out_path, theme=theme)
                    step_msg += f"\n✅ PPT Created: {saved_path}"
                    memory.append({"step": step, "summary": f"PPT Created: {saved_path}"})
                except Exception as e:
                    step_msg += f"\n❌ PPT error: {e}"
                    memory.append({"step": step, "summary": f"PPT error: {str(e)[:80]}"})

            elif act == 'web_search':
                query = action.get('query', '')
                step_msg += f"\n🔍 Web Search: {query}"
                try:
                    import ollama as ollama_api
                    api_key = os.environ.get('OLLAMA_API_KEY', '')
                    if not api_key:
                        step_msg += "\n❌ OLLAMA_API_KEY set nahi hai!"
                        memory.append({"step": step, "summary": "Web search failed: no API key"})
                    else:
                        search_results = ollama_api.web_search(query=query)
                        results_text = ""
                        results_list = getattr(search_results, 'results', []) or []
                        for i, r in enumerate(results_list[:3], 1):
                            title = getattr(r, 'title', '') or ''
                            url = getattr(r, 'url', '') or ''
                            results_text += f"\n{i}. {title}\n  {url}"
                        step_msg += results_text
                        if results_text:
                            memory.append({"step": step, "summary": f"Web search '{query}': {len(results_list)} results"})
                        else:
                            memory.append({"step": step, "summary": f"Web search '{query}': no results"})
                except Exception as e:
                    step_msg += f"\n❌ Web search error: {e}"
                    memory.append({"step": step, "summary": f"Web search error: {str(e)[:60]}"})

            elif act == 'web_fetch':
                url = action.get('url', '')
                step_msg += f"\n🌐 Web Fetch: {url}"
                try:
                    import ollama as ollama_api
                    api_key = os.environ.get('OLLAMA_API_KEY', '')
                    if not api_key:
                        step_msg += "\n❌ OLLAMA_API_KEY set nahi hai!"
                    else:
                        fetch_result = ollama_api.web_fetch(url=url)
                        content = getattr(fetch_result, 'content', '') or str(fetch_result)
                        step_msg += f"\n📄 Fetched {len(content)} chars: {content[:100]}..."
                        memory.append({"step": step, "summary": f"Web fetch '{url}': {len(content)} chars"})
                except Exception as e:
                    step_msg += f"\n❌ Web fetch error: {e}"
                    memory.append({"step": step, "summary": f"Web fetch error: {str(e)[:60]}"})

            elif act == 'local_search':
                query = action.get('query', '')
                step_msg += f"\n📂 Local Search: {query}"
                try:
                    from rag import search as rag_search
                    results = rag_search(query, top_k=3)
                    if results:
                        step_msg += f"\nFound {len(results)} chunks."
                        memory.append({"step": step, "summary": f"Local search '{query}': found {len(results)} items"})
                    else:
                        step_msg += "\n⚠️ No results. Index files first."
                        memory.append({"step": step, "summary": f"Local search '{query}': no results"})
                except Exception as e:
                    step_msg += f"\n❌ RAG error: {e}"

            elif act == 'memory_search':
                query = action.get('query', '')
                step_msg += f"\n🧠 Memory Search: {query}"
                try:
                    from memory_search import search_memory
                    result_text = search_memory(query, limit=5)
                    step_msg += f"\n{result_text[:150]}..."
                    memory.append({"step": step, "summary": f"Memory Search '{query}': {len(result_text)} chars"})
                except Exception as e:
                    step_msg += f"\n❌ Memory Search error: {e}"

            elif act == 'list_workflows':
                step_msg += "\n📹 Saved Workflows:"
                try:
                    from workflows import list_workflows as wf_list
                    wfs = wf_list()
                    if wfs:
                        for w in wfs:
                            step_msg += f"\n  • {w['name']} ({w['total_steps']} steps)"
                        memory.append({"step": step, "summary": f"Listed {len(wfs)} workflows"})
                    else:
                        step_msg += "\n  No saved workflows."
                        memory.append({"step": step, "summary": "No saved workflows"})
                except Exception as e:
                    step_msg += f"\n❌ Workflow error: {e}"

            elif act == 'replay_workflow':
                wf_name = action.get('name', '')
                step_msg += f"\n▶️ Replaying workflow: {wf_name}"
                try:
                    from workflows import load_workflow, replay_workflow
                    wf = load_workflow(wf_name)
                    if wf:
                        await replay_workflow(wf, lambda a: None)
                        memory.append({"step": step, "summary": f"Replayed workflow: {wf_name}"})
                    else:
                        step_msg += f"\n⚠️ Workflow '{wf_name}' not found"
                except Exception as e:
                    step_msg += f"\n❌ Replay error: {e}"

            elif act == 'orchestrate':
                orch_task = action.get('task', task)
                step_msg += "\n🧠 Orchestrating complex task..."
                try:
                    from orchestrator import orchestrate_task
                    orch_result = await orchestrate_task(llm, _ask_llm, orch_task, run_computer_task)
                    c = orch_result['subtasks_completed']
                    step_msg += f"\n✅ Orchestration done: {c} subtasks completed."
                    memory.append({"step": step, "summary": f"Orchestrated: {c} subtasks done"})
                except Exception as e:
                    step_msg += f"\n❌ Orchestration error: {e}"

            elif act == 'speak':
                speak_text = action.get('text', '')
                speak_voice = action.get('voice', 'hi-IN-MadhurNeural')
                step_msg += f"\n🔊 Speaking: {speak_text[:50]}..."
                try:
                    from voice import speak_async
                    await speak_async(speak_text, speak_voice)
                    memory.append({"step": step, "summary": f"Spoke: {speak_text[:50]}"})
                except Exception as e:
                    step_msg += f"\n❌ TTS error: {e}"
            
            elif act == 'done':
                result = action.get('result', 'Done.')
                await tg_output.send(f"✅ ClawBot — Task Complete!\n\n{result}")
                task_success = True
                log_action("telegram_task_done", result)
                break
            
            else:
                step_msg += f"\n❓ Unknown: {act}"
            
            # Send step update to Telegram
            await tg_output.send(step_msg)
        
        except Exception as e:
            await tg_output.send(f"📍 Step {step}\n❌ Error: {str(e)[:100]}")
            memory.append({"step": step, "summary": f"Error: {str(e)[:60]}"})
            time.sleep(0.5)
    
    # Save memory
    record_task(mem, task, memory, task_success)
    if not task_success:
        await tg_output.send("⚠️ Task finished without explicit completion (max steps reached)")
    
    await tg_output.flush()


# ════════════════════════════════════════════════════════
# 📱 TELEGRAM HANDLERS
# ════════════════════════════════════════════════════════

is_task_running = False

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text(
        f"🤖 ClawBot — ClawBot Remote Control\n\n"
        f"Your Chat ID: {chat_id}\n\n"
        f"Commands:\n"
        f"  /computer <task> — Run a full PC automation task (UI, shell, files)\n"
        f"  /status — System info\n"
        f"  /screenshot — Take screenshot\n"
        f"  /windows — List open windows\n"
        f"  /processes — Running processes\n"
        f"  /stop — Stop current task\n\n"
        f"Normal text messages will just chat with the AI!"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System status."""
    if not _is_authorized(update):
        return
    
    from system_control import get_system_info, get_network_info
    info = get_system_info()
    net = get_network_info()
    await update.message.reply_text(f"📊 System Status\n\n{info}\n\n{net}")


async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Take and send a screenshot."""
    if not _is_authorized(update):
        return
    
    from agent import take_full_screenshot_b64
    b64 = take_full_screenshot_b64()
    if b64:
        img_bytes = base64.b64decode(b64)
        await update.message.reply_photo(photo=img_bytes, caption="📸 Current Screen")
    else:
        await update.message.reply_text("❌ Screenshot failed")


async def cmd_windows(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List open windows."""
    if not _is_authorized(update):
        return
    
    windows = list_windows()
    text = "🪟 Open Windows:\n\n"
    for w in windows[:15]:
        text += f"• {w.get('title', '?')} ({w.get('width', 0)}x{w.get('height', 0)})\n"
    await update.message.reply_text(text)


async def cmd_processes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List running processes."""
    if not _is_authorized(update):
        return
    
    from system_control import get_running_processes
    out = get_running_processes(top_n=20)
    await update.message.reply_text(f"📋 Top Processes:\n\n{out[:3500]}")


async def cmd_cctv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the CCTV Control Panel."""
    if not _is_authorized(update): return
    
    keyboard = [
        [InlineKeyboardButton("📸 Snapshot", callback_data="cctv_snap"),
         InlineKeyboardButton("📹 5s Live", callback_data="cctv_live")],
        [InlineKeyboardButton("🧠 AI Report", callback_data="cctv_report")],
        [InlineKeyboardButton("◀️ Left", callback_data="cctv_left"),
         InlineKeyboardButton("▶️ Right", callback_data="cctv_right")],
        [InlineKeyboardButton("🔼 Up", callback_data="cctv_up"),
         InlineKeyboardButton("🔽 Down", callback_data="cctv_down")],
        [InlineKeyboardButton("👮 Guard On", callback_data="cctv_mon_on"),
         InlineKeyboardButton("🛑 Guard Off", callback_data="cctv_mon_off")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛡️ **CCTV Control Panel**\n"
        "Choose an action below:", 
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_cctv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Acknowledge the button click
    
    data = query.data
    
    # Map callbacks to our existing commands
    try:
        if data == "cctv_snap":
            # Just take a snapshot directly here to avoid moving too much code
            from skills.cctv_expert.monitor import load_config, send_to_telegram
            import cv2
            await query.edit_message_text("📸 Capturing snapshot...")
            config = load_config()
            alias = "Home" if "Home" in config["cameras"] else next(iter(config["cameras"]), None)
            if alias:
                url = config["cameras"][alias]
                cap = cv2.VideoCapture(url)
                ret, frame = cap.read()
                if ret:
                    send_to_telegram(frame, caption=f"📸 Live View: {alias}")
                    await query.message.reply_text("✅ Snapshot sent.")
                else:
                    await query.message.reply_text("❌ Failed to reach stream.")
                cap.release()
            else:
                await query.message.reply_text("❌ No cameras registered.")
                
        elif data == "cctv_live":
            await cmd_live(update, context)
        elif data == "cctv_report":
            await cmd_report(update, context)
        elif data == "cctv_left":
            await cmd_left(update, context)
        elif data == "cctv_right":
            await cmd_right(update, context)
        elif data == "cctv_up":
            await cmd_up(update, context)
        elif data == "cctv_down":
            await cmd_down(update, context)
        elif data == "cctv_mon_on":
            await cmd_monitor_on(update, context)
        elif data == "cctv_mon_off":
            await cmd_monitor_off(update, context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")
        if data == "cctv_snap":
            # Just take a snapshot directly here to avoid moving too much code
            from skills.cctv_expert.monitor import load_config, send_to_telegram
            import cv2
            await query.edit_message_text("📸 Capturing snapshot...")
            config = load_config()
            alias = "Home" if "Home" in config["cameras"] else next(iter(config["cameras"]), None)
            if alias:
                url = config["cameras"][alias]
                cap = cv2.VideoCapture(url)
                ret, frame = cap.read()
                if ret:
                    send_to_telegram(frame, caption=f"📸 Live View: {alias}")
                    await query.message.reply_text("✅ Snapshot sent.")
                else:
                    await query.message.reply_text("❌ Failed to reach stream.")
                cap.release()
            else:
                await query.message.reply_text("❌ No cameras registered.")
                
        elif data == "cctv_live":
            await cmd_live(update, context)
        elif data == "cctv_report":
            await cmd_report(update, context)
        elif data == "cctv_left":
            await cmd_left(update, context)
        elif data == "cctv_right":
            await cmd_right(update, context)
        elif data == "cctv_up":
            await cmd_up(update, context)
        elif data == "cctv_down":
            await cmd_down(update, context)
        elif data == "cctv_mon_on":
            await cmd_monitor_on(update, context)
        elif data == "cctv_mon_off":
            await cmd_monitor_off(update, context)
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")

monitor_process = None

async def cmd_monitor_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the background AI monitoring."""
    if not _is_authorized(update): return
    global monitor_process
    
    if monitor_process and monitor_process.poll() is None:
        await update.effective_message.reply_text("👮 Monitor is already running!")
        return
        
    await update.effective_message.reply_text("👮 Starting AI Security Monitor...")
    import subprocess
    alias = "Home" # Default
    try:
        # Start as background process
        monitor_cmd = f'python skills/cctv_expert/monitor.py ai_monitor {alias}'
        monitor_process = subprocess.Popen(monitor_cmd, shell=True)
        await update.effective_message.reply_text(f"✅ AI Guard is now watching '{alias}' on background. Alerts will be sent to this chat.")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Monitor Start Error: {e}")

async def cmd_monitor_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the background AI monitoring."""
    if not _is_authorized(update): return
    global monitor_process
    
    if monitor_process:
        import subprocess
        # On windows, we need to kill the process tree
        subprocess.run(f"taskkill /F /T /PID {monitor_process.pid}", shell=True)
        monitor_process = None
        await update.effective_message.reply_text("🛑 AI Security Monitor STOPPED.")
    else:
        await update.effective_message.reply_text("❓ Monitor was not running.")

async def cmd_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    from skills.cctv_expert.monitor import move_camera
    res = move_camera("Home", "left")
    await update.effective_message.reply_text(res)

async def cmd_right(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    from skills.cctv_expert.monitor import move_camera
    res = move_camera("Home", "right")
    await update.effective_message.reply_text(res)

async def cmd_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    from skills.cctv_expert.monitor import move_camera
    res = move_camera("Home", "up")
    await update.effective_message.reply_text(res)

async def cmd_down(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    from skills.cctv_expert.monitor import move_camera
    res = move_camera("Home", "down")
    await update.effective_message.reply_text(res)

async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a 5-second video clip to Telegram."""
    if not _is_authorized(update): return
    await update.effective_message.reply_text("📹 Recording 5s live clip...")
    try:
        from skills.cctv_expert.monitor import load_config, record_video_burst
        config = load_config()
        url = config["cameras"].get("Home")
        if not url:
            await update.effective_message.reply_text("❌ Camera 'Home' not found.")
            return
        
        path = record_video_burst(url, duration=5)
        if path and os.path.exists(path):
            with open(path, 'rb') as video:
                await context.bot.send_video(chat_id=update.effective_chat.id, video=video, caption="📹 Live Clip (5s)")
        else:
            await update.effective_message.reply_text("❌ Failed to record video.")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Video error: {e}")

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI Analaysis of the current frame."""
    if not _is_authorized(update): return
    await update.effective_message.reply_text("🧠 AI is analyzing the camera feed...")
    try:
        from skills.cctv_expert.monitor import analyze_scene
        report = await analyze_scene("Home")
        await update.effective_message.reply_text(f"📋 **AI REPORT:**\n\n{report}")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Analysis error: {e}")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the currently running task."""
    global is_task_running, cancel_task
    
    if not _is_authorized(update):
        return
        
    if not is_task_running:
        await update.message.reply_text("✅ No task is currently running.")
        return
        
    cancel_task = True
    await update.message.reply_text("🛑 Stopping the current task... Please wait a moment.")


async def run_chat_task(text: str, tg_output: TelegramOutput):
    """A conversational mode with smart live-data fetching for factual queries."""
    from agent import _ask_llm
    import urllib.request
    global CHAT_HISTORY
    
    llm = create_default_llm()
    live_data = ""
    
    text_lower = text.lower()
    
    sys_prompt = (
            f"You are ClawBot — an AI assistant running DIRECTLY on the user's Windows PC via Telegram. "
            f"You are currently in CHAT mode. The user asked a conversational question.\n"
            f"CRITICAL RULES:\n"
            f"1. You cannot execute PC actions directly from here.\n"
            f"2. If the user wants a PC task done (e.g., open app, make file), tell them to prefix it with '/computer ' (e.g. '/computer open notepad').\n"
            f"3. If the user asks about the CCTV camera, tell them to literally type the command '/live' for a video clip or '/report' for an AI summary. DO NOT say you will do it, just tell them the commands to type.\n"
            f"4. Keep responses short, friendly, and in Hinglish if appropriate."
        )
    
    # ── Auto-fetch live data for weather queries ──
    weather_keywords = ["weather", "mausam", "temperature", "forecast", "rain", "humidity", "garmi", "sardi", "barish", "aaj ka mausam"]
    
    if any(kw in text_lower for kw in weather_keywords):
        try:
            # Extract city name — last non-keyword word
            city_hint = "Delhi"
            for word in text.split():
                if word.lower() not in weather_keywords and len(word) > 2 and not word.startswith('/'):
                    city_hint = word
            
            wttr_url = f"https://wttr.in/{city_hint.replace(' ', '+')}?format=4"
            req = urllib.request.Request(wttr_url, headers={'User-Agent': 'curl/7.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                weather_data = resp.read().decode('utf-8', errors='replace').strip()
            
            if weather_data:
                live_data = f"\n\n[LIVE WEATHER DATA]\n{weather_data}\n[END LIVE DATA]\n"
                await tg_output.send(f"🌦️ Live weather fetched: {city_hint}")
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
    
    # Build prompt
    chat_context = ""
    
    try:
        from agent import get_openclaw_memory
        openclaw_mem = get_openclaw_memory()
        if openclaw_mem:
            chat_context += f"[Past PC Task Memory & Learnings]\n{openclaw_mem}\n\n"
    except Exception:
        pass

    if CHAT_HISTORY:
        chat_context += "[Previous Conversation History]\n" + "\n".join(CHAT_HISTORY[-8:]) + "\n\n"
    if live_data:
        prompt = (
            f"You are ClawBot — an AI assistant running DIRECTLY on the user's Windows PC via Telegram. "
            f"You have full PC access and can run any task when asked via /computer command. "
            f"You have LIVE data below. Answer the user's question using it accurately and naturally.\n"
            f"{live_data}"
            f"{chat_context}"
            f"User asked: {text}\n"
            f"Answer in 2-4 lines. Reply in same language as user."
        )
    else:
        prompt = (
            f"You are ClawBot — an AI assistant running DIRECTLY on the user's Windows PC.\n"
            f"You are NOT a cloud-only bot. You are physically running on this PC right now.\n"
            f"You can:\n"
            f"- Chat normally for questions, explanations, writing, coding help\n"
            f"- Actually control the PC (files, apps, code execution, PDF/PPT creation, web browsing, screenshots) when user says /computer <task>\n"
            f"IMPORTANT: When user asks to CREATE files, PDFs, PPTs, code, or do PC tasks — always tell them:\n"
            f"  \"Haan kar sakta hoon! '/computer <task>' likh do aur main seedha PC pe kar dunga.\"\n"
            f"NEVER say you can't access their PC or create files — you absolutely can via /computer mode.\n"
            f"Reply in same language as user.\n\n"
            f"{chat_context}"
            f"User says: {text}"
        )
    
    if text_lower in ("hi", "hello", "hey", "hii", "helo", "helo", "helloo"):
        await tg_output.send("Hello! Main ClawBot hoon 🤖 — aapka AI PC Assistant!\n\n"
                             "• Normal baat karo — seedha type karo\n"
                             "• PC control karna ho — /computer <task> likho\n"
                             "• Screenshot chahiye — /screenshot\n"
                             "• System info — /status")
        return
        
    try:
        raw_msg = await _ask_llm(llm, prompt)
        
        import json
        try:
            parsed = json.loads(raw_msg)
            reply = parsed.get("thought", raw_msg) if hasattr(parsed, 'get') else raw_msg
        except Exception:
            reply = raw_msg
        
        if not reply or not reply.strip():
            reply = "Kuch samajh nahi aaya, please dobara poochho!"
            
        CHAT_HISTORY.append(f"User: {text}")
        CHAT_HISTORY.append(f"ClawBot: {reply}")
        
        # Keep only the last 20 messages to prevent massive prompts
        if len(CHAT_HISTORY) > 20:
            CHAT_HISTORY = CHAT_HISTORY[-20:]
            
        save_chat_history(CHAT_HISTORY)
            
        await tg_output.send(f"💬 {reply}")
    except Exception as e:
        await tg_output.send(f"❌ LLM error: {e}")


async def classify_intent(text: str) -> bool:
    """
    Returns True if the message requires PC automation (computer task),
    False if it's a simple conversational/chat message.
    Uses fast keyword heuristics first, then falls back to LLM for ambiguous cases.
    """
    text_lower = text.lower()
    
    # ── Explicit PC task keywords (almost always need automation) ──
    pc_task_keywords = [
        # File/document creation
        "pdf bana", "ppt bana", "presentation", "excel", "word file", "report bana",
        "document", "file bana", "folder bana", "create file", "make file",
        # App control
        "kholdo", "kholo", "open kar", "band karo", "close kar", "start kar",
        "play kar", "download kar", "install kar",
        # Code tasks
        "code likho", "script bana", "python", "program bana", "automation kar",
        # System
        "screenshot lo", "volume", "brightness", "wifi", "bluetooth",
        "shutdown", "restart", "sleep",
        # Search/Fetch tasks
        "search karo", "dhoondho", "find kar", "google pe", "browser pe",
        "websearch", "web search",
        # Data tasks
        "analyse karo", "analyze", "data nikalo", "chart bana", "graph bana",
    ]
    
    # ── Pure chat keywords (never need PC) ──
    chat_keywords = [
        "kya hai", "kya hota hai", "batao", "bata do", "kaise kaam karta",
        "explain", "samjhao", "meaning", "matlab", "difference",
        "kya sochte", "tumhara naam", "who are you",
        "jokes", "shayari", "poem", "story",
        # CCTV / Camera logic
        "cctv", "camera", "dikh raha", "koi hai", "secure",
    ]
    
    if any(kw in text_lower for kw in pc_task_keywords):
        return True
    
    if any(kw in text_lower for kw in chat_keywords):
        return False
    
    # ── Ambiguous — ask LLM to classify ──
    try:
        from agent import _ask_llm
        llm = create_default_llm()
        classify_prompt = (
            f"You are a classifier. Respond with ONLY the word 'TASK' or 'CHAT'.\n"
            f"'TASK' = message needs PC actions (create file, open app, search web, make document, code, automate something)\n"
            f"'CHAT' = message is conversational (question, greeting, explanation, opinion)\n\n"
            f"Message: \"{text}\"\n"
            f"Answer (TASK or CHAT only):"
        )
        result = await _ask_llm(llm, classify_prompt)
        result_clean = result.strip().upper()
        return 'TASK' in result_clean
    except Exception:
        # Fallback: treat as chat if unsure
        return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages with auto intent detection."""
    global is_task_running, cancel_task
    
    if not _is_authorized(update):
        return
    
    task = update.message.text.strip()
    
    if not task:
        return
    
    # ── Explicit prefix override ──
    lower_task = task.lower()
    explicit_computer = False
    explicit_chat = False
    
    if lower_task.startswith('/computer '):
        task = task[10:].strip()
        explicit_computer = True
    elif lower_task.startswith('/task '):
        task = task[6:].strip()
        explicit_computer = True
    elif lower_task.startswith('/chat '):
        task = task[6:].strip()
        explicit_chat = True
        
    # Auto-intercept natural language CCTV questions
    if any(k in lower_task for k in ["cctv", "abhi camera", "kya dikh raha hai", "koi hai camera"]):
        await cmd_report(update, context)
        return
    
    if is_task_running:
        try:
            from pathlib import Path
            steer_file = Path.home() / '.clawbot' / 'workspace' / 'live_steering.txt'
            steer_file.parent.mkdir(parents=True, exist_ok=True)
            with open(steer_file, "a", encoding="utf-8") as f:
                f.write(task + "\n")
            await update.message.reply_text("📝 **Live Feedback Received!** Agent will consider this in the next step.", parse_mode="Markdown")
        except Exception:
            await update.message.reply_text("⏳ A task is already running! Wait for it to finish.")
        return
    
    is_task_running = True
    cancel_task = False
    
    try:
        bot = context.bot
        chat_id = str(update.effective_chat.id)
        tg_output = TelegramOutput(bot, chat_id)
        
        # Determine mode
        if explicit_computer:
            is_computer_mode = True
        elif explicit_chat:
            is_computer_mode = False
        else:
            # 🧠 Auto-detect intent!
            is_computer_mode = await classify_intent(task)
        
        if is_computer_mode:
            await update.message.reply_text(f"🤖 PC Task samajh aaya!\n⚡ Executing: {task[:80]}")
            os.environ['CLAWBOT_INTERFACE'] = 'Telegram Bot (User is controlling PC remotely via phone)'
            
            task_with_context = task
            if CHAT_HISTORY:
                history_text = "\n".join(CHAT_HISTORY[-6:])
                task_with_context = f"[Recent Chat History for Context]\n{history_text}\n\n[Current Task]\n{task}"
                
            CHAT_HISTORY.append(f"User (PC Task): {task}")
            save_chat_history(CHAT_HISTORY)
            
            await run_ClawBot_task(task_with_context, tg_output)
            
            CHAT_HISTORY.append(f"ClawBot: (Executed PC Task)")
            save_chat_history(CHAT_HISTORY)
        else:
            await run_chat_task(task, tg_output)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Task failed: {str(e)[:200]}")
        logger.error(f"Task error: {e}", exc_info=True)
    finally:
        is_task_running = False
        cancel_task = False


def _is_authorized(update: Update) -> bool:
    """Check if the user is authorized."""
    chat_id = str(update.effective_chat.id)
    auth_chat_id = get_authorized_chat_id()
    
    # If no CHAT_ID set, allow anyone (first-time setup)
    if not auth_chat_id:
        logger.warning(f"⚠️ No TELEGRAM_CHAT_ID set. Message from chat_id={chat_id}")
        return True
    
    if chat_id != auth_chat_id:
        logger.warning(f"🚫 Unauthorized access from chat_id={chat_id}")
        asyncio.ensure_future(
            update.message.reply_text("🚫 Unauthorized. This bot is private.")
        )
        return False
    
    return True


# ════════════════════════════════════════════════════════
# 🚀 MAIN
# ════════════════════════════════════════════════════════

def main():
    """Start the Telegram bot."""
    bot_token = get_bot_token()
    auth_chat_id = get_authorized_chat_id()
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        print("\nSetup:")
        print("  1. Talk to @BotFather on Telegram → /newbot → get TOKEN")
        print("  2. Set: TELEGRAM_BOT_TOKEN=your_token")
        print("     Set: TELEGRAM_CHAT_ID=your_chat_id")
        print("     Set: OLLAMA_BASE_URL=http://your-url:11434")
        print("  3. Save in ~/.clawbot/.env or set as environment variables")
        print("  4. Run: python telegram_bot.py")
        sys.exit(1)
    
    print("🤖 ClawBot Telegram Bot Starting...")
    print(f"   Token: {bot_token[:8]}...{bot_token[-4:]}")
    print(f"   Auth Chat ID: {auth_chat_id or 'ANY (⚠️ set TELEGRAM_CHAT_ID!)'}")
    print(f"   Model: {os.getenv('TELEGRAM_BOT_MODEL', 'qwen3.5:397b-cloud')}")
    print(f"   Ollama: {os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}")
    print()
    
    app = Application.builder().token(bot_token).build()
    
    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("screenshot", cmd_screenshot))
    app.add_handler(CommandHandler("windows", cmd_windows))
    app.add_handler(CommandHandler("processes", cmd_processes))
    app.add_handler(CommandHandler("processes", cmd_processes))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("cctv", cmd_cctv))
    app.add_handler(CommandHandler("monitor_on", cmd_monitor_on))
    app.add_handler(CommandHandler("monitor_off", cmd_monitor_off))
    app.add_handler(CommandHandler("left", cmd_left))
    app.add_handler(CommandHandler("right", cmd_right))
    app.add_handler(CommandHandler("up", cmd_up))
    app.add_handler(CommandHandler("down", cmd_down))
    app.add_handler(CommandHandler("live", cmd_live))
    app.add_handler(CommandHandler("report", cmd_report))
    
    # Callback Query Handler for CCTV Buttons
    app.add_handler(CallbackQueryHandler(handle_cctv_callback, pattern="^cctv_"))
    
    app.add_handler(CommandHandler("task", handle_message))
    app.add_handler(CommandHandler("computer", handle_message))
    app.add_handler(CommandHandler("chat", handle_message))
    
    # Any text message = task
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # ── GAP 7 FIX: Heartbeat System (proactive agent) ──
    async def heartbeat_check(context):
        """Run every 30 minutes to check HEARTBEAT.md for proactive tasks."""
        try:
            heartbeat_file = Path.home() / '.clawbot' / 'workspace' / 'HEARTBEAT.md'
            if not heartbeat_file.exists():
                return
            
            content = heartbeat_file.read_text(encoding='utf-8').strip()
            # Skip if file is empty or only has comments
            active_lines = [l for l in content.splitlines() 
                          if l.strip() and not l.strip().startswith('#')]
            if not active_lines:
                return
            
            # Only send heartbeat to authorized admin
            target_chat_id = get_authorized_chat_id()
            if not target_chat_id:
                return
            
            # Check if a task is already running
            global is_task_running
            if is_task_running:
                return
                
            # Build heartbeat prompt
            from datetime import datetime
            now = datetime.now()
            # Don't heartbeat during sleep hours (23:00 - 08:00)
            if now.hour >= 23 or now.hour < 8:
                return
            
            heartbeat_tasks = '\n'.join(active_lines)
            logger.info(f"💓 Heartbeat triggered with {len(active_lines)} tasks")
            
            try:
                llm = create_default_llm()
                prompt = (
                    f"You are ClawBot performing a HEARTBEAT check. Current time: {now.strftime('%H:%M')}.\n"
                    f"Your human asked you to periodically check on the following:\n{heartbeat_tasks}\n\n"
                    f"Check what you can and report concisely. If nothing needs attention, reply exactly: HEARTBEAT_OK"
                )
                reply = await _ask_llm(llm, prompt)
                
                if reply and 'HEARTBEAT_OK' not in reply:
                    await context.bot.send_message(
                        chat_id=target_chat_id,
                        text=f"💓 **Heartbeat Update**\n\n{reply}",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.warning(f"Heartbeat LLM failed: {e}")
                
        except Exception as e:
            logger.warning(f"Heartbeat check failed: {e}")
    
    # Schedule heartbeat every 30 minutes (starts after 2 min delay)
    if app.job_queue:
        app.job_queue.run_repeating(heartbeat_check, interval=1800, first=120)
        print("💓 Heartbeat system active (every 30 min)")
    
    print("✅ ClawBot is listening on Telegram! Send a message to control your PC.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == '__main__':
    main()

