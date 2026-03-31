"""
🤖 ClawBot - Interactive Browser Automation CLI
Powered by browser-use + Your AI of Choice

Install: pip install clawbot
Run: clawbot
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
import logging
from rich.live import Live
from rich.panel import Panel

# Hide background timeout errors from browser-use/bubus frameworks
logging.getLogger('bubus').setLevel(logging.FATAL)
logging.getLogger('bubus.service').setLevel(logging.FATAL)
logging.getLogger('browser_use.browser').setLevel(logging.FATAL)
logging.getLogger('browser_use.browser.session').setLevel(logging.FATAL)
logging.getLogger('BrowserSession').setLevel(logging.FATAL)

class PanelLogHandler(logging.Handler):
    def __init__(self, max_lines=10):
        super().__init__()
        self.max_lines = max_lines
        self.logs = [""] * max_lines  # Pre-fill to keep height fixed
        self.live = None
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record):
        try:
            msg = self.format(record)
            if not msg.strip(): return
            
            # Clean up the output to look prettier
            if "EVAL:" in msg.upper() or "EVALUATE:" in msg.upper():
                msg = f"[bold green]{msg}[/bold green]"
            elif "MEMORY:" in msg.upper():
                msg = f"[bold magenta]{msg}[/bold magenta]"
            elif "NEXT GOAL:" in msg.upper():
                msg = f"[bold yellow]{msg}[/bold yellow]"
            elif "ACTION:" in msg.upper() or "CLICK:" in msg.upper() or "NAVIGATE:" in msg.upper():
                msg = f"[bold cyan]{msg}[/bold cyan]"

            # Split multi-line messages so they don't break the height limit
            for line in msg.split('\n'):
                # Trim overly long lines to prevent text wrapping from expanding the box height
                if len(line) > 110:
                    line = line[:107] + "..."
                self.logs.append(line)
            
            # Keep exactly max_lines
            self.logs = self.logs[-self.max_lines:]
            
            if self.live:
                content = "\n".join(self.logs)
                self.live.update(Panel(content, title="🧠 Agent", border_style="cyan", subtitle="[dim]Live Logs[/dim]", width=115))
        except Exception:
            pass


def _get_env_file() -> Path:
    """Get the .env file path in user's home directory."""
    env_dir = Path.home() / '.clawbot'
    env_dir.mkdir(exist_ok=True)
    return env_dir / '.env'


def _load_env():
    """Load environment variables from .env file."""
    from dotenv import load_dotenv
    env_file = _get_env_file()
    if env_file.exists():
        load_dotenv(env_file)


def _get_style():
    """Get InquirerPy style."""
    from InquirerPy.utils import InquirerPyStyle
    return InquirerPyStyle({
        'pointer': '#00d4ff bold',
        'highlighted': '#00d4ff bold',
        'question': 'bold',
        'answer': '#00d4ff bold',
        'questionmark': '#ff6b35 bold',
    })


