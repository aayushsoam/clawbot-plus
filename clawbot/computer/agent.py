"""
🤖 ClawBot — Autonomous Computer Control Agent
Full Windows control with security, app discovery, window management, and persistent memory.
"""
import os
import ollama
import re
import time
import base64
import json
import subprocess
import pyautogui
from io import BytesIO
from pathlib import Path
from datetime import datetime
from PIL import ImageGrab
from rich.console import Console
from rich.panel import Panel

console = Console()
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.4

# ── Import ClawBot modules ──
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from actions import (
    reliable_click, reliable_type, smart_wait, ensure_window_focus,
    bring_window_to_front, drag_and_drop, select_all_and_copy
)
from security import is_command_safe, log_action
from system_control import (
    set_volume, mute_toggle, set_brightness, get_brightness,
    wifi_toggle, bluetooth_toggle, get_network_info,
    lock_screen, shutdown, cancel_shutdown, restart, sleep_pc,
    get_system_info, get_running_processes, kill_process, open_app_by_name,
    create_file, read_file, list_directory
)
from window_manager import (
    list_windows, focus_window, minimize_window, maximize_window,
    close_window, resize_window, move_window, snap_window
)

# ── Claw3D Gateway (DISABLED — removed to stop terminal warnings) ──
# To re-enable, uncomment the block below:
# try:
#     from gateway import start_gateway_thread, publish_event as _gw_publish
#     _GW_STARTED = False
#     def _ensure_gateway():
#         global _GW_STARTED
#         if not _GW_STARTED:
#             start_gateway_thread()
#             _GW_STARTED = True
#     _ensure_gateway()
#     def gw_event(event_type: str, data: dict):
#         try: _gw_publish(event_type, data)
#         except Exception: pass
# except Exception as _gw_err:
#     def gw_event(event_type: str, data: dict): pass
def gw_event(event_type: str, data: dict): pass  # no-op stub


# ════════════════════════════════════════════════════════
# 📁 PATHS
# ════════════════════════════════════════════════════════
COMPUTER_DIR = Path(__file__).parent
MEMORY_FILE = COMPUTER_DIR / "memory.json"
APPS_CACHE  = COMPUTER_DIR / "apps_cache.json"

# ════════════════════════════════════════════════════════
# 🧠 PERSISTENT MEMORY
# ════════════════════════════════════════════════════════

WORKSPACE_DIR = Path.home() / ".clawbot"
MEMORY_DIR = WORKSPACE_DIR / "memory"
SESSIONS_DIR = WORKSPACE_DIR / "sessions"
MEMORY_MD = WORKSPACE_DIR / "MEMORY.md"

