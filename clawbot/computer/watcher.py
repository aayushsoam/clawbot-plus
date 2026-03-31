"""
👁️ Proactive Context Awareness (Watcher) Module
Monitors the screen in the background and offers help when user appears stuck.
"""
import os
import time
import base64
import asyncio
import threading
from io import BytesIO
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()

# How often to check the screen (seconds)
WATCH_INTERVAL = 30

# Track recent states to avoid spamming
_last_notification_time = 0
_notification_cooldown = 120  # Min 2 minutes between notifications


def _take_screenshot_b64() -> str | None:
    """Take a screenshot and return base64 string."""
    try:
        from PIL import ImageGrab
        screenshot = ImageGrab.grab()
        screenshot.thumbnail((800, 600))  # Small size for quick analysis
        buf = BytesIO()
        screenshot.save(buf, format="JPEG", quality=50)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception:
        return None


def _show_notification(title: str, message: str):
    """Show a Windows toast notification."""
    try:
        # Try plyer first (cross-platform)
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="ClawBot",
            timeout=10,
        )
        return
    except ImportError:
        pass
    
    try:
        # Fallback: PowerShell toast notification (Windows 10+)
        import subprocess
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $template = @"
        <toast>
            <visual>
                <binding template="ToastGeneric">
                    <text>{title}</text>
                    <text>{message}</text>
                </binding>
            </visual>
        </toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ClawBot").Show($toast)
        '''
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, timeout=10
        )
    except Exception:
        # Last fallback: just print to console
        console.print(f"\n[bold yellow]🔔 {title}[/bold yellow]")
        console.print(f"[yellow]{message}[/yellow]\n")


async def _analyze_screen(ask_llm_fn, screenshot_b64: str) -> dict | None:
    """
    Ask the LLM to analyze if the user appears stuck.
    
    Returns:
        dict with 'is_stuck' (bool) and 'suggestion' (str), or None
    """
    prompt = (
        "You are a helpful assistant watching the user's screen. "
        "Analyze this screenshot and determine:\n"
        "1. Is the user stuck on an error, warning, or popup?\n"
        "2. Is there a dialog box or notification that needs attention?\n"
        "3. Is there a crash or hang visible?\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"is_stuck": true/false, "issue": "brief description of issue", "suggestion": "what you can help with"}\n\n'
        "If the screen looks normal (desktop, browser, coding), set is_stuck to false.\n"
        "Only set is_stuck to true if there is a clear error, popup, or crash visible."
    )
    
    try:
        from browser_use.llm.messages import UserMessage
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}}
        ]
        messages = [UserMessage(content=content)]
        response = await ask_llm_fn(messages)
        
        # Parse the response
        import json
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Extract JSON
        if '{' in response_text:
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start != -1 and end != -1:
                result = json.loads(response_text[start:end+1])
                return result
    except Exception:
        pass
    
    return None


class ScreenWatcher:
    """Background thread that watches the screen and notifies when user is stuck."""
    
    def __init__(self, llm):
        self.llm = llm
        self._running = False
        self._thread = None
    
    def start(self):
        """Start the watcher in a background thread."""
        if self._running:
            console.print("[yellow]⚠️ Watcher already running![/yellow]")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        
        console.print("[bold cyan]👁️ Proactive Watcher started[/bold cyan]")
        console.print(f"[dim]Checking screen every {WATCH_INTERVAL}s for errors/issues...[/dim]")
    
    def stop(self):
        """Stop the watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        console.print("[yellow]🛑 Watcher stopped.[/yellow]")
    
    def _watch_loop(self):
        """Main watch loop running in background thread."""
        global _last_notification_time
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self._running:
            try:
                time.sleep(WATCH_INTERVAL)
                
                if not self._running:
                    break
                
                # Check cooldown
                now = time.time()
                if now - _last_notification_time < _notification_cooldown:
                    continue
                
                # Take screenshot
                b64 = _take_screenshot_b64()
                if not b64:
                    continue
                
                # Analyze with LLM
                result = loop.run_until_complete(
                    _analyze_screen(self.llm.ainvoke, b64)
                )
                
                if result and result.get("is_stuck"):
                    issue = result.get("issue", "Unknown issue")
                    suggestion = result.get("suggestion", "Main help kar sakta hu")
                    
                    _show_notification(
                        "🤖 ClawBot detected an issue!",
                        f"{issue}\n{suggestion}"
                    )
                    _last_notification_time = now
                    
                    # Log to memory
                    try:
                        from agent import append_daily_memory
                        append_daily_memory("WATCHER", f"Detected: {issue}. Suggested: {suggestion}")
                    except Exception:
                        pass
                    
            except Exception:
                pass  # Silent failure in background thread
        
        loop.close()

