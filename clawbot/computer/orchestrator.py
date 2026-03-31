"""
🧠 Multi-Agent Orchestrator Module
Breaks complex tasks into sub-tasks and coordinates multiple AI workers.
"""
import json
from rich.console import Console
from rich.panel import Panel

console = Console()


async def orchestrate_task(llm, ask_llm_fn, task: str, execute_subtask_fn) -> dict:
    """
    Break a complex task into sub-tasks, execute each, and combine results.
    
    Args:
        llm: The LLM instance
        ask_llm_fn: async function(llm, prompt) -> str
        task: The complex task description
        execute_subtask_fn: async function(llm, subtask_text) -> None
        
    Returns:
        dict with keys: success, subtasks_completed, subtasks_failed
    """
    
    console.print(Panel(
        f"[bold cyan]🧠 Multi-Agent Orchestration[/bold cyan]\n"
        f"[dim]Task: {task}[/dim]",
        border_style="cyan"
    ))
    
    # ── Phase 1: Planning (Planner Agent) ──
    console.print("\n[yellow]📋 Phase 1: Planner Agent breaking down the task...[/yellow]")
    
    plan_prompt = f"""You are a Task Planner. Break this complex task into simple, sequential sub-tasks.
Each sub-task should be a single, actionable step that can be done independently.

TASK: {task}

Return a JSON array of sub-tasks. Each sub-task should have:
- "id": sequential number
- "description": clear action description
- "depends_on": id of task that must complete first (0 = no dependency)

Example:
```json
[
  {{"id": 1, "description": "Create a new folder called 'project'", "depends_on": 0}},
  {{"id": 2, "description": "Create index.html inside the 'project' folder", "depends_on": 1}},
  {{"id": 3, "description": "Create style.css inside the 'project' folder", "depends_on": 1}}
]
```

Return ONLY the JSON array, no other text."""

    try:
        plan_response = await ask_llm_fn(llm, plan_prompt)
        subtasks = _parse_subtasks(plan_response)
    except Exception as e:
        console.print(f"[red]❌ Planning failed: {e}[/red]")
        return {"success": False, "subtasks_completed": 0, "subtasks_failed": 1}
    
    if not subtasks:
        console.print("[yellow]⚠️ Could not break task into sub-tasks. Running as single task.[/yellow]")
        await execute_subtask_fn(llm, task)
        return {"success": True, "subtasks_completed": 1, "subtasks_failed": 0}
    
    console.print(f"[green]✅ Plan created: {len(subtasks)} sub-tasks[/green]")
    for st in subtasks:
        dep = f" (after #{st['depends_on']})" if st.get('depends_on', 0) > 0 else ""
        console.print(f"[dim]  {st['id']}. {st['description']}{dep}[/dim]")
    
    # ── Phase 2: Execution (Worker Agents) ──
    console.print(f"\n[yellow]⚙️ Phase 2: Executing {len(subtasks)} sub-tasks...[/yellow]")
    
    completed = set()
    failed = set()
    results = {}
    
    for st in subtasks:
        task_id = st["id"]
        desc = st["description"]
        depends = st.get("depends_on", 0)
        
        # Check dependency
        if depends > 0 and depends not in completed:
            console.print(f"[red]⏭️ Skipping #{task_id} (dependency #{depends} not met)[/red]")
            failed.add(task_id)
            continue
        
        console.print(f"\n[bold cyan]🔨 Worker #{task_id}:[/bold cyan] {desc}")
        
        try:
            await execute_subtask_fn(llm, desc)
            completed.add(task_id)
            results[task_id] = "success"
            console.print(f"[green]  ✅ #{task_id} complete[/green]")
        except Exception as e:
            failed.add(task_id)
            results[task_id] = f"failed: {str(e)[:80]}"
            console.print(f"[red]  ❌ #{task_id} failed: {e}[/red]")
    
    # ── Phase 3: Review ──
    console.print(f"\n[yellow]📊 Phase 3: Review[/yellow]")
    console.print(f"[green]  ✅ Completed: {len(completed)}/{len(subtasks)}[/green]")
    if failed:
        console.print(f"[red]  ❌ Failed: {len(failed)}/{len(subtasks)}[/red]")
    
    overall_success = len(failed) == 0
    
    if overall_success:
        console.print(Panel(
            f"[green]🎉 All {len(subtasks)} sub-tasks completed successfully![/green]",
            title="Orchestration Complete", border_style="green"
        ))
    else:
        console.print(Panel(
            f"[yellow]⚠️ {len(completed)}/{len(subtasks)} sub-tasks completed. {len(failed)} failed.[/yellow]",
            title="Orchestration Partial", border_style="yellow"
        ))
    
    return {
        "success": overall_success,
        "subtasks_completed": len(completed),
        "subtasks_failed": len(failed),
        "results": results,
    }


def is_complex_task(task: str) -> bool:
    """Heuristic to determine if a task is complex enough for multi-agent orchestration."""
    complexity_keywords = [
        "build", "create app", "full project", "website bana", "complete",
        "multiple files", "setup", "configure and deploy", "entire",
        "from scratch", "step by step", "poora", "bana do", "develop",
    ]
    task_lower = task.lower()
    
    # Long tasks are likely complex
    if len(task.split()) > 20:
        return True
    
    # Check for complexity keywords
    if any(kw in task_lower for kw in complexity_keywords):
        return True
    
    return False


def _parse_subtasks(response: str) -> list[dict]:
    """Parse LLM response into a list of subtask dicts."""
    import re
    
    # Try to extract JSON array
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()
    
    # Find array brackets
    start = response.find('[')
    end = response.rfind(']')
    
    if start != -1 and end != -1:
        json_str = response[start:end+1]
        try:
            subtasks = json.loads(json_str)
            if isinstance(subtasks, list) and len(subtasks) > 0:
                return subtasks
        except json.JSONDecodeError:
            pass
    
    return []