for d in [WORKSPACE_DIR, MEMORY_DIR, SESSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

if not MEMORY_MD.exists():
    MEMORY_MD.write_text("# 🧠 ClawBot Durable Memory\n\n- User Preferences:\n- Important Facts:\n", encoding='utf-8')

def load_memory() -> dict:
    # We no longer load the flat memory.json file.
    # The active loop memory will just be empty at start.
    return {"tasks": [], "learnings": []}

def save_memory(mem: dict):
    pass # Deprecated in favor of daily logs and session files

def record_task(mem: dict, task: str, steps: list[dict], success: bool):
    """Save the completed task as an OpenClaw-style Markdown session file."""
    try:
        title = re.sub(r'[^a-zA-Z0-9]+', '-', task[:30].strip().lower())
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = SESSIONS_DIR / f"{timestamp}_{title}.md"
        
        status = "✅ SUCCESS" if success else "❌ FAILED"
        content = f"# Task Session: {task}\n**Status:** {status}\n**Date:** {timestamp}\n\n## Action Log\n"
        for s in steps:
            content += f"- Step {s['step']}: {s['summary']}\n"
            
        filepath.write_text(content, encoding='utf-8')
    except Exception as e:
        console.print(f"[red]Session save error: {e}[/red]")


def get_relevant_learnings(mem: dict, task: str) -> str:
    if not mem.get("learnings") and not mem.get("tasks"):
        return ""
    parts = []
    if mem.get("learnings"):
        parts.append("Past successful strategies:")
        for l in mem["learnings"][-10:]:
            parts.append(f"  • {l}")
    task_lower = task.lower()
    keywords = set(task_lower.split())
    similar = []
    for t in reversed(mem.get("tasks", [])[-20:]):
        t_words = set(t["task"].lower().split())
        if keywords & t_words:
            status = "✅" if t["success"] else "❌"
            similar.append(f"  {status} '{t['task']}' → {', '.join(t['steps'][:3])}")
    if similar:
        parts.append("Similar past tasks:")
        parts.extend(similar[:5])
    return "\n".join(parts) if parts else ""


# ════════════════════════════════════════════════════════
# 📱 APP DISCOVERY
# ════════════════════════════════════════════════════════

APP_KNOWLEDGE = {
    "chrome":     {"cat": "Browser",    "open": "start chrome", "tasks": "search web, open URLs, download files, manage tabs", "keys": "Ctrl+T new tab, Ctrl+L address bar, Ctrl+W close tab"},
    "edge":       {"cat": "Browser",    "open": "start msedge", "tasks": "search web, open URLs, download files", "keys": "Ctrl+T new tab, Ctrl+L address bar"},
    "firefox":    {"cat": "Browser",    "open": "start firefox", "tasks": "search web, open URLs, browse privately", "keys": "Ctrl+T new tab, Ctrl+L address bar"},
    "whatsapp":   {"cat": "Chat",       "open": "start whatsapp:", "tasks": "send messages, make voice/video calls, send files/photos", "keys": "Ctrl+N new chat, Ctrl+Shift+M mute"},
    "telegram":   {"cat": "Chat",       "open": "start tg://", "tasks": "send messages, send files, create groups, make calls", "keys": ""},
    "discord":    {"cat": "Chat",       "open": "start discord:", "tasks": "voice chat, text chat, screen share, join servers", "keys": "Ctrl+Shift+M mute, Ctrl+Shift+D deafen"},
    "spotify":    {"cat": "Media",      "open": "start spotify:", "tasks": "play music, create playlists, search songs, podcasts", "keys": "Space pause, Ctrl+Right next track"},
    "vlc":        {"cat": "Media",      "open": "start vlc", "tasks": "play videos, play audio, stream media", "keys": "Space pause, F fullscreen"},
    "notepad":    {"cat": "Editor",     "open": "start notepad", "tasks": "write text, edit files, find/replace text", "keys": "Ctrl+S save, Ctrl+F find"},
    "code":       {"cat": "Dev",        "open": "start code", "tasks": "write code, debug, terminal, extensions, git", "keys": "Ctrl+P open file, Ctrl+Shift+P command palette, Ctrl+` terminal"},
    "word":       {"cat": "Office",     "open": "start winword", "tasks": "write documents, format text, insert tables/images", "keys": "Ctrl+B bold, Ctrl+I italic"},
    "excel":      {"cat": "Office",     "open": "start excel", "tasks": "spreadsheets, formulas, charts, data analysis", "keys": "Ctrl+Shift+L filter, F2 edit cell"},
    "powerpoint": {"cat": "Office",     "open": "start powerpnt", "tasks": "create presentations, add slides, animations", "keys": "F5 slideshow"},
    "outlook":    {"cat": "Office",     "open": "start outlook", "tasks": "email, calendar, contacts, schedule meetings", "keys": "Ctrl+N new email, Ctrl+R reply"},
    "paint":      {"cat": "Creative",   "open": "start ms-paint:", "tasks": "draw, edit images, crop, resize", "keys": ""},
    "photos":     {"cat": "Media",      "open": "start ms-photos:", "tasks": "view photos, edit images, slideshows", "keys": ""},
    "calculator": {"cat": "Utility",    "open": "start calculator:", "tasks": "math calculations, unit conversion", "keys": ""},
    "settings":   {"cat": "System",     "open": "start ms-settings:", "tasks": "WiFi, Bluetooth, display, sound, updates, accounts", "keys": ""},
    "terminal":   {"cat": "System",     "open": "start wt", "tasks": "run commands, PowerShell, CMD, scripts", "keys": "Ctrl+Shift+T new tab"},
    "explorer":   {"cat": "System",     "open": "start explorer", "tasks": "browse files, copy/move/delete files, search files", "keys": "Ctrl+E search, Alt+Up parent folder"},
    "git":        {"cat": "Dev",        "open": "shell", "tasks": "version control, commit, push, pull, branch", "keys": ""},
    "node":       {"cat": "Dev",        "open": "shell", "tasks": "run JavaScript, npm packages, web servers", "keys": ""},
    "python":     {"cat": "Dev",        "open": "shell", "tasks": "run Python scripts, pip install, REPL", "keys": ""},
}


def discover_apps() -> dict:
    if APPS_CACHE.exists():
        try:
            cache = json.loads(APPS_CACHE.read_text(encoding='utf-8'))
            cached_time = datetime.strptime(cache.get("scanned_at", ""), "%Y-%m-%d %H:%M")
            if (datetime.now() - cached_time).total_seconds() < 3600:
                return cache
        except Exception:
            pass

    console.print("[dim]🔍 Scanning installed apps...[/dim]")
    apps_found = {}

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10
        )
        if result.stdout:
            start_apps = json.loads(result.stdout)
            if isinstance(start_apps, dict):
                start_apps = [start_apps]
            for app in start_apps:
                name = app.get("Name", "").strip()
                app_id = app.get("AppID", "").strip()
                if name and len(name) > 1:
                    apps_found[name.lower()] = {"name": name, "app_id": app_id, "source": "start_menu"}
    except Exception:
        pass

    try:
        desktop = Path.home() / "Desktop"
        public_desktop = Path("C:/Users/Public/Desktop")
        for d in [desktop, public_desktop]:
            if d.exists():
                for f in d.glob("*.lnk"):
                    apps_found[f.stem.lower()] = {"name": f.stem, "app_id": str(f), "source": "desktop_shortcut"}
    except Exception:
        pass

    enriched = {}
    for key, info in apps_found.items():
        enriched[key] = info
        for kw, knowledge in APP_KNOWLEDGE.items():
            if kw in key or key in kw:
                enriched[key]["knowledge"] = knowledge
                break

    result_data = {
        "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "app_count": len(enriched),
        "apps": enriched,
    }

    try:
        APPS_CACHE.write_text(json.dumps(result_data, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass

    return result_data


def build_app_context(app_data: dict) -> str:
    lines = []
    categorized: dict[str, list] = {}
    for key, info in app_data.get("apps", {}).items():
        k = info.get("knowledge")
        if k:
            cat = k["cat"]
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(
                f"  {info['name']}: open=`{k['open']}` | tasks: {k['tasks']}"
                + (f" | keys: {k['keys']}" if k.get('keys') else "")
            )
    if not categorized:
        return ""
    lines.append("INSTALLED APPS ON THIS PC:")
    for cat in sorted(categorized.keys()):
        lines.append(f"[{cat}]")
        lines.extend(categorized[cat])
    unknown = [info['name'] for info in app_data.get("apps", {}).values() if 'knowledge' not in info]
    if unknown:
        top = unknown[:20]
        lines.append(f"[Other] {', '.join(top)}" + (f" +{len(unknown)-20} more" if len(unknown) > 20 else ""))
    return "\n".join(lines)


# ════════════════════════════════════════════════════════
# 🚀 SKILLS (From SKILL.md files)
# ════════════════════════════════════════════════════════

def get_skills_context(task: str = "") -> str:
    """Reads SKILL.md files — only loads skills RELEVANT to the current task (GAP 4 fix)."""
    skills_dir = COMPUTER_DIR.parent.parent / "skills"
    if not skills_dir.exists():
        return ""
        
    all_skills = []
    try:
        for skill_folder in os.listdir(skills_dir):
            skill_path = skills_dir / skill_folder / "SKILL.md"
            if skill_path.exists():
                try:
                    content = skill_path.read_text(encoding='utf-8')
                    name_match = re.search(r'^name:\s*(.*?)$', content, re.MULTILINE)
                    desc_match = re.search(r'^description:\s*(?:["\']?)(.*?)(?:["\']?)$', content, re.MULTILINE)
                    if name_match and desc_match:
                        all_skills.append({
                            "name": name_match.group(1).strip(),
                            "desc": desc_match.group(1).strip(),
                            "folder": skill_folder
                        })
                except Exception:
                    pass
    except Exception as e:
        console.print(f"[dim]Failed to read skills: {e}[/dim]")
        
    if not all_skills:
        return ""
    
    # --- SMART SKILL MATCHING: Only inject relevant skills (saves ~5000 tokens) ---
    task_lower = task.lower() if task else ""
    relevant = []
    other_names = []
    
    for sk in all_skills:
        sk_text = f"{sk['name']} {sk['desc']} {sk['folder']}".lower()
        # Check if any word from the task appears in the skill
        if task_lower and any(word in sk_text for word in task_lower.split() if len(word) > 3):
            relevant.append(sk)
        else:
            other_names.append(sk['name'])
    
    lines = ["AVAILABLE SKILLS (matched to your task):"]
    if relevant:
        for sk in relevant[:8]:  # Max 8 relevant skills
            lines.append(f"  • **{sk['name']}**: {sk['desc']}")
    
    # Show remaining as compact list (just names, no descriptions)
    if other_names:
        lines.append(f"  (Other available: {', '.join(other_names[:20])})")
        if len(other_names) > 20:
            lines.append(f"  (+{len(other_names)-20} more skills available)")
    
    return "\n".join(lines)


# ════════════════════════════════════════════════════════
# 📸 SCREENSHOTS
# ════════════════════════════════════════════════════════

def take_full_screenshot_b64() -> str:
    try:
        screenshot = ImageGrab.grab()
        screenshot.thumbnail((1280, 1024))
        buf = BytesIO()
        screenshot.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        console.print(f"[red]Screenshot error: {e}[/red]")
        return ""


def take_active_window_screenshot_b64() -> tuple[str, tuple[int, int]]:
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        sw, sh = pyautogui.size()
        left, top = max(0, left), max(0, top)
        right, bottom = min(sw, right), min(sh, bottom)
        if right - left < 100 or bottom - top < 100:
            return take_full_screenshot_b64(), (0, 0)
        screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
        buf = BytesIO()
        screenshot.save(buf, format="JPEG", quality=75)
        return base64.b64encode(buf.getvalue()).decode('utf-8'), (left, top)
    except Exception:
        return take_full_screenshot_b64(), (0, 0)


# ════════════════════════════════════════════════════════
# 🧠 OPENCLAW MEMORY INTEGRATION
# ════════════════════════════════════════════════════════

def get_openclaw_memory() -> str:
    """Read ClawBot's persona, user facts, and long-term memory."""
    local_ws = COMPUTER_DIR.parent.parent / "workspace"
    workspace = local_ws if local_ws.exists() else Path.home() / ".clawbot" / "workspace"
    
    # Auto-migrate OpenClaw identity if exists
    openclaw_ws = Path.home() / ".openclaw" / "workspace"
    if not workspace.exists() and openclaw_ws.exists():
        import shutil
        workspace.mkdir(parents=True, exist_ok=True)
        for f in ["IDENTITY.md", "SOUL.md", "USER.md", "HEARTBEAT.md", "AGENTS.md", "BOOTSTRAP.md"]:
            src = openclaw_ws / f
            if src.exists():
                try: shutil.copy2(src, workspace / f)
                except Exception: pass
                
    # If still completely missing (e.g., fresh PIP install on a new PC), auto-generate defaults!
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "IDENTITY.md").write_text("# 🤖 CLAWBOT IDENTITY\n\nYou are ClawBot, an elite Computer Control Agent and Senior Developer AI.", encoding='utf-8')
        (workspace / "AGENTS.md").write_text("# 👨‍💻 Senior Developer Coding Workflow (MANDATORY)\n\n1. **PLAN:** Research and formulate steps.\n2. **EXECUTE:** Write the code.\n3. **VERIFY:** Build/run/test the code.\n4. **SHOW OUTPUT:** Report back to user.", encoding='utf-8')
        (workspace / "SOUL.md").write_text("# 🧠 CORE SOUL\n\nYou never loop blindly. You act independently.", encoding='utf-8')
        (workspace / "USER.md").write_text("# 👤 USER FACTS\n\nName: User", encoding='utf-8')
    
    parts = []
    
    # Core Persona & Rules
    for file in ["IDENTITY.md", "SOUL.md", "USER.md", "AGENTS.md", "BOOTSTRAP.md"]:
        path = workspace / file
        if path.exists():
            try:
                parts.append(f"--- {str(path)} ---\n{path.read_text(encoding='utf-8').strip()}")
            except Exception:
                pass
                
    # Long-term Memory & Heartbeat
    for file in ["MEMORY.md", "HEARTBEAT.md"]:
        path = workspace / file
        if path.exists():
            try:
                parts.append(f"--- {str(path)} ---\n{path.read_text(encoding='utf-8').strip()}")
            except Exception:
                pass
                
    # Durable Long-Term Memory (MEMORY.md)
    if MEMORY_MD.exists():
        try:
            parts.append(f"--- LONG-TERM PREFERENCES ({str(MEMORY_MD)}) ---\n{MEMORY_MD.read_text(encoding='utf-8').strip()}")
        except Exception:
            pass

    # Daily Raw Logs (Today & Yesterday)
    from datetime import datetime, timedelta
    if MEMORY_DIR.exists():
        today = datetime.now().strftime("%Y-%m-%d.md")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d.md")
        for file in [yesterday, today]:
            path = MEMORY_DIR / file
            if path.exists():
                try:
                    parts.append(f"--- RECENT LOG ({file}) ---\n{path.read_text(encoding='utf-8').strip()}")
                except Exception:
                    pass

    if not parts:
        return ""
        
    return "CLAWBOT PERSONA & MEMORY ARCHITECTURE:\n" + "\n\n".join(parts)


def append_daily_memory(role: str, text: str):
    """Write interaction directly to today's Clawbot memory file."""
    try:
        from datetime import datetime
        today_file = MEMORY_DIR / datetime.now().strftime("%Y-%m-%d.md")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"\n### [{timestamp}] {role.upper()}\n{text}\n"
        
        with open(today_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        console.print(f"[dim text-red]Failed to write ClawBot memory: {e}[/dim]")


# ════════════════════════════════════════════════════════
# 🛠️ HELPERS
# ════════════════════════════════════════════════════════

# Long-running command patterns that need extended timeouts (GAP 6 fix)
_LONG_CMD_PATTERNS = [
    'npm install', 'npm i ', 'npm ci', 'npm run build', 'npm run dev',
    'pip install', 'pip3 install', 'npx create', 'npx -y',
    'git clone', 'git pull', 'git push', 'git fetch',
    'yarn install', 'yarn add', 'pnpm install',
    'playwright install', 'cargo build', 'go build',
    'docker build', 'docker pull', 'dotnet build',
]
_MEDIUM_CMD_PATTERNS = [
    'npm run', 'npm test', 'pytest', 'python -m', 'node ',
    'tsc ', 'webpack', 'vite build', 'next build',
]

def _get_shell_timeout(cmd: str) -> int:
    """Dynamic timeout: 120s for installs, 60s for builds, 30s for others."""
    cmd_lower = cmd.lower()
    if any(p in cmd_lower for p in _LONG_CMD_PATTERNS):
        return 120
    if any(p in cmd_lower for p in _MEDIUM_CMD_PATTERNS):
        return 60
    return 30


def run_shell(cmd: str) -> str:
    """Run shell command with security check and dynamic timeout."""
    is_safe, reason = is_command_safe(cmd)
    if not is_safe:
        log_action("shell_blocked", f"{cmd} → {reason}", blocked=True)
        console.print(f"[bold red]{reason}[/bold red]")
        return reason

    timeout = _get_shell_timeout(cmd)
    log_action("shell", cmd)
    try:
        import os
        env = os.environ.copy()
        npm_path = str(Path.home() / "AppData" / "Roaming" / "npm")
        if npm_path not in env.get("PATH", ""):
            env["PATH"] = f"{npm_path};{env.get('PATH', '')}"
            
        clawbot_root = str(COMPUTER_DIR.parent)
        env["PYTHONPATH"] = f"{clawbot_root};{env.get('PYTHONPATH', '')}"
        
        if timeout > 30:
            console.print(f"[dim]   ⏱️ Extended timeout: {timeout}s[/dim]")
            
        result = subprocess.run(
            cmd, shell=True,
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=timeout, env=env
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0 and err:
            return f"ERROR: {err[:500]}"
        return out if out else "(done)"
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s. Try breaking into smaller steps."
    except Exception as e:
        return f"ERROR: {e}"


IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff'}


def load_image_b64(path: str) -> str | None:
    try:
        from PIL import Image
        img = Image.open(path)
        img.thumbnail((1280, 1024))
        buf = BytesIO()
        img.convert('RGB').save(buf, format='JPEG', quality=85)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception:
        return None


def extract_file_paths(text: str) -> list[str]:
    patterns = [
        r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]+',
        r'/(?:[^/\0]+/)*[^/\0]+',
    ]
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text):
            p = m.group(0).strip('"\'')
            ext = os.path.splitext(p)[1].lower()
            if ext in IMAGE_EXTS and os.path.isfile(p):
                found.append(p)
    return list(dict.fromkeys(found))


async def _ask_llm(llm, prompt: str, b64_img: str | None = None, extra_images: list[str] | None = None):
    from browser_use.llm.messages import UserMessage
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    
    _c = Console()
    content: list = [{"type": "text", "text": prompt}]
    if b64_img:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}})
    if extra_images:
        for img_path in extra_images:
            b64 = load_image_b64(img_path)
            if b64:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    messages = [UserMessage(content=content)]
    
    full_text = ""
    thinking_text = ""
    in_thinking = False
    finished_thinking = False
    usage_info = ""

    try:
        with Live(console=_c, refresh_per_second=15, transient=False) as live:
            async for chunk in llm.astream(messages):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if not isinstance(token, str):
                    token = str(token)
                full_text += token
                
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    u = chunk.usage_metadata
                    usage_info = f"[dim cyan]🪙 Tokens: {u.get('input_tokens',0)} in | {u.get('output_tokens',0)} out[/dim cyan]"
                
                # Check for thinking blocks
                if not finished_thinking:
                    if "<thinking>" in full_text and "</thinking>" not in full_text:
                        in_thinking = True
                        parts = full_text.split("<thinking>")
                        if len(parts) > 1:
                            thinking_text = parts[1].strip()
                            disp = thinking_text
                            if len(disp) > 500:
                                disp = "..." + disp[-500:]
                            live.update(Panel(disp, title="💭 Thinking...", style="dim italic", border_style="dim"))
                    elif "</thinking>" in full_text and in_thinking:
                        in_thinking = False
                        finished_thinking = True
                        live.update(Panel("Completed in background.", title="💭 Thinking (Completed)", border_style="dim", style="dim"))
                        
                        # Save full thought to log file
                        try:
                            t_log = Path.home() / '.clawbot' / 'thought.log'
                            t_log.parent.mkdir(exist_ok=True)
                            parts = full_text.split("<thinking>")[1].split("</thinking>")
                            t_log.open('a', encoding='utf-8').write("\n--- THOUGHT ---\n" + parts[0] + "\n")
                        except Exception:
                            pass
                            
    except Exception as e:
        error_msg = str(e).lower()
        if ("multimodal" in error_msg or "vision" in error_msg or ("400" in error_msg and ("image" in error_msg or "multimodal" in error_msg))) and (b64_img or extra_images):
            # Model rejects image payload! Retry as text-only.
            _c.print("[bold yellow]⚠️ Model rejected image. Retrying as plain text-only...[/bold yellow]")
            messages[0].content = prompt  # Plain string, not array, for strict text-only models
            try:
                with _c.status("[dim]ClawBot thinking (sync, text-only)...[/dim]", spinner="dots"):
                    response = await llm.ainvoke(messages)
                    full_text = getattr(response, 'content', getattr(response, 'completion', str(response)))
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        u = response.usage_metadata
                        usage_info = f"[dim cyan]🪙 Tokens: {u.get('input_tokens',0)} in | {u.get('output_tokens',0)} out[/dim cyan]"
            except Exception as retry_e:
                # If retry STILL fails, we must catch it so it prints an error in chat rather than exploding the app!
                raise Exception(f"Vision error: {error_msg} | Fallback Error: {str(retry_e)}")
        else:
            # Fallback to sync ainvoke if streaming is not supported by this provider
            with _c.status("[dim]ClawBot thinking (sync)...[/dim]", spinner="dots"):
                response = await llm.ainvoke(messages)
                full_text = getattr(response, 'content', getattr(response, 'completion', str(response)))
                
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    u = response.usage_metadata
                    usage_info = f"[dim cyan]🪙 Tokens: {u.get('input_tokens',0)} in | {u.get('output_tokens',0)} out[/dim cyan]"

    if usage_info:
        _c.print(f"  {usage_info}")

    return full_text.strip()