# ─── AI Providers & Models ────────────────────────────────────────────
PROVIDERS = {
    '🟢 Google Gemini': {
        'class': 'ChatGoogle',
        'env_key': 'GOOGLE_API_KEY',
        'models': [
            # Gemini 3.1 (Latest Preview)
            'gemini-3.1-pro-preview',
            'gemini-3.1-flash-preview',
            'gemini-3.1-flash',
            # Gemini 2.5
            'gemini-2.5-pro',
            'gemini-2.5-flash',
            'gemini-2.5-flash-preview-05-20',
            # Gemini 2.0
            'gemini-2.0-flash',
            'gemini-2.0-flash-thinking-exp',
            'gemini-2.0-flash-lite',
            # Gemini 1.5 (Stable, higher free quota)
            'gemini-1.5-pro',
            'gemini-1.5-flash',
            'gemini-1.5-flash-8b',
        ],
    },
    '🔵 OpenAI (ChatGPT)': {
        'class': 'ChatOpenAI',
        'env_key': 'OPENAI_API_KEY',
        'models': [
            'gpt-4o',
            'gpt-4o-mini',
            'o3-mini',
            'o4-mini',
            'gpt-4.1-mini',
        ],
    },
    '🌙 Kimi (Moonshot AI)': {
        'class': 'ChatOpenAI',
        'env_key': 'MOONSHOT_API_KEY',
        'base_url': 'https://api.moonshot.cn/v1',
        'models': [
            'moonshot-v1-8k',
            'moonshot-v1-32k',
            'moonshot-v1-128k',
            'moonshot-v1-auto',
        ],
    },
    '🟠 Anthropic (Claude)': {
        'class': 'ChatAnthropic',
        'env_key': 'ANTHROPIC_API_KEY',
        'models': [
            'claude-3-7-sonnet-20250219 — [Coding & Reasoning Master] (NEW)',
            'claude-3-5-sonnet-latest — [Coding & General Expert]',
            'claude-3-5-haiku-latest — [Fast Instruction & Automation]',
            'claude-3-opus-20240229 — [Complex Math & Deep Thought]',
        ],
    },
    '⚡ Groq (Fast)': {
        'class': 'ChatGroq',
        'env_key': 'GROQ_API_KEY',
        'models': [
            'llama-3.3-70b-versatile',
            'gemma2-9b-it',
        ],
    },
    '🐋 DeepSeek': {
        'class': 'ChatDeepSeek',
        'env_key': 'DEEPSEEK_API_KEY',
        'models': [
            'deepseek-chat',
            'deepseek-reasoner',
        ],
    },
    '🟩 NVIDIA NIM': {
        'class': 'ChatOpenAI',
        'env_key': 'NVIDIA_API_KEY',
        'base_url': 'https://integrate.api.nvidia.com/v1',
        'models': [
            'nvidia/allnemotron-pipeline — [Auto-Router: Code, Vision, Text Master]',
            'nvidia/nemotron-3-super-120b — [Super Intelligence & Logic]',
            'meta/llama-3.3-70b-instruct — [Coding & Conversational Expert] (Voted #1)',
            'meta/llama-3.1-405b-instruct — [Ultra Heavy Reasoning]',
            'meta/llama-3.2-90b-vision-instruct — [Advanced Vision & Image Analysis]',
            'nvidia/llama-3.1-nemotron-70b-instruct — [Research & Creative Writing]',
            'mistralai/mistral-large-2-instruct — [Enterprise Grade Logic]',
            'microsoft/phi-4 — [Fast & Efficient Reasoning] (NEW)',
            'deepseek-ai/deepseek-r1 — [Mathematical & Logic Master] (NEW)',
            'deepseek-ai/deepseek-v3.2 — [Latest DeepSeek Vision & Logic]',
            'deepseek-ai/deepseek-v3.1 — [Optimized Logic & Coding]',
            'z-ai/glm5 — [High-Speed General Intelligence]',
        ],
    },
    '🦙 Ollama (Local - Free)': {
        'class': 'ChatOllama',
        'env_key': None,
        'models': [
            'qwen3-vl:4b — [Local Vision & Action Model 4B]',
            'gemini-3-flash-preview:cloud — [Gemini 3 Flash Preview] (NEW)',
            'deepseek-v3.2:cloud — [DeepSeek V3.2 Vision & Logic] (NEW)',
            'openvoid/Void-Gemini — [Gemini 3 Flash Alt]',
            'qwen3.5:cloud — [Ultimate Coding & Instruction]',
            'kimi-k2.5:cloud — [General Conversational & Fast]',
            'llama3.3 — [Balanced Instruction Expert]',
            'llama3.2 — [Fast General Tasks]',
            'deepseek-r1 — [Deep Mathematics / Reasoning]',
            'qwen3-coder:480b-cloud — [Pure Coding Expert]',
            'qwen2.5 — [Instruction & Coding]',
            'mistral — [Fast & Lightweight]',
            'phi3 — [Code & Math Edge Devices]',
        ],
    },
    '☁️ Ollama (Cloud / Custom Host)': {
        'class': 'ChatOllama',
        'env_key': 'OLLAMA_BASE_URL',
        'is_base_url_only': True,
        'models': [
            'qwen3-vl:4b — [Local Vision & Action Model 4B]',
            'gemini-3-flash-preview:cloud — [Gemini 3 Flash Preview] (NEW)',
            'deepseek-v3.2:cloud — [DeepSeek V3.2 Vision & Logic] (NEW)',
            'openvoid/Void-Gemini — [Gemini 3 Flash Alt]',
            'qwen3.5:cloud — [Ultimate Coding & Instruction]',
            'kimi-k2.5:cloud — [General Conversational & Fast]',
            'llama3.3 — [Balanced Instruction Expert]',
            'llama3.2 — [Fast General Tasks]',
            'deepseek-r1 — [Deep Mathematics / Reasoning]',
            'qwen3-coder:480b-cloud — [Pure Coding Expert]',
            'qwen2.5 — [Instruction & Coding]',
            'mistral — [Fast & Lightweight]',
            'phi3 — [Code & Math Edge Devices]',
        ],
    },
    '🐙 GitHub Models (Marketplace)': {
        'class': 'ChatOpenAI',
        'env_key': 'GITHUB_TOKEN',
        'base_url': 'https://models.github.ai/inference',
        'models': [
            'openai/gpt-4o',
            'openai/gpt-4.1',
            'mistral-ai/Codestral-2501',
            'meta-llama/Llama-3.3-70B-Instruct',
            'cohere/command-r7b-12-2024',
            'AI21-Labs/AI21-Jamba-1.5-Large'
        ],
    },
}


def show_banner(model_name: str = "", mode_label: str = ""):
    """Show the ClawBot Claude Code-style split welcome banner."""
    import io
    import getpass
    import socket
    from rich.console import Console
    from rich.columns import Columns
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table

    # Fix Windows terminal encoding
    if os.name == 'nt':
        os.system('chcp 65001 > nul 2>&1')
        if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    console = Console(force_terminal=True)
    W = console.width or 100

    try:
        username = getpass.getuser()
        cwd = str(Path.home() / 'OneDrive' / 'Desktop')
    except Exception:
        username = 'user'
        cwd = str(Path.home())

    # ── Left side: mini logo + info ──
    mini_logo = (
        "[bold cyan]  ▐▛████▜▌ [/]\n"
        "[bold cyan]  ▝▜█████▛▘[/]\n"
        "[bold cyan]    ▘▘ ▝▝  [/]"
    )
    model_str    = model_name or "ClawBot AI"
    mode_str     = mode_label or "Computer Mode"
    left_content = (
        f"{mini_logo}\n\n"
        f"[bold white]  Welcome back, {username}![/bold white]\n\n"
        f"[dim]  {model_str}[/dim]\n"
        f"[dim]  {mode_str}[/dim]\n"
        f"[dim]  {cwd}[/dim]"
    )

    # ── Right side: shortcuts ──
    right_content = (
        "[bold white]Tips for getting started[/bold white]\n"
        "[dim]─────────────────────────────────[/dim]\n"
        "[dim]❯[/dim]  Type any task and press [bold]Enter[/bold]\n"
        "[dim]❯[/dim]  [bold]/voice[/bold]  💬 Start Voice Mode\n"
        "[dim]❯[/dim]  [bold]/video[/bold]  Switch to video mode\n"
        "[dim]❯[/dim]  [bold]/normal[/bold] Back to agent mode\n"
        "[dim]❯[/dim]  [bold]switch[/bold]  Change AI model\n"
        "[dim]❯[/dim]  [bold]Ctrl+C[/bold] Stop current task\n"
        "[dim]❯[/dim]  [bold]quit[/bold]   Exit ClawBot\n"
        "[dim]─────────────────────────────────[/dim]\n"
        "[dim]No recent activity[/dim]"
    )

    # ── Build the split table ──
    table = Table.grid(padding=(0, 2))
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_row(
        Text.from_markup(left_content),
        Text.from_markup(right_content)
    )

    console.print(Panel(
        table,
        title=f"[bold #00d4ff]── ClawBot v1.0 ──[/bold #00d4ff]",
        border_style='#00d4ff',
        padding=(0, 1),
    ))
    console.print()


