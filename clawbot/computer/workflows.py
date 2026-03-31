"""
📹 Workflow Cloning (Demonstration Learning) Module
Record ClawBot action sequences and replay them later as macros.
"""
import json
import time
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()

WORKFLOWS_DIR = Path.home() / ".clawbot" / "workflows"


def ensure_dir():
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


def start_recording(name: str) -> dict:
    """Start recording a new workflow session."""
    ensure_dir()
    return {
        "name": name,
        "created_at": datetime.now().isoformat(),
        "steps": [],
        "is_recording": True,
    }


def record_step(session: dict, action: dict, result_summary: str):
    """Record a single action step during a workflow recording session."""
    if not session.get("is_recording"):
        return
    
    step = {
        "step_number": len(session["steps"]) + 1,
        "timestamp": datetime.now().isoformat(),
        "action": action.get("action"),
        "params": {k: v for k, v in action.items() if k not in ("action", "thought")},
        "thought": action.get("thought", ""),
        "result": result_summary[:200],
    }
    session["steps"].append(step)


def stop_recording(session: dict, description: str = "") -> str:
    """Stop recording and save the workflow to disk."""
    ensure_dir()
    session["is_recording"] = False
    session["description"] = description
    session["total_steps"] = len(session["steps"])
    
    # Save workflow
    safe_name = "".join(c if c.isalnum() or c in '-_ ' else '' for c in session["name"])
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    filename = f"{safe_name}.json"
    filepath = WORKFLOWS_DIR / filename
    
    filepath.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding='utf-8')
    
    console.print(f"[green]✅ Workflow '{session['name']}' saved with {len(session['steps'])} steps[/green]")
    console.print(f"[dim]File: {filepath}[/dim]")
    
    return str(filepath)


def list_workflows() -> list[dict]:
    """List all saved workflows."""
    ensure_dir()
    workflows = []
    
    for f in WORKFLOWS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            workflows.append({
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "total_steps": data.get("total_steps", 0),
                "created_at": data.get("created_at", ""),
                "file": str(f),
            })
        except Exception:
            continue
    
    return workflows


def load_workflow(name: str) -> dict | None:
    """Load a saved workflow by name."""
    ensure_dir()
    
    # Try exact filename first
    for f in WORKFLOWS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if data.get("name", "").lower() == name.lower() or f.stem.lower() == name.lower():
                return data
        except Exception:
            continue
    
    return None


async def replay_workflow(workflow: dict, execute_action_fn):
    """
    Replay a saved workflow step by step.
    
    Args:
        workflow: The loaded workflow dict
        execute_action_fn: async function(action_dict) → str that executes a ClawBot action
    """
    steps = workflow.get("steps", [])
    name = workflow.get("name", "Unknown")
    
    console.print(f"\n[bold cyan]▶️ Replaying workflow: {name}[/bold cyan]")
    console.print(f"[dim]{len(steps)} steps to execute[/dim]\n")
    
    for i, step in enumerate(steps, 1):
        action_name = step.get("action", "unknown")
        params = step.get("params", {})
        
        # Reconstruct the action dict
        action = {"action": action_name, **params}
        
        console.print(f"[cyan]📍 Step {i}/{len(steps)}:[/cyan] {action_name} {json.dumps(params)[:80]}")
        
        try:
            result = await execute_action_fn(action)
            console.print(f"[dim]   → {str(result)[:100]}[/dim]")
        except Exception as e:
            console.print(f"[red]   ❌ Step failed: {e}[/red]")
        
        # Small delay between steps for stability
        time.sleep(0.5)
    
    console.print(f"\n[green]✅ Workflow '{name}' replay complete![/green]")


def delete_workflow(name: str) -> bool:
    """Delete a saved workflow by name."""
    ensure_dir()
    
    for f in WORKFLOWS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if data.get("name", "").lower() == name.lower() or f.stem.lower() == name.lower():
                f.unlink()
                console.print(f"[green]✅ Workflow '{name}' deleted.[/green]")
                return True
        except Exception:
            continue
    
    console.print(f"[yellow]⚠️ Workflow '{name}' not found.[/yellow]")
    return False