def _parse_json(raw: str) -> dict:
    """Ultra-robust JSON parser with 5 fallback levels (GAP 2 fix)."""
    import re as _re
    
    # Step 1: Extract JSON from markdown code blocks
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    
    # Step 2: Find the outermost JSON object
    s, e = raw.find('{'), raw.rfind('}')
    if s != -1 and e != -1:
        raw = raw[s:e+1]
    
    # Attempt 1: Direct parse
    try:
        return json.loads(raw, strict=False)
    except Exception:
        pass
    
    # Attempt 2: Fix Windows backslash escaping (C:\Users → C:\\Users)
    try:
        fixed = _re.sub(r'\\(?=[^"\\/bfnrtu])', r'\\\\', raw)
        return json.loads(fixed, strict=False)
    except Exception:
        pass
    
    # Attempt 3: Remove trailing commas before } or ]
    try:
        fixed = _re.sub(r',\s*([}\]])', r'\1', raw)
        return json.loads(fixed, strict=False)
    except Exception:
        pass
    
    # Attempt 4: Fix single quotes → double quotes (some LLMs do this)
    try:
        fixed = raw.replace("'", '"')
        fixed = _re.sub(r',\s*([}\]])', r'\1', fixed)
        return json.loads(fixed, strict=False)
    except Exception:
        pass
    
    # Attempt 5: Extract action and thought with regex (last resort)
    try:
        action_match = _re.search(r'"action"\s*:\s*"([^"]+)"', raw)
        thought_match = _re.search(r'"thought"\s*:\s*"([^"]*?)"', raw)
        if action_match:
            result = {"action": action_match.group(1), "thought": ""}
            if thought_match:
                result["thought"] = thought_match.group(1)
            # Extract other common fields
            for field in ['command', 'text', 'path', 'content', 'x', 'y', 'key', 'keys',
                          'level', 'result', 'query', 'url', 'window_title', 'name',
                          'direction', 'amount', 'language', 'code', 'pattern', 'old_text', 'new_text']:
                m = _re.search(rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
                if m:
                    result[field] = m.group(1)
                else:
                    # Try numeric values
                    m = _re.search(rf'"{field}"\s*:\s*(\d+)', raw)
                    if m:
                        result[field] = int(m.group(1))
            console.print(f"[yellow]⚠️ JSON was malformed. Recovered via regex: action={result['action']}[/yellow]")
            return result
    except Exception:
        pass
    
    # All attempts failed
    raise json.JSONDecodeError(f"All 5 JSON parse attempts failed", raw[:200], 0)


# ════════════════════════════════════════════════════════
# 🚀 ClawBot MAIN LOOP
# ════════════════════════════════════════════════════════

def get_system_context() -> str:
    import getpass, socket, platform
    user = getpass.getuser()
    pc = socket.gethostname()
    cwd = os.getcwd()
    home = str(Path.home())
    paths = {}
    for folder in ['Downloads', 'Documents', 'Desktop']:
        res = subprocess.run(["powershell", "[Environment]::GetFolderPath('"+folder+"')"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        paths[folder] = res.stdout.strip() or f"{home}\\{folder}"
    return (
        f"--- SYSTEM CONTEXT ---\n"
        f"PC: {pc} | User: {user}\n"
        f"CWD: {cwd} | Home: {home}\n"
        f"Downloads: {paths['Downloads']}\n"
        f"Documents: {paths['Documents']}\n"
        f"Desktop: {paths['Desktop']}\n"
        f"OS: {platform.system()} {platform.release()}\n"
        f"----------------------"
    )


async def run_computer_task(llm, task: str):
    """ClawBot — Full Computer Control Agent."""

    # ── Phase 1: Context & Discovery ──
    sys_context = get_system_context()
    mem = load_memory()
    app_data = discover_apps()
    app_context = build_app_context(app_data)
    skills_context = get_skills_context(task)  # GAP 4: pass task for smart matching
    learnings = get_relevant_learnings(mem, task)
    openclaw_memory = get_openclaw_memory()
    
    # Save user task immediately to OpenClaw memory
    append_daily_memory("USER", task)

    try:
        session_count = len(list(SESSIONS_DIR.glob("*.md")))
    except Exception:
        session_count = 0

    console.print(Panel(
        f"[bold cyan]🤖 ClawBot — Computer Control[/bold cyan]\n"
        f"[dim]Task:[/dim] {task}\n"
        f"[dim]Apps:[/dim] {app_data.get('app_count', 0)} discovered  |  "
        f"[dim]Memory:[/dim] {session_count} past sessions  |  "
        f"[dim]Persona:[/dim] {'[green]Loaded[/green]' if openclaw_memory else '[dim]None[/dim]'}",
        border_style="cyan", padding=(0, 2)
    ))

    width, height = pyautogui.size()
    memory: list[dict] = []
    needs_screenshot = False
    extra_images = extract_file_paths(task)
    if extra_images:
        console.print(f"[dim]📁 {len(extra_images)} image(s) attached from task[/dim]")
    task_success = False

    video_engine = os.environ.get('CLAWBOT_VIDEO_ENGINE', 'cloud')
    video_engine_rule = ""
    if video_engine == 'local':
        video_engine_rule = "- **VIDEO GENERATION:** The user has strictly chosen LOCAL PYTHON. Do NOT use fal.ai or prompt the user for paid cloud services. ALWAYS write and execute local python scripts (like using `make_pro_video.py` or `moviepy`) to generate .mp4 videos."
    elif video_engine == 'cloud':
        video_engine_rule = "- **VIDEO GENERATION:** The user has chosen CLOUD APIs. You are allowed to use fal.ai or Koda-Stack paid web APIs for rendering video."

    deep_os_rule = "- **DEEP OS ACTIVE:** You MUST prioritize `win_ui_click` over coordinate-based `click` for GUI elements. Guess the `name` (e.g. 'Save') and `control_type` (e.g. 'ButtonControl', 'EditControl', 'MenuItemControl') to interact natively with Windows."

    # ── Detect OS & Environment ──
    import platform, getpass, socket
    os_name = platform.system()  # Windows / Linux / Darwin
    os_version = platform.version()
    os_arch = platform.machine()
    hostname = socket.gethostname()
    username = getpass.getuser()
    shell_name = "PowerShell" if os_name == "Windows" else "bash"
    interface_source = os.environ.get("CLAWBOT_INTERFACE", "CLI Terminal")

    # ── ClawBot System Prompt ──
    SYSTEM = f"""You are ClawBot — an intelligent AI assistant with FULL CONTROL of this {os_name} {width}x{height} PC.
You are precise, efficient, and never repeat failing actions.

ENVIRONMENT INFO:
- OS: {os_name} {os_version} ({os_arch})
- Hostname: {hostname}
- User: {username}
- Shell: {shell_name}
- Interface: {interface_source} (This is where the user is talking to you from)
- Screen: {width}x{height}
IMPORTANT: All shell commands MUST be {shell_name}-compatible. On Windows, use PowerShell syntax (e.g., `New-Item`, `Get-ChildItem`). NEVER use Linux commands like `ls`, `cat`, `rm` on Windows.

CRITICAL RULE: Your memory, persona, and user preference files MUST ONLY be written to `{str((COMPUTER_DIR.parent.parent / 'workspace')).replace(chr(92), chr(92)+chr(92))}` if you are actively working inside the source code, otherwise to `C:\\\\Users\\\\thaku\\\\.clawbot\\\\workspace`. NEVER write to `.claw` or `.openclaw` directories.
CRITICAL JSON ESCAPE RULE: Any Windows paths in your JSON MUST use double backslashes! E.g., `"path": "C:\\\\Users\\\\Desktop"`. This is vital because single backslashes will crush the JSON parser!

{f"{chr(10)}{openclaw_memory}{chr(10)}" if openclaw_memory else ""}

{sys_context}

You know every app installed and how humans use them.

{app_context}

CRITICAL REASONING INSTRUCTION (Claude Opus 4.6 Standard):
BEFORE outputting any JSON command, you MUST formulate a full Chain of Thought inside `<thinking>...</thinking>` tags. 
Your thinking MUST include:
1. **Goal Analysis:** What exactly did the user ask? Break it down.
2. **Environment Check:** What files/apps are already active or known?
3. **Strategy:** Choose the best system tool or CLI approach (prefer over GUI clicks).
4. **Pitfall ID:** What could go wrong? Avoid infinite loops or overwriting blindly.
6. **Security/CCTV:** Use `python skills/cctv_expert/monitor.py watch Home` to show live feed, or `ai_monitor Home` for background alerts.
Only AFTER closing the </thinking> tag, you may output your final precise JSON action.

{f"{chr(10)}{skills_context}" if skills_context else ""}

{f"MEMORY (learn from past):{chr(10)}{learnings}" if learnings else ""}

STRATEGY (follow in order of preference):
1. Direct system commands FIRST — shell, system_control actions (instant, most reliable)
2. Keyboard shortcuts next — hotkeys, Ctrl+shortcuts (fast, reliable)
3. Focus the target app BEFORE any GUI interaction
4. GUI clicks ONLY as last resort (after 1-3 fail)
5. CODING TASKS — You are a SENIOR SOFTWARE ENGINEER. Code like one. You MUST follow this 4-step workflow:
   - [STEP 1: PLAN] ARCHITECTURE FIRST: Before writing ANY code, plan the full file tree. A web project MUST have separate files: index.html, styles.css (or style.css), app.js (or script.js). NEVER inline CSS or JS into HTML.
   - [STEP 2: EXECUTE] WRITE COMPLETE FILES: Every file must be production-quality. CSS must include modern layout, variables, responsive design, and premium glassmorphism/dark mode aesthetics. JS must be complete. NO HTML PLACEHOLDERS. The `write_file` action automatically creates missing parent directories.
   - [STEP 3: VERIFY] DO NOT CALL DONE YET: After writing files, you MUST verify syntax. If writing Python, run `python file.py`. If JS, run `node file.js`. If HTML, check structure. If any errors occur, SELF-HEAL and fix the code immediately.
   - [STEP 4: SHOW OUTPUT] PROVE IT WORKS: Once verified, you must show the output. If it's a website/UI, take a screenshot of the running app or code preview. If it's a backend script, show the terminal output. CRITICAL: Once you capture the screenshot or show the output, YOU MUST CALL `done` IN THE VERY NEXT STEP. Do not critique the screenshot. Do not rewrite code to make it prettier. Screenshot = Task Finished!
6. AUTO-SWARMING: If the user assigns a complex project (e.g. 'Build a React + Node website', 'Setup full architecture', 'Analyze data and build dashboard'), you MUST use the SWARM MULTI-AGENT capabilities to spawn specialist workers for each domain. DO NOT do everything sequentially yourself.

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

--- DEEP OS HOOKS (Windows Native UIAutomation) ---
UI Click:         {{"thought":"...", "action":"win_ui_click",     "name":"Save", "control_type":"ButtonControl"}}

--- CODING TOOLS (OpenCode/Claude Code style — use for ALL code tasks) ---
Read file:        {{"thought":"...", "action":"read_file",         "path":"src/App.tsx", "start_line":1, "end_line":50}}
Write file:       {{"thought":"...", "action":"write_file",        "path":"src/Component.tsx", "content":"import React..."}}
Edit file (diff): {{"thought":"...", "action":"edit_file",         "path":"src/App.tsx", "old_text":"old code", "new_text":"new code"}}
Grep search:      {{"thought":"...", "action":"grep_search",       "pattern":"useState", "include":"*.tsx"}}
Glob files:       {{"thought":"...", "action":"glob_files",        "pattern":"src/**/*.ts"}}
Todo write:       {{"thought":"...", "action":"todo_write",        "todos":[{{"id":1, "task":"Create component", "status":"in_progress"}}, {{"id":2, "task":"Add tests", "status":"pending"}}]}}
Todo read:        {{"thought":"...", "action":"todo_read"}}

--- WEB SEARCH (instant info without browser) ---
Web search:       {{"thought":"...", "action":"web_search",       "query":"latest news about AI"}}
Web fetch:        {{"thought":"...", "action":"web_fetch",        "url":"https://example.com"}}

--- FLOW CONTROL ---
Done:             {{"thought":"...", "action":"done",             "result":"what was accomplished"}}
Screenshot:       {{"thought":"...", "action":"take_screenshot"}}

--- CODE EXECUTION (self-healing — ONLY for Python scripts, NOT for TS/JS/Go/Rust) ---
Run code:         {{"thought":"...", "action":"run_code",          "language":"python", "code":"print('hello')", "task_context":"what this code should do"}}

--- KNOWLEDGE & MEMORY RETRIEVAL ---
Local file search:    {{"thought":"...", "action":"local_search",      "query":"electricity bill amount"}}

--- OPENCLAW HYBRID MEMORY SEARCH (search your past logs, sessions, and preferences) ---
Memory search:    {{"thought":"...", "action":"memory_search",     "query":"user preferred programming topics"}}

--- WORKFLOW MACROS (record and replay action sequences) ---
List workflows:   {{"thought":"...", "action":"list_workflows"}}
Replay workflow:  {{"thought":"...", "action":"replay_workflow",   "name":"daily_backup"}}

--- SWARM MULTI-AGENT (ClawTeam - One Command to Full Automation) ---
Spawn Worker:     {{"thought":"...", "action":"shell", "command":"python -m clawteam spawn subprocess clawbot --team frontend-squad --agent-name dev1 --task 'Build App.js'"}}
List Tasks:       {{"thought":"...", "action":"shell", "command":"python -m clawteam task list frontend-squad"}}
Message Worker:   {{"thought":"...", "action":"shell", "command":"python -m clawteam inbox send frontend-squad dev1 'API is ready'"}}
Check Inbox:      {{"thought":"...", "action":"shell", "command":"python -m clawteam inbox receive frontend-squad"}}

--- VOICE (speak aloud to user) ---
Speak:            {{"thought":"...", "action":"speak",             "text":"Hello", "voice":"hi-IN-MadhurNeural"}}
(NOTE: Use 'speak' ONLY if the user explicitly asks you to speak. Using 'speak' does NOT end the task. If you are finished, you MUST use 'done'!)

--- ADVANCED CAPABILITIES ---
Generate PPT:     {{"thought":"...", "action":"generate_ppt", "slides":[{{"title":"Slide 1", "points":["Point 1", "Point 2"]}}], "theme":"dark"}}

CRITICAL RULES:
- SECURITY: All shell commands are checked. Dangerous commands (format, del /s, system32) are BLOCKED.
- If the user asks to build a project, app, or website: ALWAYS create a dedicated folder for it first (e.g., `mkdir project_name`), and place all code files inside that folder!
- **CODING WORKFLOW (Senior Engineer Standard):**
  - For ANY code task: ALWAYS use `write_file` to create files. NEVER use `run_code` for non-Python languages.
  - A website project MUST ALWAYS produce AT MINIMUM these separate files: `index.html`, `styles.css`, `app.js`. Never put CSS inside HTML `<style>` tags or JS inside `<script>` tags when building a project.
  - CSS files must be COMPLETE: include CSS custom properties (variables), responsive breakpoints (@media), hover/active states, transitions/animations, proper spacing, a professional color scheme, and Google Fonts import.
  - JS files must be COMPLETE: include DOM selectors, event listeners, fetch API calls to backend, error handling, loading spinners, and form validation.
  - Backend files must include: proper middleware setup, CORS, error handling middleware, input validation, and organized route structure.
  - Before modifying existing code, ALWAYS use `read_file` first.
  - For small changes, prefer `edit_file` (targeted diff) over full rewrite.
  - Use `grep_search` and `glob_files` to explore codebases.
  - For simple sequential work, use `todo_write`. For complex multi-domain projects, use SWARM Multi-Agent.
  - After writing ALL files, VERIFY via `shell` (e.g., `node server.js`, `npm run build`, `python script.py`). DO NOT call `done` until every referenced file exists.
  - **SINGLE FILE / MARKDOWN BYPASS:** If the user asks for a simple text file, a plan, or a markdown file (like `SKILLS_MAP.md`), YOU DO NOT NEED TO VERIFY IT IN A SHELL OR TAKE A SCREENSHOT. Write the file and IMMEDIATELY call `done` to prevent looping!
- **BINARY FILES:** NEVER use `create_file` or `write_file` to generate `.pptx`, `.xlsx`, `.docx`, or `.pdf` files. Your text output will corrupt them. For PowerPoint, you MUST use the `generate_ppt` action. For other binary formats, use the `run_code` action to execute a Python script utilizing `pandas` or `python-docx` to generate these files.
- **TASK COMPLETION (ANTI-LOOP):** Do NOT write the same file more than once. If you see 'Wrote: X' in history, that file is DONE — move to the NEXT step. Similarly, NEVER use `read_file` on the exact same file repeatedly. If you have read it once, you have the information. If you are stuck reading the same files over and over, you MUST break the loop immediately by calling `done`. Only call `done` when ALL planned work is finished or if you are caught in a repetitive action loop.
- **TODO DISCIPLINE:** If you created a todo_write plan, you MUST complete EVERY item before calling `done`. Do not abandon your plan.
- After clicking a text field, IMMEDIATELY type in the next step. Never click the same field twice.
- NEVER repeat the exact same action more than 2 times. If it fails or returns the same result, YOU MUST STOP and either change approach or use `done`.
- **CONVERSATION / SMALL TALK:** If the user just says "hi", "hello", "how are you" or makes simple conversation without asking for a concrete task: ALWAYS respond using the `done` action with a friendly greeting in the `result` field. Do NOT use the `speak` action for this, and do NOT loop. The task is instantly `done`.
- Before any GUI click/type, use "focus_app" to bring the target app to front.
- WhatsApp: Click search bar ONCE → type contact name → click result → type message → press Enter.
- For information/search tasks, use "web_search" FIRST before opening a browser. It is faster and more reliable.
- Output ONLY valid JSON. No markdown, no extra text.
{video_engine_rule}
{deep_os_rule}"""

    win_offset = (0, 0)
    log_action("task_start", task)
    
    # Send lifecycle START to make agent appear and walk to desk
    gw_event("agent", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "stream": "lifecycle", "data": {"phase": "start"}})
    # Send the user's task to the 3D chat
    gw_event("chat", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "state": "final", "message": {"role": "user", "content": task}})

    from pathlib import Path
    steer_file = Path.home() / '.clawbot' / 'workspace' / 'live_steering.txt'

    for step in range(1, 41):  # 40 steps max
        # ── Handle Live Steering (Mid-task user feedback) ──
        live_feedback = ""
        if steer_file.exists():
            live_feedback = steer_file.read_text(encoding="utf-8").strip()
            if live_feedback:
                console.print(f"\n[bold magenta]🚨 User Live Feedback Received:[/bold magenta] {live_feedback}")
                memory.append({"step": step, "summary": f"USER FEEDBACK: {live_feedback}"})
            try:
                steer_file.unlink() # Delete after reading to prevent repeating
            except Exception:
                pass

        mem_text = ""
        if memory:
            mem_text = "\nSession history:\n" + "\n".join(
                f"  {m['step']}. {m['summary']}" for m in memory[-8:]
            )

        prompt = f"{SYSTEM}{mem_text}\n\nTask: {task}\n"
        if live_feedback:
            prompt += f"\n\n🚨 CRITICAL LIVE FEEDBACK FROM USER:\n\"{live_feedback}\"\nYou MUST incorporate this new information into your current approach immediately!\n"

        # ── Loop Detection ──
        if len(memory) >= 3:
            last_3 = [m['summary'] for m in memory[-3:]]
            if len(set(last_3)) == 1 or all('screen(' in s for s in last_3):
                prompt += "\n⚠️ CRITICAL: You repeated the SAME ACTION 3x! It is NOT WORKING. You MUST use a COMPLETELY DIFFERENT approach NOW.\n"
                prompt += "Try: keyboard shortcut, shell command, or focus_app first.\n"
                console.print(f"[bold red]🔄 Loop detected! Forcing different approach...[/bold red]")
            elif len(memory) >= 2 and memory[-1]['summary'] == memory[-2]['summary']:
                prompt += "\n⚠️ You repeated the same action twice. Switch strategy if it fails again.\n"

        # ── Completion Detection (anti-loop) ──
        completion_signals = [
            'Self-Healing: Success', 'Created:', 'opened', 'Task Complete', 
            'installed', 'Code (python) SUCCESS', 'Code (js) SUCCESS', 
            'PPT Created', 'Requested screenshot'
        ]
        if len(memory) >= 1:
            recent_summaries = ' '.join(m['summary'] for m in memory[-6:])
            if any(sig.lower() in recent_summaries.lower() for sig in completion_signals):
                prompt += "\n✅ CRITICAL (ANTI-LOOP): Your session history shows the task verification or screenshot/output was already captured! The 4-step workflow is complete. YOU MUST CALL `done` IN THIS EXACT STEP. Do not critique the work, do NOT rewrite code, do NOT loop. Call `done` now!\n"

        if needs_screenshot:
            prompt += "Screenshot attached. Analyze and decide next action."
        else:
            prompt += "No screenshot. Use system commands/keyboard first. Request screenshot only if needed."

        b64 = None
        if needs_screenshot:
            if step == 1 or len(memory) == 0:
                b64 = take_full_screenshot_b64()
                win_offset = (0, 0)
                console.print(f"\n[bold cyan]📍 Step {step}:[/bold cyan] [dim](full scan)[/dim]", end=" ")
            else:
                time.sleep(0.6)
                b64, win_offset = take_active_window_screenshot_b64()
                ox, oy = win_offset
                console.print(f"\n[bold cyan]📍 Step {step}:[/bold cyan] [dim](window @ {ox},{oy})[/dim]", end=" ")
            needs_screenshot = False
        else:
            console.print(f"\n[bold cyan]📍 Step {step}:[/bold cyan] [dim](thinking)[/dim]", end=" ")

        try:
            # Show "Thinking..." bubble in 3D
            gw_event("chat", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "state": "delta", "message": {"role": "assistant", "content": "Thinking..."}})
            
            raw = await _ask_llm(llm, prompt, b64_img=b64, extra_images=extra_images)

            action = _parse_json(raw)
            act = action.get('action')
            thought = action.get('thought', '')

            if thought:
                console.print(f"\n[magenta]🧠 {thought}[/magenta]")
            
            # Show action string in 3D chat
            action_text = thought if thought else f"Executing {act}..."
            gw_event("chat", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "state": "delta", "message": {"role": "assistant", "content": f"🛠 {action_text}"}})

            # ══════════════════════════════════════════
            # EXECUTE ACTION
            # ══════════════════════════════════════════

            # --- System Control Actions ---
            if act == 'set_volume':
                level = int(action.get('level', 50))
                console.print(f"[green]🔊 Volume → {level}%[/green]")
                set_volume(level)
                memory.append({"step": step, "summary": f"Volume: {level}%"})
                log_action("set_volume", str(level))

            elif act == 'mute_toggle':
                console.print("[green]🔇 Mute toggle[/green]")
                mute_toggle()
                memory.append({"step": step, "summary": "Mute toggled"})
                log_action("mute_toggle", "toggled")

            elif act == 'set_brightness':
                level = int(action.get('level', 50))
                console.print(f"[green]💡 Brightness → {level}%[/green]")
                out = set_brightness(level)
                console.print(f"[dim]   → {out[:100]}[/dim]")
                memory.append({"step": step, "summary": f"Brightness: {level}%"})

            elif act == 'wifi':
                enable = action.get('enable', True)
                state = "ON" if enable else "OFF"
                console.print(f"[green]📡 WiFi → {state}[/green]")
                out = wifi_toggle(enable)
                console.print(f"[dim]   → {out[:100]}[/dim]")
                memory.append({"step": step, "summary": f"WiFi: {state}"})

            elif act == 'bluetooth':
                enable = action.get('enable', True)
                state = "ON" if enable else "OFF"
                console.print(f"[green]🔵 Bluetooth → {state}[/green]")
                out = bluetooth_toggle(enable)
                console.print(f"[dim]   → {out[:100]}[/dim]")
                memory.append({"step": step, "summary": f"Bluetooth: {state}"})

            elif act == 'system_info':
                console.print("[green]📊 System Info[/green]")
                out = get_system_info()
                console.print(f"[dim]{out}[/dim]")
                memory.append({"step": step, "summary": f"System info: {out[:60]}"})

            elif act == 'list_processes':
                console.print("[green]📋 Running Processes[/green]")
                out = get_running_processes()
                console.print(f"[dim]{out[:300]}[/dim]")
                memory.append({"step": step, "summary": f"Listed processes"})

            elif act == 'kill_process':
                name = action.get('name', '')
                console.print(f"[yellow]💀 Kill: {name}[/yellow]")
                out = kill_process(name)
                console.print(f"[dim]   → {out}[/dim]")
                memory.append({"step": step, "summary": f"Kill: {name} → {out[:40]}"})
                log_action("kill_process", name)

            elif act == 'lock_screen':
                console.print("[yellow]🔒 Locking screen...[/yellow]")
                lock_screen()
                memory.append({"step": step, "summary": "Screen locked"})
                log_action("lock_screen", "locked")

            elif act == 'shutdown':
                delay = int(action.get('delay', 30))
                console.print(f"[bold red]⚡ Shutdown in {delay}s[/bold red]")
                shutdown(delay)
                memory.append({"step": step, "summary": f"Shutdown scheduled: {delay}s"})
                log_action("shutdown", f"delay={delay}")

            elif act == 'restart':
                delay = int(action.get('delay', 10))
                console.print(f"[bold red]🔄 Restart in {delay}s[/bold red]")
                restart(delay)
                memory.append({"step": step, "summary": f"Restart scheduled: {delay}s"})
                log_action("restart", f"delay={delay}")

            elif act == 'sleep':
                console.print("[yellow]😴 Sleeping...[/yellow]")
                sleep_pc()
                memory.append({"step": step, "summary": "PC sleeping"})

            elif act == 'create_file':
                fpath = action.get('path', '')
                content = action.get('content', '')
                console.print(f"[green]📄 Create: {fpath}[/green]")
                out = create_file(fpath, content)
                console.print(f"[dim]   → {out}[/dim]")
                memory.append({"step": step, "summary": f"Created: {fpath}"})
                log_action("create_file", fpath)

            # ═══ OpenCode/Claude Code Style Coding Tools ═══
            elif act == 'read_file':
                fpath = action.get('path', '')
                start = action.get('start_line', None)
                end = action.get('end_line', None)
                console.print(f"[cyan]📖 Read: {fpath}[/cyan]")
                try:
                    p = Path(fpath)
                    if not p.is_absolute():
                        p = Path(os.getcwd()) / p
                    text = p.read_text(encoding='utf-8', errors='ignore')
                    lines = text.splitlines()
                    if start and end:
                        chunk = lines[max(0,int(start)-1):int(end)]
                        result_text = '\n'.join(f"{i+max(1,int(start))}: {l}" for i, l in enumerate(chunk))
                        console.print(f"[dim]   Lines {start}-{end} ({len(chunk)} lines)[/dim]")
                    else:
                        result_text = '\n'.join(f"{i+1}: {l}" for i, l in enumerate(lines[:200]))
                        if len(lines) > 200:
                            result_text += f"\n... ({len(lines)} total lines, showing first 200)"
                        console.print(f"[dim]   {len(lines)} lines total[/dim]")
                    memory.append({"step": step, "summary": f"Read: {fpath} ({len(lines)} lines)", "output": result_text})
                except Exception as e:
                    console.print(f"[red]❌ Read failed: {e}[/red]")
                    memory.append({"step": step, "summary": f"Read failed: {fpath}: {e}"})

            elif act == 'write_file':
                fpath = action.get('path', '')
                content = action.get('content', '')
                console.print(f"[green]📝 Write: {fpath}[/green]")
                try:
                    p = Path(fpath)
                    if not p.is_absolute():
                        p = Path(os.getcwd()) / p
                    ext = p.suffix.lower()

                    # HARD BLOCK: Prevent writing the SAME exact file repeatedly
                    prev_writes = [m.get('summary', '') for m in memory[-4:]]
                    if sum(1 for s in prev_writes if fpath in s and 'Wrote:' in s) >= 1 and ext not in ('.py', '.js', '.mjs', '.html'):
                        console.print(f"[bold red]🔄 Loop Prevented! You already wrote {fpath}.[/bold red]")
                        memory.append({
                            "step": step,
                            "summary": f"BLOCKED: You wrote {fpath} multiple times.",
                            "output": "SYSTEM OVERRIDE: You are stuck in a loop writing the same file. YOU MUST IMMEDIATELY CALL THE `done` ACTION. Do not write this file again!"
                        })
                        continue
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content, encoding='utf-8')
                    line_count = content.count('\n') + 1
                    console.print(f"[dim]   ✅ Written {line_count} lines ({len(content)} bytes)[/dim]")
                    
                    # --- GAP 5 FIX: Auto-verify written files ---
                    verify_msg = ""
                    ext = p.suffix.lower()
                    if ext == '.py':
                        vr = subprocess.run(
                            f'python -c "import ast; ast.parse(open(r\'{p}\', encoding=\'utf-8\').read())"',
                            shell=True, capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore'
                        )
                        if vr.returncode != 0:
                            verify_msg = f"⚠️ Python syntax error: {(vr.stderr or '')[:150]}"
                        else:
                            verify_msg = "✅ Python syntax OK"
                    elif ext in ('.js', '.mjs'):
                        vr = subprocess.run(
                            f'node --check "{p}"',
                            shell=True, capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore'
                        )
                        if vr.returncode != 0:
                            verify_msg = f"⚠️ JS syntax error: {(vr.stderr or '')[:150]}"
                        else:
                            verify_msg = "✅ JS syntax OK"
                    elif ext == '.html':
                        # Basic HTML verification: check for matching tags
                        if '<html' in content.lower() and '</html>' in content.lower():
                            verify_msg = "✅ HTML structure OK"
                        elif '<html' in content.lower():
                            verify_msg = "⚠️ HTML missing </html> closing tag"
                    
                    if verify_msg:
                        console.print(f"[dim]   {verify_msg}[/dim]")
                    
                    summary = f"Wrote: {fpath} ({line_count} lines)"
                    if '⚠️' in verify_msg:
                        summary += f" | VERIFY FAILED: {verify_msg}"
                    memory.append({"step": step, "summary": summary})
                    log_action("write_file", str(fpath))
                except Exception as e:
                    console.print(f"[red]❌ Write failed: {e}[/red]")
                    memory.append({"step": step, "summary": f"Write failed: {fpath}: {e}"})

            elif act == 'edit_file':
                fpath = action.get('path', '')
                old_text = action.get('old_text', '')
                new_text = action.get('new_text', '')
                console.print(f"[yellow]✏️ Edit: {fpath}[/yellow]")
                try:
                    p = Path(fpath)
                    if not p.is_absolute():
                        p = Path(os.getcwd()) / p
                    content = p.read_text(encoding='utf-8', errors='ignore')
                    if old_text in content:
                        new_content = content.replace(old_text, new_text, 1)
                        p.write_text(new_content, encoding='utf-8')
                        console.print(f"[dim]   ✅ Replaced {len(old_text)} chars → {len(new_text)} chars[/dim]")
                        memory.append({"step": step, "summary": f"Edited: {fpath} (diff applied)"})
                        log_action("edit_file", str(fpath))
                    else:
                        console.print(f"[red]❌ old_text not found in file![/red]")
                        # Show a snippet of the file to help the agent find the right text
                        preview = content[:500].replace('\n', '\n  ')
                        memory.append({"step": step, "summary": f"Edit failed: old_text not found in {fpath}. File starts with: {preview[:200]}"})
                except Exception as e:
                    console.print(f"[red]❌ Edit failed: {e}[/red]")
                    memory.append({"step": step, "summary": f"Edit failed: {fpath}: {e}"})

            elif act == 'grep_search':
                pattern = action.get('pattern', '')
                include = action.get('include', '')
                console.print(f"[cyan]🔎 Grep: '{pattern}'{' in ' + include if include else ''}[/cyan]")
                try:
                    cmd = f'findstr /S /R /N /C:"{pattern}"'
                    if include:
                        cmd += f' {include}'
                    else:
                        cmd += ' *.*'
                    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, cwd=os.getcwd(), timeout=10, encoding='utf-8', errors='ignore')
                    out = result.stdout.strip()
                    matches = out.splitlines()[:30]
                    for m in matches[:10]:
                        console.print(f"[dim]  {m[:120]}[/dim]")
                    if len(matches) > 10:
                        console.print(f"[dim]  ... +{len(matches)-10} more[/dim]")
                    memory.append({"step": step, "summary": f"Grep '{pattern}': {len(matches)} matches", "output": '\n'.join(matches)})
                except Exception as e:
                    console.print(f"[red]❌ Grep failed: {e}[/red]")
                    memory.append({"step": step, "summary": f"Grep failed: {e}"})

            elif act == 'glob_files':
                pattern = action.get('pattern', '*')
                console.print(f"[cyan]📂 Glob: {pattern}[/cyan]")
                try:
                    import glob as globmod
                    cwd = os.getcwd()
                    found = globmod.glob(os.path.join(cwd, pattern), recursive=True)
                    found = [os.path.relpath(f, cwd) for f in found[:50]]
                    for f in found[:15]:
                        console.print(f"[dim]  {f}[/dim]")
                    if len(found) > 15:
                        console.print(f"[dim]  ... +{len(found)-15} more[/dim]")
                    memory.append({"step": step, "summary": f"Glob '{pattern}': {len(found)} files", "output": '\n'.join(found)})
                except Exception as e:
                    console.print(f"[red]❌ Glob failed: {e}[/red]")
                    memory.append({"step": step, "summary": f"Glob failed: {e}"})

            elif act == 'todo_write':
                # HARD BLOCK: If previous action was also todo_write, force execution instead
                prev_actions = [m.get('summary', '') for m in memory[-3:]]
                was_todo_before = any('Todo updated' in s or 'Todo' in s for s in prev_actions)
                
                if was_todo_before:
                    # Already planned! Read existing todos and force execution of first pending item
                    todo_file = WORKSPACE_DIR / "current_todos.json"
                    existing_todos = []
                    if todo_file.exists():
                        existing_todos = json.loads(todo_file.read_text(encoding='utf-8'))
                    first_pending = next((t for t in existing_todos if t.get('status') != 'done'), None)
                    task_desc = first_pending.get('task', 'the first task') if first_pending else 'creating the project folder'
                    
                    console.print(f"[bold yellow]🔄 Loop detected! Forcing different approach...[/bold yellow]")
                    memory.append({
                        "step": step,
                        "summary": f"BLOCKED: Repeated todo_write",
                        "output": f"SYSTEM OVERRIDE: You already have a plan. STOP PLANNING. You MUST NOW execute: '{task_desc}'. Use 'shell' to create folders (mkdir) or 'write_file' to create the first code file. DO NOT call todo_write or todo_read. Your very next action MUST be 'shell' or 'write_file'."
                    })
                else:
                    todos = action.get('todos', [])
                    console.print(f"[magenta]📋 Todo: {len(todos)} items[/magenta]")
                    todo_file = WORKSPACE_DIR / "current_todos.json"
                    todo_file.write_text(json.dumps(todos, indent=2), encoding='utf-8')
                    for t in todos:
                        icon = '✅' if t.get('status') == 'done' else '🔄' if t.get('status') == 'in_progress' else '⬜'
                        console.print(f"[dim]  {icon} {t.get('id', '?')}. {t.get('task', '')}[/dim]")
                    memory.append({
                        "step": step, 
                        "summary": f"Todo updated: {len(todos)} items", 
                        "output": "Todos saved successfully. SYSTEM INSTRUCTION: DO NOT use todo_write again. Immediately execute the first pending task using 'shell' (mkdir) or 'write_file'. Your next action MUST create a file or folder."
                    })

            elif act == 'todo_read':
                console.print(f"[magenta]📋 Reading todos...[/magenta]")
                todo_file = WORKSPACE_DIR / "current_todos.json"
                if todo_file.exists():
                    todos = json.loads(todo_file.read_text(encoding='utf-8'))
                    for t in todos:
                        icon = '✅' if t.get('status') == 'done' else '🔄' if t.get('status') == 'in_progress' else '⬜'
                        console.print(f"[dim]  {icon} {t.get('id', '?')}. {t.get('task', '')}[/dim]")
                    memory.append({"step": step, "summary": f"Todos: {len(todos)} items", "output": json.dumps(todos)})
                else:
                    console.print(f"[dim]  No active todos[/dim]")
                    memory.append({"step": step, "summary": "No active todos"})

            # --- Window Management ---
            elif act == 'focus_app':
                title = action.get('window_title', '')
                console.print(f"[cyan]🪟 Focus: {title}[/cyan]")
                result = focus_window(title)
                console.print(f"[dim]   → {result}[/dim]")
                memory.append({"step": step, "summary": f"Focused: {title}"})
                time.sleep(0.3)
                needs_screenshot = True

            elif act == 'minimize_window':
                title = action.get('window_title', '')
                console.print(f"[cyan]⬇️ Minimize: {title}[/cyan]")
                result = minimize_window(title)
                console.print(f"[dim]   → {result}[/dim]")
                memory.append({"step": step, "summary": f"Minimized: {title}"})

            elif act == 'maximize_window':
                title = action.get('window_title', '')
                console.print(f"[cyan]⬆️ Maximize: {title}[/cyan]")
                result = maximize_window(title)
                console.print(f"[dim]   → {result}[/dim]")
                memory.append({"step": step, "summary": f"Maximized: {title}"})

            elif act == 'close_window':
                title = action.get('window_title', '')
                console.print(f"[cyan]❌ Close: {title}[/cyan]")
                result = close_window(title)
                console.print(f"[dim]   → {result}[/dim]")
                memory.append({"step": step, "summary": f"Closed: {title}"})
                log_action("close_window", title)

            elif act == 'snap_window':
                title = action.get('window_title', '')
                position = action.get('position', 'left')
                console.print(f"[cyan]📐 Snap: {title} → {position}[/cyan]")
                result = snap_window(title, position)
                console.print(f"[dim]   → {result}[/dim]")
                memory.append({"step": step, "summary": f"Snapped: {title} → {position}"})

            elif act == 'list_windows':
                console.print("[cyan]🪟 Listing windows...[/cyan]")
                windows = list_windows()
                for w in windows[:8]:
                    console.print(f"[dim]  • {w.get('title', '?')} ({w.get('width', 0)}x{w.get('height', 0)})[/dim]")
                memory.append({"step": step, "summary": f"Listed {len(windows)} windows"})

            # --- GUI Actions ---
            elif act in ('click', 'double_click', 'right_click'):
                raw_x, raw_y = int(action.get('x', 0)), int(action.get('y', 0))
                ox, oy = win_offset
                x, y = raw_x + ox, raw_y + oy
                label = {'click': '🖱️', 'double_click': '🖱️🖱️', 'right_click': '🖱️R'}[act]
                console.print(f"[yellow]{label} ({raw_x}+{ox}, {raw_y}+{oy}) → ({x},{y})[/yellow]")
                success = reliable_click(x, y, click_type=act)
                if not success:
                    console.print(f"[red]⚠️ Click failed, retrying...[/red]")
                    reliable_click(x, y, click_type=act)
                memory.append({"step": step, "summary": f"{label} screen({x},{y})"})
                smart_wait(act)
                needs_screenshot = True
                log_action(act, f"({x},{y})")

            elif act == 'win_ui_click':
                name = action.get('name', '')
                ctype = action.get('control_type', '')
                console.print(f"[yellow]🤖 UI Click: Name='{name}', Type='{ctype}'[/yellow]")
                try:
                    import uiautomation as auto
                    # Wait for 3 seconds max to find the control
                    auto.SetGlobalSearchTimeout(3.0)
                    kwargs = {}
                    if name: kwargs['Name'] = name
                    if ctype: kwargs['ControlType'] = getattr(auto.ControlType, ctype, auto.ControlType.ButtonControl)
                    
                    control = auto.Control(**kwargs)
                    if control.Exists(3, 1):
                        control.Click()
                        console.print(f"[dim]   ✅ Clicked native UI element[/dim]")
                        memory.append({"step": step, "summary": f"UI Click target: '{name}' (Success)"})
                    else:
                        console.print(f"[red]⚠️ UI element '{name}' not found on screen![/red]")
                        memory.append({"step": step, "summary": f"UI Click target: '{name}' (Failed - Not found)"})
                except ImportError:
                    console.print(f"[red]❌ uiautomation library missing. Run: pip install uiautomation[/red]")
                    memory.append({"step": step, "summary": f"UI Click failed: uiautomation not installed"})
                except Exception as e:
                    console.print(f"[red]❌ UI Click error: {e}[/red]")
                    memory.append({"step": step, "summary": f"UI Click error: {str(e)[:50]}"})
                smart_wait('click')
                needs_screenshot = True

            elif act == 'type':
                text = action.get('text', '')
                console.print(f"[blue]⌨️ Type: '{text[:60]}'[/blue]")
                ensure_window_focus()
                success = reliable_type(text)
                if not success:
                    console.print(f"[red]⚠️ Type failed, retrying...[/red]")
                    reliable_type(text, use_clipboard=False)
                memory.append({"step": step, "summary": f"Typed: '{text[:40]}'"})
                smart_wait('type')
                needs_screenshot = True
                log_action("type", text[:50])

            elif act == 'press':
                key = action.get('key', 'enter')
                console.print(f"[blue]⌨️ Press: {key}[/blue]")
                ensure_window_focus()
                pyautogui.press(key)
                memory.append({"step": step, "summary": f"Pressed: {key}"})
                smart_wait('press')
                needs_screenshot = True

            elif act == 'hotkey':
                keys = action.get('keys', [])
                console.print(f"[blue]⌨️ Hotkey: {'+'.join(keys)}[/blue]")
                ensure_window_focus()
                pyautogui.hotkey(*keys)
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
                    console.print(f"[blue]🔄 Scroll {direction} ×{amount} at ({sx},{sy})[/blue]")
                else:
                    console.print(f"[blue]🔄 Scroll {direction} ×{amount}[/blue]")
                pyautogui.scroll(-amount if direction == 'down' else amount)
                memory.append({"step": step, "summary": f"Scrolled {direction} ×{amount}"})
                smart_wait('scroll')
                needs_screenshot = True

            elif act == 'drag':
                x1, y1 = int(action.get('x1', 0)), int(action.get('y1', 0))
                x2, y2 = int(action.get('x2', 0)), int(action.get('y2', 0))
                ox, oy = win_offset
                console.print(f"[yellow]↕️ Drag ({x1+ox},{y1+oy}) → ({x2+ox},{y2+oy})[/yellow]")
                drag_and_drop(x1 + ox, y1 + oy, x2 + ox, y2 + oy)
                memory.append({"step": step, "summary": f"Dragged ({x1+ox},{y1+oy})→({x2+ox},{y2+oy})"})
                smart_wait('click')
                needs_screenshot = True

            # --- Web Search Actions ---
            elif act == 'web_search':
                query = action.get('query', '')
                console.print(f"[bold green]🔍 Web Search:[/bold green] {query}")
                try:
                    api_key = os.environ.get('OLLAMA_API_KEY', '')
                    if not api_key:
                        console.print("[red]❌ OLLAMA_API_KEY set nahi hai! Web search ke liye zaroori hai.[/red]")
                        memory.append({"step": step, "summary": f"Web search failed: no API key"})
                    else:
                        search_results = ollama.web_search(query=query)
                        results_text = ""
                        results_list = getattr(search_results, 'results', []) or []
                        for i, r in enumerate(results_list[:5], 1):
                            title = getattr(r, 'title', '') or ''
                            snippet = getattr(r, 'snippet', '') or getattr(r, 'content', '') or ''
                            url = getattr(r, 'url', '') or ''
                            results_text += f"{i}. {title}\n   {snippet[:150]}\n   URL: {url}\n"
                            console.print(f"[dim]  {i}. {title}[/dim]")
                            console.print(f"[dim]     {snippet[:100]}[/dim]")
                        if results_text:
                            memory.append({"step": step, "summary": f"Web search '{query}': {len(results_list)} results\n{results_text[:300]}"})
                        else:
                            memory.append({"step": step, "summary": f"Web search '{query}': no results"})
                            console.print("[yellow]⚠️ Koi results nahi mile[/yellow]")
                except Exception as e:
                    console.print(f"[red]❌ Web search error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Web search error: {str(e)[:60]}"})

            elif act == 'web_fetch':
                url = action.get('url', '')
                console.print(f"[bold green]🌐 Web Fetch:[/bold green] {url}")
                try:
                    api_key = os.environ.get('OLLAMA_API_KEY', '')
                    if not api_key:
                        console.print("[red]❌ OLLAMA_API_KEY set nahi hai![/red]")
                        memory.append({"step": step, "summary": f"Web fetch failed: no API key"})
                    else:
                        fetch_result = ollama.web_fetch(url=url)
                        content = getattr(fetch_result, 'content', '') or str(fetch_result)
                        # Truncate to avoid overwhelming the model
                        display_content = content[:500]
                        memory_content = content[:1000]
                        console.print(f"[dim]  📄 Fetched {len(content)} chars[/dim]")
                        console.print(f"[dim]  {display_content[:200]}...[/dim]")
                        memory.append({"step": step, "summary": f"Web fetch '{url}': {len(content)} chars\n{memory_content}"})
                except Exception as e:
                    console.print(f"[red]❌ Web fetch error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Web fetch error: {str(e)[:60]}"})

            # --- Flow Control ---
            elif act == 'take_screenshot':
                console.print("[dim]📸 Screenshot requested[/dim]")
                needs_screenshot = True
                memory.append({"step": step, "summary": "Requested screenshot"})

            elif act == 'shell':
                cmd = action.get('command', '')
                console.print(f"[green]⚡ Shell:[/green] {cmd}")
                out = run_shell(cmd)
                
                # ── MKDIR LOOP FIX ──
                if "mkdir" in cmd.lower() and "already exists" in out.lower():
                    console.print("[dim]   → (Directory already exists, treating as success)[/dim]")
                    memory.append({"step": step, "summary": f"Shell: `{cmd}` → Success (Directory ready)."})
                else:
                    console.print(f"[dim]   → {out[:250]}...[/dim]")
                    memory.append({"step": step, "summary": f"Shell: `{cmd}` →\n{out[:1500]}"})
                
                smart_wait('shell')
                # Take screenshot after app-opening commands so agent can verify
                if cmd.strip().lower().startswith('start '):
                    needs_screenshot = True

            elif act == 'run_code':
                lang = action.get('language', 'python')
                code = action.get('code', '')
                ctx = action.get('task_context', task)
                console.print(f"[bold magenta]🔧 Self-Healing Code ({lang}):[/bold magenta]")
                console.print(f"[dim]{code[:200]}...[/dim]")
                try:
                    from self_healing import _run_code_with_healing_async
                    heal_result = await _run_code_with_healing_async(
                        lambda p, img=None: _ask_llm(llm, p), lang, code, ctx
                    )
                    output_text = heal_result.get('output', '')
                    if heal_result['success']:
                        memory.append({"step": step, "summary": f"Code ({lang}) SUCCESS after {heal_result['attempts']} attempt(s):\n{output_text[:500]}"})
                        # ── Auto-done: if output mentions file creation, task is complete ──
                        file_signals = ['.pdf', '.pptx', '.xlsx', '.docx', '.mp4', 'saved to', 'saved at', 'created at', 'written to', 'generated']
                        if any(sig in output_text.lower() for sig in file_signals):
                            console.print(f"[bold green]✅ Task Complete! File created: {output_text[:200]}[/bold green]")
                            task_success = True
                            break
                    else:
                        memory.append({"step": step, "summary": f"Code ({lang}) FAILED after {heal_result['attempts']} attempts:\n{output_text[:300]}"})
                except Exception as e:
                    console.print(f"[red]❌ Self-healing error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Self-healing error: {str(e)[:80]}"})
            elif act == 'generate_ppt':
                slides_data = action.get('slides', [])
                theme = action.get('theme', 'dark')
                out_path = action.get('output_path', None)
                ppt_title = action.get('title', 'Presentation')
                console.print(f"[bold cyan]🎨 Generating PPT: {ppt_title} ({theme} theme, {len(slides_data)} slides)[/bold cyan]")
                try:
                    from ppt_generator import create_ppt
                    saved_path = create_ppt(slides_data, output_path=out_path, theme=theme)
                    console.print(f"[bold green]✅ PPT Created: {saved_path}[/bold green]")
                    import subprocess as _sp
                    _sp.Popen(['start', '', saved_path], shell=True)
                    memory.append({"step": step, "summary": f"PPT Created: {saved_path}"})
                except ImportError:
                    console.print("[yellow]⚠️ Installing python-pptx...[/yellow]")
                    import subprocess as _sp
                    _sp.run(['pip', 'install', 'python-pptx', '-q'], check=False)
                    from ppt_generator import create_ppt
                    saved_path = create_ppt(slides_data, output_path=out_path, theme=theme)
                    console.print(f"[bold green]✅ PPT Created: {saved_path}[/bold green]")
                    memory.append({"step": step, "summary": f"PPT Created: {saved_path}"})
                except Exception as e:
                    console.print(f"[red]❌ PPT generation error: {e}[/red]")
                    memory.append({"step": step, "summary": f"PPT generation error: {str(e)[:80]}"})


            elif act == 'local_search':
                query = action.get('query', '')
                console.print(f"[bold green]📂 Local Search:[/bold green] {query}")
                try:
                    from rag import search as rag_search
                    results = rag_search(query, top_k=5)
                    if results:
                        result_text = ""
                        for i, r in enumerate(results, 1):
                            result_text += f"{i}. [{r['extension']}] {r['file_path']}\n   {r['chunk_text'][:150]}...\n"
                            console.print(f"[dim]  {i}. {r['file_path']} (score: {r['score']})[/dim]")
                        memory.append({"step": step, "summary": f"Local search '{query}':\n{result_text[:1000]}"})
                    else:
                        console.print("[yellow]⚠️ Koi result nahi mila. Index karo pehle.[/yellow]")
                        memory.append({"step": step, "summary": f"Local search '{query}': no results"})
                except Exception as e:
                    console.print(f"[red]❌ RAG error: {e}[/red]")
                    memory.append({"step": step, "summary": f"RAG error: {str(e)[:80]}"})

            elif act == 'memory_search':
                query = action.get('query', '')
                console.print(f"[bold cyan]🧠 Memory Search:[/bold cyan] {query}")
                try:
                    from memory_search import search_memory
                    results = search_memory(query, limit=5)
                    console.print(f"[dim]{results[:300]}...[/dim]")
                    memory.append({"step": step, "summary": f"Memory search '{query}':\n{results[:1000]}"})
                except Exception as e:
                    console.print(f"[red]❌ Memory search error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Memory search error: {str(e)[:80]}"})

            elif act == 'memory_search':
                query = action.get('query', '')
                console.print(f"[bold blue]🧠 OpenClaw Memory Search:[/bold blue] {query}")
                try:
                    from memory_search import search_memory
                    result_text = search_memory(query, limit=5)
                    console.print(f"[dim]{result_text[:200]}...[/dim]")
                    memory.append({"step": step, "summary": f"Memory Search '{query}':\n{result_text}"})
                except Exception as e:
                    console.print(f"[red]❌ Memory Search error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Memory error: {str(e)[:80]}"})

            elif act == 'list_workflows':
                console.print("[cyan]📹 Saved Workflows:[/cyan]")
                try:
                    from workflows import list_workflows as wf_list
                    wfs = wf_list()
                    if wfs:
                        wf_text = ""
                        for w in wfs:
                            wf_text += f"• {w['name']} ({w['total_steps']} steps) — {w.get('description', '')}\n"
                            console.print(f"[dim]  • {w['name']} ({w['total_steps']} steps)[/dim]")
                        memory.append({"step": step, "summary": f"Listed {len(wfs)} workflows:\n{wf_text}"})
                    else:
                        console.print("[dim]  Koi saved workflow nahi hai.[/dim]")
                        memory.append({"step": step, "summary": "No saved workflows"})
                except Exception as e:
                    console.print(f"[red]❌ Workflow error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Workflow error: {str(e)[:80]}"})

            elif act == 'replay_workflow':
                wf_name = action.get('name', '')
                console.print(f"[cyan]▶️ Replaying workflow: {wf_name}[/cyan]")
                try:
                    from workflows import load_workflow, replay_workflow
                    wf = load_workflow(wf_name)
                    if wf:
                        await replay_workflow(wf, lambda a: None)  # Basic replay
                        memory.append({"step": step, "summary": f"Replayed workflow: {wf_name}"})
                    else:
                        console.print(f"[yellow]⚠️ Workflow '{wf_name}' not found[/yellow]")
                        memory.append({"step": step, "summary": f"Workflow '{wf_name}' not found"})
                except Exception as e:
                    console.print(f"[red]❌ Replay error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Replay error: {str(e)[:80]}"})

            elif act == 'orchestrate':
                orch_task = action.get('task', task)
                console.print(f"[bold cyan]🧠 Orchestrating complex task...[/bold cyan]")
                try:
                    from orchestrator import orchestrate_task
                    orch_result = await orchestrate_task(
                        llm, _ask_llm, orch_task, run_computer_task
                    )
                    c = orch_result['subtasks_completed']
                    f = orch_result['subtasks_failed']
                    memory.append({"step": step, "summary": f"Orchestrated: {c} done, {f} failed"})
                except Exception as e:
                    console.print(f"[red]❌ Orchestration error: {e}[/red]")
                    memory.append({"step": step, "summary": f"Orchestration error: {str(e)[:80]}"})

            elif act == 'speak':
                speak_text = action.get('text', '')
                speak_voice = action.get('voice', 'hi-IN-MadhurNeural')
                console.print(f"[bold magenta]🔊 Speaking:[/bold magenta] {speak_text[:100]}")
                try:
                    from voice import speak_async
                    import asyncio
                    await speak_async(speak_text, speak_voice)
                    memory.append({"step": step, "summary": f"Spoke: {speak_text[:80]}"})
                except Exception as e:
                    console.print(f"[red]❌ TTS error: {e}[/red]")
                    memory.append({"step": step, "summary": f"TTS error: {str(e)[:80]}"})

            elif act == 'done':
                result = action.get('result', '')
                console.print(Panel(
                    f"✅ {result}",
                    title="ClawBot — Task Complete", border_style="green", padding=(1, 2)
                ))
                record_task(mem, task, memory, success=True)
                
                # Show final result and gracefully END the lifecycle run
                gw_event("chat", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "state": "final", "message": {"role": "assistant", "content": f"✅ {result}"}})
                gw_event("agent", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "stream": "lifecycle", "data": {"phase": "end"}})
                append_daily_memory("AI", result)
                # Auto-speak result if user asked verbally (bol/bata/sunao)
                voice_keywords = ['bol', 'bata', 'sunao', 'speak', 'bolo', 'batao']
                if any(kw in task.lower() for kw in voice_keywords):
                    try:
                        from voice import speak_async
                        await speak_async(result, 'hi-IN-MadhurNeural')
                    except Exception:
                        pass
                task_success = True
                break

            else:
                console.print(f"[red]❓ Unknown action: {act}[/red]")

        except json.JSONDecodeError:
            console.print(f"[red]❌ Invalid JSON from AI[/red]")
            memory.append({"step": step, "summary": "JSON parse error"})
            time.sleep(0.5)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                console.print("\n[bold red]⏳ API Quota Exceeded (429)[/bold red]")
                console.print("[dim]Aapki Free API limit (Gemini/OpenAI) khatam ho gayi hai. Kuch seconds rok lijiye, ClawBot automatically retry karega![/dim]\n")
                memory.append({"step": step, "summary": "Waiting for API Rate Limit Quota"})
                time.sleep(10)  # Wait longer to avoid spamming the server
            else:
                short_err = str(e)[:150] + ("..." if len(str(e)) > 150 else "")
                console.print(f"[red]❌ Error: {short_err}[/red]")
                memory.append({"step": step, "summary": f"Error: {str(e)[:60]}"})
            time.sleep(0.5)

    # ── Save to Memory ──
    record_task(mem, task, memory, task_success)
    
    if not task_success:
        # If loop exited without done, end it as error
        gw_event("agent", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "stream": "lifecycle", "data": {"phase": "error"}})
    else:
        gw_event("agent", {"runId": "clawbot-run", "sessionKey": "clawbot-session", "stream": "lifecycle", "data": {"phase": "end"}})
    learned_count = len(mem.get('learnings', []))
    console.print(f"\n[dim]💾 Task saved. Total learnings: {learned_count}[/dim]\n")

