"""
🕐 Background Daemon (Heartbeat) Module
Runs scheduled tasks from HEARTBEAT.md in the background.
"""
import re
import time
import threading
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()

WORKSPACE = Path.home() / ".clawbot" / "workspace"
HEARTBEAT_FILE = WORKSPACE / "HEARTBEAT.md"


def parse_heartbeat() -> list[dict]:
    """
    Parse HEARTBEAT.md for scheduled tasks.
    
    Expected format in HEARTBEAT.md:
        ## Scheduled Tasks
        - every 30m: check for new emails and notify me
        - every 2h: take a backup of my Documents folder
        - every 24h: summarize today's memory log
        - daily 09:00: good morning greeting with weather update
    """
    if not HEARTBEAT_FILE.exists():
        return []
    
    tasks = []
    content = HEARTBEAT_FILE.read_text(encoding='utf-8')
    
    # Pattern: - every <number><m/h>: <task description>
    interval_pattern = re.compile(
        r'-\s*every\s+(\d+)\s*(m|min|minutes?|h|hr|hours?)\s*:\s*(.+)',
        re.IGNORECASE
    )
    
    # Pattern: - daily HH:MM: <task description>
    daily_pattern = re.compile(
        r'-\s*daily\s+(\d{1,2}):(\d{2})\s*:\s*(.+)',
        re.IGNORECASE
    )
    
    for line in content.splitlines():
        line = line.strip()
        
        # Interval-based tasks
        match = interval_pattern.match(line)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            task_text = match.group(3).strip()
            
            if unit.startswith('h'):
                interval_seconds = amount * 3600
            else:
                interval_seconds = amount * 60
            
            tasks.append({
                "type": "interval",
                "interval_seconds": interval_seconds,
                "task": task_text,
                "last_run": None,
                "label": f"every {amount}{'h' if unit.startswith('h') else 'm'}",
            })
            continue
        
        # Daily scheduled tasks
        match = daily_pattern.match(line)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            task_text = match.group(3).strip()
            
            tasks.append({
                "type": "daily",
                "hour": hour,
                "minute": minute,
                "task": task_text,
                "last_run_date": None,
                "label": f"daily {hour:02d}:{minute:02d}",
            })
    
    return tasks


def _should_run_interval(task: dict) -> bool:
    """Check if an interval task is due."""
    if task["last_run"] is None:
        return True
    elapsed = time.time() - task["last_run"]
    return elapsed >= task["interval_seconds"]


def _should_run_daily(task: dict) -> bool:
    """Check if a daily task should run at this time."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    if task.get("last_run_date") == today_str:
        return False
    
    if now.hour == task["hour"] and now.minute >= task["minute"]:
        return True
    if now.hour > task["hour"]:
        # Missed the exact slot but hasn't run today yet
        return True
    
    return False


def _log_daemon_event(event: str):
    """Write daemon event to today's memory log."""
    try:
        memory_dir = WORKSPACE / "memory"
        memory_dir.mkdir(exist_ok=True)
        today_file = memory_dir / datetime.now().strftime("%Y-%m-%d.md")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"\n### [{timestamp}] DAEMON\n{event}\n"
        
        with open(today_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


async def _execute_heartbeat_task(llm, task_text: str):
    """Run a single heartbeat task through ClawBot."""
    try:
        from agent import run_computer_task
        console.print(f"\n[bold yellow]🕐 Daemon executing:[/bold yellow] {task_text}")
        _log_daemon_event(f"Starting scheduled task: {task_text}")
        await run_computer_task(llm, task_text)
        _log_daemon_event(f"Completed scheduled task: {task_text}")
    except Exception as e:
        console.print(f"[red]❌ Daemon task failed: {e}[/red]")
        _log_daemon_event(f"Failed scheduled task: {task_text} → {str(e)[:100]}")


async def run_daemon(llm):
    """
    Main daemon loop. Parses HEARTBEAT.md and runs tasks on schedule.
    Runs forever until KeyboardInterrupt.
    """
    import asyncio
    
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    
    if not HEARTBEAT_FILE.exists():
        # Create a default HEARTBEAT.md template
        HEARTBEAT_FILE.write_text(
            "# ClawBot Heartbeat Schedule\n\n"
            "## Scheduled Tasks\n"
            "# Add your scheduled tasks below. Examples:\n"
            "# - every 30m: check for new emails and notify me\n"
            "# - every 2h: take a backup of my Documents folder\n"
            "# - daily 09:00: good morning greeting with weather update\n"
            "# - every 24h: summarize today's memory log\n",
            encoding='utf-8'
        )
        console.print(f"[yellow]📝 Created template HEARTBEAT.md at {HEARTBEAT_FILE}[/yellow]")
        console.print("[dim]Add your scheduled tasks and restart the daemon.[/dim]")
        return
    
    tasks = parse_heartbeat()
    
    if not tasks:
        console.print("[yellow]⚠️ HEARTBEAT.md mein koi scheduled task nahi mila![/yellow]")
        console.print(f"[dim]Edit karo: {HEARTBEAT_FILE}[/dim]")
        return
    
    console.print(f"\n[bold cyan]🕐 ClawBot Daemon Started[/bold cyan]")
    console.print(f"[dim]Monitoring {len(tasks)} scheduled task(s):[/dim]")
    for t in tasks:
        console.print(f"[dim]  • [{t['label']}] {t['task']}[/dim]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")
    
    _log_daemon_event(f"Daemon started with {len(tasks)} tasks")
    
    try:
        while True:
            for task in tasks:
                should_run = False
                
                if task["type"] == "interval" and _should_run_interval(task):
                    should_run = True
                elif task["type"] == "daily" and _should_run_daily(task):
                    should_run = True
                
                if should_run:
                    await _execute_heartbeat_task(llm, task["task"])
                    
                    if task["type"] == "interval":
                        task["last_run"] = time.time()
                    elif task["type"] == "daily":
                        task["last_run_date"] = datetime.now().strftime("%Y-%m-%d")
            
            # Re-parse HEARTBEAT.md periodically (hot-reload)
            await asyncio.sleep(30)
            tasks = parse_heartbeat()
            
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Daemon stopped.[/yellow]")
        _log_daemon_event("Daemon stopped by user")

