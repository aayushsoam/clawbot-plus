"""
🔧 Self-Healing Code Execution Module
Writes code to a temp file, runs it, and auto-fixes errors in a loop.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

MAX_RETRIES = 5
TIMEOUT_SECONDS = 30


def run_code_with_healing(llm_ask_fn, language: str, code: str, task_context: str = "") -> dict:
    """
    Execute code and if it fails, ask the LLM to fix it automatically.
    
    Args:
        llm_ask_fn: async function(prompt, image=None) -> str (the LLM caller)
        language: 'python' or 'powershell'
        code: the code to execute
        task_context: optional context about what this code is supposed to do
        
    Returns:
        dict with keys: success, output, final_code, attempts
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_code_with_healing_async(llm_ask_fn, language, code, task_context)
    )


async def _run_code_with_healing_async(llm_ask_fn, language: str, code: str, task_context: str = "") -> dict:
    """Async implementation of the self-healing code runner."""
    
    current_code = code
    all_errors = []
    
    for attempt in range(1, MAX_RETRIES + 1):
        console.print(f"\n[bold cyan]🔄 Attempt {attempt}/{MAX_RETRIES}[/bold cyan]")
        
        # Write code to temp file
        ext = ".py" if language == "python" else ".ps1"
        with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False, encoding='utf-8') as f:
            f.write(current_code)
            temp_path = f.name
        
        try:
            # Execute the code
            result = _execute_code(temp_path, language)
            
            if result["success"]:
                console.print(Panel(
                    f"[green]✅ Code executed successfully on attempt {attempt}![/green]\n"
                    f"[dim]{result['output'][:300]}[/dim]",
                    title="Self-Healing: Success", border_style="green"
                ))
                return {
                    "success": True,
                    "output": result["output"],
                    "final_code": current_code,
                    "attempts": attempt,
                }
            
            # Code failed — collect error
            error_msg = result["error"]
            all_errors.append(f"Attempt {attempt}: {error_msg}")
            
            console.print(f"[red]❌ Error (attempt {attempt}):[/red] {error_msg[:200]}")
            
            if attempt < MAX_RETRIES:
                # Ask LLM to fix the code
                console.print("[yellow]🧠 Asking AI to fix the error...[/yellow]")
                
                fix_prompt = _build_fix_prompt(language, current_code, error_msg, all_errors, task_context)
                fixed_response = await llm_ask_fn(fix_prompt)
                
                # Extract code from LLM response
                fixed_code = _extract_code(fixed_response, language)
                
                if fixed_code and fixed_code.strip() != current_code.strip():
                    current_code = fixed_code
                    console.print("[green]📝 AI ne code fix kar diya, retry kar raha hu...[/green]")
                else:
                    console.print("[yellow]⚠️ AI ne same code return kiya, trying broader fix...[/yellow]")
                    # Ask for a completely different approach
                    rewrite_prompt = (
                        f"The previous {language} code failed {attempt} times with these errors:\n"
                        + "\n".join(all_errors) + "\n\n"
                        f"Write a COMPLETELY DIFFERENT approach to accomplish this task:\n{task_context}\n\n"
                        f"Return ONLY the {language} code, nothing else."
                    )
                    rewrite_response = await llm_ask_fn(rewrite_prompt)
                    rewritten = _extract_code(rewrite_response, language)
                    if rewritten:
                        current_code = rewritten
        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    
    # All retries exhausted
    console.print(Panel(
        f"[red]❌ {MAX_RETRIES} attempts mein bhi fix nahi hua.[/red]\n"
        f"[dim]Last error: {all_errors[-1] if all_errors else 'Unknown'}[/dim]",
        title="Self-Healing: Failed", border_style="red"
    ))
    return {
        "success": False,
        "output": "\n".join(all_errors),
        "final_code": current_code,
        "attempts": MAX_RETRIES,
    }


def _execute_code(file_path: str, language: str) -> dict:
    """Execute a code file and return success/error."""
    try:
        import sys
        if language == "python":
            cmd = [sys.executable, file_path]
        elif language == "powershell":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", file_path]
        else:
            return {"success": False, "output": "", "error": f"Unsupported language: {language}"}
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=TIMEOUT_SECONDS,
        )
        
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        
        if result.returncode == 0:
            return {"success": True, "output": stdout or "(completed with no output)", "error": ""}
        else:
            error = stderr or f"Exit code {result.returncode}"
            return {"success": False, "output": stdout, "error": error}
            
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"Timed out after {TIMEOUT_SECONDS}s"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


def _build_fix_prompt(language: str, code: str, error: str, all_errors: list, context: str) -> str:
    """Build a prompt asking the LLM to fix the broken code."""
    return (
        f"You are a {language} debugging expert. Fix the following code that produced an error.\n\n"
        f"TASK CONTEXT: {context}\n\n"
        f"BROKEN CODE:\n```{language}\n{code}\n```\n\n"
        f"ERROR:\n```\n{error}\n```\n\n"
        f"PREVIOUS ERRORS: {'; '.join(all_errors[-3:])}\n\n"
        f"RULES:\n"
        f"- Return ONLY the complete fixed {language} code\n"
        f"- Do NOT explain anything, no markdown headers, just pure code\n"
        f"- Make sure the fix addresses the root cause\n"
        f"- If a module is missing, try an alternative approach\n"
        f"- Wrap the code in ```{language} ... ``` fences"
    )


def _extract_code(response: str, language: str) -> str | None:
    """Extract code from LLM response (handles markdown fences)."""
    import re
    
    # Try to extract from code fences
    patterns = [
        rf'```{language}\s*\n(.*?)```',
        r'```\w*\s*\n(.*?)```',
        r'```\s*\n(.*?)```',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # If no fences found, try to use the whole response as code
    # (only if it looks like code — has indentation or common keywords)
    lines = response.strip().split('\n')
    code_indicators = ['import ', 'def ', 'class ', 'for ', 'if ', 'print(', 'return ',
                        'function ', 'const ', 'let ', 'var ', '$', 'Get-', 'Set-']
    
    if any(any(indicator in line for indicator in code_indicators) for line in lines[:5]):
        return response.strip()
    
    return None