def select_provider() -> tuple[str, dict]:
    """Let user pick an AI provider."""
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice

    choices = [Choice(name=name, value=name) for name in PROVIDERS]

    provider_name = inquirer.select(
        message='🧠 AI Provider choose karo:',
        choices=choices,
        style=_get_style(),
    ).execute()

    if provider_name is None:
        sys.exit(0)

    return provider_name, PROVIDERS[provider_name]


def select_model(provider_info: dict) -> str:
    """Let user pick a model from the selected provider."""
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice

    choices = [Choice(name=m, value=m) for m in provider_info['models']]

    model = inquirer.select(
        message='📦 Model choose karo:',
        choices=choices,
        style=_get_style(),
    ).execute()

    if model is None:
        sys.exit(0)

    # Strip the expertise label (e.g. 'llama3.3 — [Expert]' -> 'llama3.3')
    return model.split(' — ')[0].strip()


def get_api_key(provider_info: dict) -> str | None:
    """Get API key — load from saved config or ask user."""
    from InquirerPy import inquirer
    from rich.console import Console

    console = Console()
    env_key = provider_info.get('env_key')

    if env_key is None:
        console.print('[green]✅ Ollama local hai — API key ki zaroorat nahi![/green]')
        return None

    # Check if already set
    existing_key = os.getenv(env_key)
    if existing_key and existing_key != 'your-api-key-here':
        masked = existing_key[:8] + '...' + existing_key[-4:]
        console.print(f'[green]✅ {env_key} found:[/green] {masked}')

        use_existing = inquirer.confirm(
            message='Yahi key use karni hai?',
            default=True,
            style=_get_style(),
        ).execute()

        if use_existing:
            return existing_key

    # Ask for new key
    is_base_url = provider_info.get('is_base_url_only', False)
    prompt_msg = f'🌐 {env_key} enter karo (e.g. http://192.168.1.100:11434):' if is_base_url else f'🔑 {env_key} enter karo:'
    
    api_key_input = inquirer.secret(
        message=prompt_msg,
        style=_get_style(),
    ).execute() if not is_base_url else inquirer.text(
        message=prompt_msg,
        style=_get_style(),
    ).execute()

    if not api_key_input:
        console.print('[red]❌ Required hai![/red]')
        sys.exit(1)

    # Save to config file (~/.clawbot/.env)
    from dotenv import set_key
    env_file = _get_env_file()
    env_file.touch(exist_ok=True)
    set_key(str(env_file), env_key, api_key_input)
    os.environ[env_key] = api_key_input
    console.print(f'[green]✅ {env_key} saved to ~/.clawbot/.env[/green]')

    return api_key_input


def create_llm(provider_info: dict, model: str, api_key: str | None):
    """Create the LLM instance."""
    
    # ── HYBRID MOA ROUTER: AllNemotron Pipeline ──
    if "allnemotron" in model.lower():
        class AllNemotronRouter:
            def __init__(self, key, url):
                from langchain_openai import ChatOpenAI
                self.code_model = ChatOpenAI(model="nvidia/nemotron-3-super-120b", api_key=key, base_url=url, max_retries=1, timeout=45.0)
                self.text_model = ChatOpenAI(model="nvidia/llama-3.1-nemotron-70b-instruct", api_key=key, base_url=url, max_retries=1, timeout=45.0)
                self.vision_model = ChatOpenAI(model="meta/llama-3.2-90b-vision-instruct", api_key=key, base_url=url, max_retries=1, timeout=45.0)
                self.model_name = "AllNemotron Pipeline"

            def _route(self, messages):
                last_msg = messages[-1]
                content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
                is_vision = False
                is_coding = False
                
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            is_vision = True
                        elif isinstance(item, dict) and item.get("type") == "text":
                            txt = item.get("text", "").lower()
                            if any(kw in txt for kw in ["code", "script", "html", "css", "python", "js", "react", "program", "build"]):
                                is_coding = True
                else:
                    txt = str(content).lower()
                    if any(kw in txt for kw in ["code", "script", "html", "css", "python", "js", "react", "program", "build"]):
                        is_coding = True
                        
                from rich.console import Console
                c = Console()
                if is_vision:
                    c.print("[dim magenta]⚡ AllNemotron Routed → Vision Model (Llama-3.2-90B-Vision)[/dim magenta]")
                    return self.vision_model
                elif is_coding:
                    c.print("[dim magenta]⚡ AllNemotron Routed → Coding Model (Llama-3.1-Nemotron-70B)[/dim magenta]")
                    return self.text_model # Note: I swapped this back to text_model for safety if the other errors
                else:
                    c.print("[dim magenta]⚡ AllNemotron Routed → Reasoning Model (Llama-3.1-Nemotron-70B)[/dim magenta]")
                    return self.text_model

            async def ainvoke(self, messages, *args, **kwargs):
                return await self._route(messages).ainvoke(messages, *args, **kwargs)

            async def astream(self, messages, *args, **kwargs):
                kwargs['timeout'] = 45.0
                async for chunk in self._route(messages).astream(messages, *args, **kwargs):
                    yield chunk

        return AllNemotronRouter(api_key, provider_info.get('base_url', ''))

    class_name = provider_info['class']
    from browser_use import llm as llm_module
    chat_class = getattr(llm_module, class_name)

    kwargs = {'model': model}
    
    url_param = 'host' if class_name == 'ChatOllama' else 'base_url'
    
    if api_key:
        if provider_info.get('is_base_url_only'):
            kwargs[url_param] = api_key
        else:
            kwargs['api_key'] = api_key
            
    if 'base_url' in provider_info and not provider_info.get('is_base_url_only'):
        kwargs[url_param] = provider_info['base_url']

    return chat_class(**kwargs)


def ensure_chrome_running() -> bool:
    """Make sure Chrome is running with debugging port."""
    import httpx
    from InquirerPy import inquirer
    from rich.console import Console

    console = Console()

    is_running = False
    try:
        resp = httpx.get('http://127.0.0.1:9222/json/version', timeout=1.0)
        if resp.status_code == 200:
            is_running = True
            console.print('[yellow]⚠️  Ek purani Chrome session abhi bhi chal rahi hai.[/yellow]')
    except Exception:
        console.print('[yellow]⚠️  Chrome debugging mode mein nahi chal raha[/yellow]')

    prompt_msg = 'Chrome ko refresh/restart karein (recommended)?' if is_running else 'Chrome auto-launch karein port 9222 par?'
    launch = inquirer.confirm(
        message=prompt_msg,
        default=True,
        style=_get_style(),
    ).execute()

    if not launch:
        console.print('[red]❌ Chrome ke bina agent nahi chalega![/red]')
        console.print('[dim]Manual: chrome --remote-debugging-port=9222[/dim]')
        return False

    console.print('[dim]Chrome restart ho raha hai...[/dim]')

    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'],
                       capture_output=True, text=True)
        time.sleep(2)
        chrome_paths = [
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        ]
        chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)
        if not chrome_exe:
            console.print('[red]❌ Chrome nahi mila![/red]')
            return False
        temp_profile = os.path.join(os.environ.get('TEMP', '/tmp'), 'clawbot-chrome')
        subprocess.Popen([chrome_exe, '--remote-debugging-port=9222',
                          f'--user-data-dir={temp_profile}'])
    elif sys.platform == 'darwin':
        subprocess.run(['pkill', '-f', 'Google Chrome'], capture_output=True)
        time.sleep(2)
        temp_profile = '/tmp/clawbot-chrome'
        subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                          '--remote-debugging-port=9222', f'--user-data-dir={temp_profile}'])
    else:
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True)
        time.sleep(2)
        temp_profile = '/tmp/clawbot-chrome'
        subprocess.Popen(['google-chrome', '--remote-debugging-port=9222',
                          f'--user-data-dir={temp_profile}'])

    console.print('[dim]Chrome start ho raha hai...[/dim]')
    for _ in range(10):
        time.sleep(1)
        try:
            resp = httpx.get('http://127.0.0.1:9222/json/version', timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                browser = data.get('Browser', 'Unknown')
                console.print(f'[green]✅ Chrome launched:[/green] {browser}')
                return True
        except Exception:
            pass

    console.print('[red]❌ Chrome start nahi hua 10 seconds mein[/red]')
    return False


async def run_task(llm, task: str):
    """Run a single browser task."""
    from browser_use import Agent, BrowserSession
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    session = BrowserSession.from_existing_browser(port=9222)

    # Determine Vision compatibility
    # Vision-capable models get live screen watching (like Google Assistant)
    # for faster, more accurate task completion
    use_vision = True
    provider_name = getattr(llm, '__module__', '')
    model_name = getattr(llm, 'model_name', '') or str(getattr(llm, 'model', ''))
    
    # Vision-first models: always keep vision ON for best accuracy
    # qwen3.5, gemini, gpt-4o, claude etc. are all vision-capable
    vision_first_models = ['qwen3.5', 'qwen3', 'gemini', 'gpt-4o', 'claude', 'kimi']
    is_vision_model = any(vm in model_name.lower() for vm in vision_first_models)
    
    if not is_vision_model:
        # Only forcefully disable for known text-only models
        if 'vision' not in model_name.lower():
            if 'nvidia' in provider_name.lower() or ('llama' in model_name.lower() and 'ollama' not in provider_name.lower()):
                use_vision = False

    agent = Agent(task=task, llm=llm, browser_session=session, use_vision=use_vision)
    
    vision_msg = "" if use_vision else " [dim](vision disabled)[/dim]"
    console.print(f'\n[bold #00d4ff]🚀 Running:[/bold #00d4ff] {task}{vision_msg}\n')

    # Intercept agent logs for the UI Panel
    agent_logger = logging.getLogger('browser_use')
    handler = PanelLogHandler(max_lines=12)
    old_handlers = agent_logger.handlers.copy()
    old_propagate = agent_logger.propagate
    
    for h in old_handlers:
        agent_logger.removeHandler(h)
    agent_logger.addHandler(handler)
    agent_logger.propagate = False

    try:
        with Live(Panel("Initializing...", title="🧠 Agent Thinking...", border_style="cyan", subtitle="[dim]Live Logs[/dim]"), refresh_per_second=4) as live:
            handler.live = live
            result = await agent.run()
            
        console.print(f'\n[green]✅ Done![/green]')
        if result and hasattr(result, 'all_results'):
            for r in result.all_results:
                if r.extracted_content:
                    console.print(Panel(str(r.extracted_content),
                                        title='📋 Result', border_style='green'))
    except KeyboardInterrupt:
        console.print('\n[yellow]⏹️  Task cancelled[/yellow]')
    except Exception as e:
        error_msg = str(e)
        console.print(f'\n[bold red]❌ Task Error:[/bold red] [red]{error_msg}[/red]\n')
        
        # Smart Error Interpreter for User-Friendly Tips
        if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg.upper() or 'rate limit' in error_msg.lower():
            console.print(Panel(
                "[bold yellow]TIPS TO FIX:[/bold yellow]\n\n"
                "• Aapka free API quota (limit) khatam ho gaya hai ya aapne bohut saari requests ek sath bhej di hain.\n"
                "• **Solution:** 5-10 minute wait karein aur wapas try karein, YA naya free provider select karein (jaise NVIDIA NIM ya Kimi).",
                title="⚠️ Rate Limit Exceeded (429)", border_style="yellow"
            ))
        elif '401' in error_msg or 'unauthorized' in error_msg.lower() or 'invalid_api_key' in error_msg.lower():
            console.print(Panel(
                "[bold yellow]TIPS TO FIX:[/bold yellow]\n\n"
                "• Aapki API key galat hai ya expire ho chuki hai.\n"
                "• **Solution:** Aapki key `~/.clawbot/.env` me save stithi me hai. Usko manual delete karke naya setup karein ya dusra API key daalein.",
                title="🔑 Authentication Error (401)", border_style="yellow"
            ))
        elif '404' in error_msg or 'not found' in error_msg.lower():
            console.print(Panel(
                "[bold yellow]TIPS TO FIX:[/bold yellow]\n\n"
                "• Jo Model aapne select kiya hai, wo provider ke paas available nahi hai ya uska server down hai.\n"
                "• **Solution:** List me se koi dusra Model select karein.",
                title="🔍 Model/Endpoint Not Found (404)", border_style="yellow"
            ))
    finally:
        # Restore original loggers
        agent_logger.removeHandler(handler)
        for h in old_handlers:
            agent_logger.addHandler(h)
        agent_logger.propagate = old_propagate
        await session.stop()


def handle_tunnel_command(args):
    """Start a secure tunnel to expose the local ClawBot gateway as wss://"""
    from rich.console import Console
    from rich.panel import Panel
    import subprocess, re, time, threading
    console = Console()

    port = 18789
    # Try to extract --port if given
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except Exception:
            pass

    # Make sure gateway is running
    try:
        from .computer.gateway import start_gateway_thread
        start_gateway_thread()
        time.sleep(0.5)
    except Exception as e:
        console.print(f"[yellow]Gateway warning: {e}[/yellow]")

    console.print(f"\n[bold #00d4ff]🌐 ClawBot Tunnel Starting on port {port}...[/bold #00d4ff]\n")

    def try_cloudflared():
        try:
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            url_pattern = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")
            for line in proc.stderr:
                m = url_pattern.search(line)
                if m:
                    return proc, m.group(0)
        except FileNotFoundError:
            return None, None
        return None, None

    def try_localtunnel():
        try:
            proc = subprocess.Popen(
                ["npx", "--yes", "localtunnel", "--port", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            url_pattern = re.compile(r"https://[^\s]+\.loca\.lt")
            for line in proc.stdout:
                m = url_pattern.search(line)
                if m:
                    return proc, m.group(0)
        except Exception:
            return None, None
        return None, None

    console.print("[dim]Trying Cloudflare tunnel...[/dim]")
    proc, https_url = try_cloudflared()

    if not https_url:
        console.print("[dim]Cloudflare not found, trying localtunnel...[/dim]")
        proc, https_url = try_localtunnel()

    if not https_url:
        console.print("[red]❌ No tunnel provider found![/red]")
        console.print("Install Cloudflare tunnel: [bold]winget install cloudflare.cloudflared[/bold]")
        return

    wss_url = https_url.replace("https://", "wss://")

    console.print(Panel(
        f"[bold green]✅ Tunnel is LIVE![/bold green]\n\n"
        f"Gateway URL (paste in Claw3D):\n"
        f"[bold #00d4ff]{wss_url}[/bold #00d4ff]\n\n"
        f"[dim]Token: run [bold]clawbot devices approve --latest[/bold] in another terminal[/dim]\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        title="🌐 ClawBot Tunnel",
        border_style="#00d4ff"
    ))

    try:
        if proc:
            proc.wait()
    except KeyboardInterrupt:
        if proc:
            proc.terminate()
        console.print("\n[dim]Tunnel stopped.[/dim]")


async def handle_devices_command(args):
    """Handle the 'devices' subcommand (e.g., 'clawbot devices approve --latest')."""
    from rich.console import Console
    console = Console()
    
    if not args or len(args) < 1:
        console.print("[yellow]Usage: clawbot devices [list|approve][/yellow]")
        return

    sub = args[0].lower()
    
    try:
        import websockets
    except ImportError:
        console.print("[red]❌ Required 'websockets' package missing. Install it with: pip install websockets[/red]")
        return

    try:
        async with websockets.connect("ws://127.0.0.1:18789") as ws:
            # Wait for challenge
            challenge_raw = await ws.recv()
            challenge = json.loads(challenge_raw)
            nonce = challenge.get("payload", {}).get("nonce")
            
            # Connect
            await ws.send(json.dumps({
                "type": "req",
                "method": "connect",
                "id": "cli-approval",
                "params": {"auth": {"token": "clawbot-local"}}
            }))
            
            # Wait for connect response
            await ws.recv()
            
            if sub == "list":
                await ws.send(json.dumps({
                    "type": "req",
                    "method": "devices.list",
                    "id": "list-req"
                }))
                res = json.loads(await ws.recv())
                pending = res.get("payload", {}).get("pending", [])
                if not pending:
                    console.print("[green]No connections pending approval.[/green]")
                else:
                    console.print("[bold cyan]Pending Connections:[/bold cyan]")
                    for p in pending:
                        console.print(f"  • IP: {p['ip']} | Code: [bold yellow]{p['pairCode']}[/bold yellow] | Nonce: {p['nonce'][:8]}...")
            
            elif sub == "approve":
                # Find the latest pending device if --latest or no nonce provided
                target_nonce = None
                if "--latest" in args or len(args) == 1:
                     await ws.send(json.dumps({
                        "type": "req",
                        "method": "devices.list",
                        "id": "list-before-approve"
                    }))
                     res = json.loads(await ws.recv())
                     pending = res.get("payload", {}).get("pending", [])
                     if pending:
                         target_nonce = pending[-1]["nonce"]
                
                if not target_nonce and len(args) > 1 and args[1] != "--latest":
                    target_nonce = args[1]

                if not target_nonce:
                    console.print("[red]❌ No pending connection found to approve.[/red]")
                    return

                await ws.send(json.dumps({
                    "type": "req",
                    "method": "devices.approve",
                    "id": "approve-req",
                    "params": {"nonce": target_nonce}
                }))
                
                res = json.loads(await ws.recv())
                if res.get("ok"):
                    token = res.get("payload", {}).get("token")
                    console.print(f"[bold green]✅ Device approved![/bold green]")
                    console.print(f"[dim]Generated Token: {token}[/dim]")
                else:
                    console.print(f"[red]❌ Approval failed: {res.get('error', 'unknown error')}[/red]")

    except Exception as e:
        # Offline fallback: Generate a token directly if gateway isn't running
        if sub == "approve":
            import uuid
            import json
            from pathlib import Path
            new_token = str(uuid.uuid4())
            tokens_file = Path.home() / ".clawbot" / "tokens.json"
            
            authorized_tokens = ["clawbot-local"]
            try:
                if tokens_file.exists():
                    data = json.loads(tokens_file.read_text())
                    authorized_tokens.extend(data.get("tokens", []))
            except Exception:
                pass
                
            authorized_tokens.append(new_token)
            
            try:
                tokens_file.parent.mkdir(exist_ok=True)
                tokens_file.write_text(json.dumps({"tokens": list(set(authorized_tokens))}))
                console.print(f"[bold green]✅ Device offline approved![/bold green]")
                console.print(f"[dim]Generated Token: {new_token}[/dim]")
                console.print("[dim]Aap is token ko Claw3D mein use kar sakte hain.[/dim]")
            except Exception as write_err:
                console.print(f"[red]❌ Token save nahi ho paya: {write_err}[/red]")

        elif sub == "list":
            console.print("[yellow]Gateway is not running. No active pending connections.[/yellow]")
            console.print(f"[dim]Start clawbot in another terminal to see live connections.[/dim]")
        else:
            console.print(f"[red]❌ Gateway is not running! Error: {e}[/red]")


def main():
    """Main CLI entry point — this is what runs when you type 'clawbot'."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    # Check for CLI arguments (subcommands)
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "devices":
            asyncio.run(handle_devices_command(sys.argv[2:]))
            return
        elif cmd == "tunnel":
            handle_tunnel_command(sys.argv[2:])
            return
        elif cmd in ("--version", "-v"):
            console.print("[bold #00d4ff]ClawBot v1.0.0[/bold #00d4ff]")
            return

    # Load saved config
    _load_env()

    # ── Claw3D Gateway (DISABLED — warnings band karne ke liye) ──
    # Agar future mein chahiye toh uncomment kar dena:
    # try:
    #     from .computer.gateway import start_gateway_thread
    #     start_gateway_thread()
    # except Exception as e:
    #     console.print(f"[dim yellow]Warning: Claw3D Gateway start failed: {e}[/dim yellow]")

    show_banner()

    telegram_bot_running = False

    try:
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice

        # ── Step 0: Connect Menu ──
        env_file = _get_env_file()
        has_token = bool(os.environ.get('TELEGRAM_BOT_TOKEN', ''))

        if has_token:
            console.print(f'[green]✅ Telegram Bot auto-connected[/green] (Token saved in .env)\n')
            connect_choice = 'skip'
        else:
            connect_choice = inquirer.select(
                message='Telegram Bot connect karna chahte hain?',
                choices=[
                    Choice(value='skip', name='⏭️  Continue (skip)'),
                    Choice(value='connect', name='📱 Connect Telegram Bot'),
                ],
                style=_get_style(),
            ).execute()

        if connect_choice == 'connect':
            console.print('\n[bold cyan]📱 Telegram Bot Setup[/bold cyan]')
            console.print('[dim]Step 1: @BotFather ko /newbot bhejo → Token milega[/dim]')
            console.print('[dim]Step 2: @userinfobot ko message bhejo → Chat ID milega[/dim]\n')

            bot_token = inquirer.text(
                message='Telegram Bot Token paste karo:',
                style=_get_style(),
            ).execute().strip()

            chat_id = inquirer.text(
                message='Telegram Chat ID paste karo:',
                style=_get_style(),
            ).execute().strip()

            if bot_token:
                # Save to .env
                existing = ''
                if env_file.exists():
                    existing = env_file.read_text()
                
                # Remove old telegram keys if present
                lines = existing.splitlines()
                lines = [l for l in lines if not l.startswith('TELEGRAM_BOT_TOKEN') and not l.startswith('TELEGRAM_CHAT_ID')]
                lines.append(f"TELEGRAM_BOT_TOKEN='{bot_token}'")
                if chat_id:
                    lines.append(f"TELEGRAM_CHAT_ID='{chat_id}'")
                
                env_file.write_text('\n'.join(lines) + '\n')
                os.environ['TELEGRAM_BOT_TOKEN'] = bot_token
                if chat_id:
                    os.environ['TELEGRAM_CHAT_ID'] = chat_id
                has_token = True
                console.print(f'[green]✅ Telegram credentials saved to {env_file}[/green]\n')
            else:
                console.print('[yellow]⚠️ Token empty tha, skip kar rahe hain[/yellow]\n')

        # ── Step 1: Scope Selection ──
        scope = inquirer.select(
            message='Kisko control karna hai aaj?',
            choices=[
                Choice(value='browser', name='🌐 Browser (Web Automation)'), 
                Choice(value='computer', name='💻 Computer (Windows OS Control)'),
                Choice(value='both', name='🔄 Both Control (Computer + Telegram Bot)'),
                Choice(value='deep_os', name='🧩 Deep OS (Native Windows UI Control)'),
            ],
            style=_get_style(),
        ).execute()

        is_computer = scope in ('computer', 'both', 'deep_os')

        if scope == 'deep_os':
            os.environ['CLAWBOT_DEEP_OS'] = '1'
        else:
            os.environ.pop('CLAWBOT_DEEP_OS', None)

        # Telegram config is handled after LLM selection

        mode_label = 'Both (Computer + browser)' if scope == 'both' else ('Computer' if is_computer else 'Browser')
        console.print(f'[#00d4ff]Mode:[/#00d4ff] {mode_label}\n')

        # ── Step 2: Select AI Provider ──
        provider_name, provider_info = select_provider()
        console.print(f'[#00d4ff]Selected:[/#00d4ff] {provider_name}\n')

        # ── Step 3: Select Model ──
        model = select_model(provider_info)
        console.print(f'[#00d4ff]Model:[/#00d4ff] {model}\n')

        # ── Step 4: API Key ──
        api_key = get_api_key(provider_info)
        console.print()

        # ── Step 5: Initialize LLM ──
        try:
            llm = create_llm(provider_info, model, api_key)

            # If 'Both Control', start Telegram bot in background (using selected LLM)
            if scope == 'both':
                if not has_token:
                    console.print('[bold red]❌ Pehle Telegram Bot connect karo! Token set nahi hai.[/bold red]')
                    console.print('[dim]ClawBot restart karo aur "Connect Telegram Bot" select karo.[/dim]')
                    sys.exit(1)
                import pathlib
                import subprocess
                bot_path = pathlib.Path(__file__).parent / "computer" / "telegram_bot.py"
                
                # Kill any existing telegram_bot.py instances to avoid 409 Conflict
                try:
                    subprocess.run(['taskkill', '/F', '/FI', 'WINDOWTITLE eq ClawBot Telegram Bot*'], capture_output=True)
                    result = subprocess.run(['wmic', 'process', 'where', 'CommandLine like "%telegram_bot.py%"', 'get', 'ProcessId', '/FORMAT:VALUE'], capture_output=True, text=True)
                    for line in result.stdout.splitlines():
                        if line.startswith('ProcessId=') and line.strip() != 'ProcessId=':
                            pid = line.split('=')[1].strip()
                            if pid.isdigit():
                                subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                except Exception:
                    pass
                
                # Pass environment variables
                bot_env = os.environ.copy()
                bot_env['CLAWBOT_TELEGRAM_PROVIDER'] = provider_name
                bot_env['CLAWBOT_TELEGRAM_MODEL'] = model
                if api_key:
                    bot_env['CLAWBOT_TELEGRAM_API_KEY'] = api_key
                
                subprocess.Popen(
                    [sys.executable, str(bot_path)], 
                    cwd=str(bot_path.parent),
                    env=bot_env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                telegram_bot_running = True
                console.print('[bold green]✅ Telegram Bot background mein chalu ho gaya![/bold green]')
                console.print(f'[dim]🤖 Linked with Model: {model}[/dim]')
                console.print('[dim]Ab phone se bhi task de sakte hain, aur yahan CLI se bhi.[/dim]\n')
            
            console.print(f'[green]✅ AI ready![/green] {provider_info["class"]}({model})\n')
        except Exception as e:
            console.print(f'[red]❌ LLM create nahi hua: {e}[/red]')
            sys.exit(1)

        # ── Step 6: Ensure Chrome is running (Only for Browser) ──
        if not is_computer:
            if not ensure_chrome_running():
                sys.exit(1)


    except KeyboardInterrupt:
        console.print('\n[yellow]⏹️  ClawBot setup cancelled[/yellow]')
        sys.exit(0)

    # ── Show the Claude Code-style welcome banner AFTER setup ──
    show_banner(model_name=f"{model}", mode_label=mode_label)

    # (Gateway is already running — started at top of main())

    prompt_text = '[bold #00d4ff]❯ [/bold #00d4ff]'
    task_prefix = ""
    W = console.width or 100
    divider = '[dim]' + '─' * W + '[/dim]'

    while True:
        try:
            task = console.input(prompt_text).strip()

            if not task:
                continue

            if task.lower() == '/video':
                try:
                    from InquirerPy import inquirer
                    from InquirerPy.base.control import Choice
                    video_engine = inquirer.select(
                        message='Video Engine choose karo:',
                        choices=[
                            Choice(value='local', name='💻 Local Python (100% Free - make_pro_video.py)'),
                            Choice(value='cloud', name='☁️ Cloud APIs (fal.ai / Paid Koda-Stack)'),
                        ],
                        style=_get_style(),
                    ).execute()
                    os.environ['CLAWBOT_VIDEO_ENGINE'] = video_engine
                except Exception:
                    os.environ['CLAWBOT_VIDEO_ENGINE'] = 'cloud'
                    video_engine = 'cloud'

                prompt_text = '[bold #ff0055]🎬 Video Generate > [/bold #ff0055]'
                task_prefix = "Use your video generation/koda-stack skills to do the following: "
                console.print(f"[dim]Switched to Video Mode ({'Local' if video_engine == 'local' else 'Cloud'}). Type /normal to go back.[/dim]")
                continue
                
            if task.lower() == '/script':
                prompt_text = '[bold #00ffaa]📝 Script Writing > [/bold #00ffaa]'
                task_prefix = "Use your scriptwriting/koda-stack /brief skill to do the following: "
                console.print("[dim]Switched to Script Writing Mode. Type /normal to go back.[/dim]")
                continue
                
            if task.lower() == '/capcut':
                task = r"Mera video 'C:\Users\thaku\OneDrive\Desktop\my project\browser\pro_video.mp4' lo aur CapCut automation skill ka use karke isey edit karo. CapCut open karo, video import karke timeline par dalo, Auto-Captions generate karo, aur ek trending typography template apply karke Export kar do. Yaad rakho, tumhe apne Computer Control actions (shell, click, wait, take_screenshot) use karke exactly wahi UI execution blueprint follow karni hai jo Skills mein `capcut-automation` ke andar likhi hai!"
                console.print(f"\n[bold magenta]🎬 CapCut Editor Mode Activated![/bold magenta]")
                console.print("[dim]AI is taking control of the mouse. Stand back and watch the magic![/dim]\n")
                # Do NOT continue, let it fall through to run_computer_task!

            if task.lower() == '/code':
                prompt_text = '[bold #00ffaa]💻 Code Mode (OpenCode) > [/bold #00ffaa]'
                task_prefix = "Use your bare-metal bash tool and coding-agent skill to execute this task securely via OpenCode. Run the command: opencode run \"{task}\". IMPORTANT: You MUST set pty:true in your bash tool call! Do not try to write the code yourself, just spawn opencode to do it. The user's task is: "
                console.print("\n[bold #00ffaa]💻 ClawBot Code Mode Activated![/bold #00ffaa]")
                console.print("[dim]All tasks will now be routed directly to OpenCode for native execution.\nType /normal to go back to standard agent mode.[/dim]\n")
                continue

            if task.lower().startswith('/mcp'):
                try:
                    import json
                    from pathlib import Path
                    mcp_config_path = Path.home() / '.clawbot' / 'mcp.json'
                    parts = task.strip().split(' ')
                    if len(parts) >= 4 and parts[1] == 'add':
                        name = parts[2]
                        # Handling env vars briefly if they exist
                        env_vars = {}
                        command_parts = parts[3:]
                        if '--env' in command_parts:
                            idx = command_parts.index('--env')
                            env_str = command_parts[idx+1]
                            if '=' in env_str:
                                k, v = env_str.split('=', 1)
                                env_vars[k] = v.strip('"\'')
                            # Remove env args
                            command_parts = command_parts[:idx] + command_parts[idx+2:]
                            
                        if '--' in command_parts:
                            command_parts.remove('--')
                            
                        command = command_parts[0]
                        args = command_parts[1:]
                        
                        mcp_config_path.parent.mkdir(parents=True, exist_ok=True)
                        mcp_data = {"mcpServers": {}}
                        if mcp_config_path.exists():
                            try:
                                mcp_data = json.loads(mcp_config_path.read_text())
                            except Exception:
                                pass
                        
                        mcp_data["mcpServers"][name] = {
                            "command": command,
                            "args": args,
                            "env": env_vars
                        }
                        mcp_config_path.write_text(json.dumps(mcp_data, indent=2))
                        console.print(f"[green]✅ Successfully added MCP server '{name}' to {mcp_config_path}[/green]")
                    else:
                        console.print("[yellow]Usage: /mcp add <name> [--env KEY=VAL] -- <command> [args...][/yellow]")
                except Exception as e:
                    console.print(f"[red]❌ MCP configuration error: {e}[/red]")
                continue

            if task.lower() == '/voice':
                try:
                    from .computer.voice import voice_mode_loop
                    asyncio.run(voice_mode_loop(llm))
                except Exception as e:
                    console.print(f"[red]❌ Voice mode error: {e}[/red]")
                continue

            if task.lower() == '/normal':
                prompt_text = '[bold #ff6b35]🤖 Task > [/bold #ff6b35]'
                task_prefix = ""
                console.print("[dim]Switched back to Normal Agent Mode.[/dim]")
                continue

            if task.lower() in ('quit', 'exit', 'q', 'band karo'):
                console.print('\n[dim]👋 Bye! Browser open rahega.[/dim]')
                break

            if task.lower() == 'switch':
                if not hasattr(sys, '_old_llms'):
                    sys._old_llms = []
                sys._old_llms.append(llm)  # Keep reference to prevent GC closing httpx warning

                provider_name, provider_info = select_provider()
                model = select_model(provider_info)
                api_key = get_api_key(provider_info)
                llm = create_llm(provider_info, model, api_key)
                console.print(f'[green]✅ Switched to {model}[/green]\n')
                continue

            if task.lower() == 'chrome':
                if not is_computer:
                    ensure_chrome_running()
                else:
                    console.print('\n[yellow]⚠️ Aap Computer OS mode me hain, Chrome ki zarurat nahi![/yellow]\n')
                continue

            final_task = task_prefix + task if task_prefix else task

            try:
                if is_computer:
                    from .computer.agent import run_computer_task
                    asyncio.run(run_computer_task(llm, final_task))
                else:
                    asyncio.run(run_task(llm, final_task))
            except KeyboardInterrupt:
                # Stop ONLY the current task — keep ClawBot running!
                console.print(f'\n[bold yellow]⏹ Task roka gaya![/bold yellow] [dim]ClawBot ab bhi chal raha hai.[/dim]')
            console.print(divider)
            console.print(f'[dim]  ? for shortcuts     ❯ {model}[/dim]')
            console.print(divider)

        except KeyboardInterrupt:
            console.print(f'\n[dim]Ctrl+C dabaya. "quit" type karein ClawBot band karne ke liye.[/dim]')
            console.print(divider)
        except EOFError:
            break


if __name__ == '__main__':
    main()
