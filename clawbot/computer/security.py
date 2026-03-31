"""
🔒 ClawBot Security Module
Blocks dangerous commands, sanitizes shell input, and logs all actions.
"""

import json
import re
from datetime import datetime
from pathlib import Path

COMPUTER_DIR = Path(__file__).parent
SECURITY_LOG = COMPUTER_DIR / "security_log.json"

# ════════════════════════════════════════════════════════
# 🚫 BLOCKED PATTERNS — Never execute these
# ════════════════════════════════════════════════════════

BLOCKED_COMMANDS = [
    # Destructive disk operations
    r'(?:^|\s)format\s+[a-zA-Z]:',         # format C:, format D: (disk format only)
    r'\bdiskpart\b',                     # disk partition tool
    r'\bclean\b.*\ball\b',              # diskpart clean all
    
    # Mass file deletion
    r'\bdel\b.*(/s|/q|\\)',             # del /s /q recursive
    r'\brmdir\b.*(/s|/q)',             # rmdir /s /q
    r'\brd\b.*(/s|/q)',                # rd /s /q
    r'\brm\b.*-r.*/',                  # rm -rf (WSL/Git Bash)
    r'Remove-Item.*-Recurse.*-Force.*(Windows|System32|Program)', # PowerShell recursive delete system dirs
    
    # Registry manipulation
    r'\breg\b.*(delete|add).*HKLM',    # Registry edit HKLM
    r'\bregedit\b',                     # Registry editor
    
    # System file attacks
    r'system32',                        # Anything touching system32
    r'\\Windows\\System',              # System directory access
    r'\bsfc\b',                         # System file checker
    r'\bbcdedit\b',                     # Boot config editor
    
    # Credential/security attacks
    r'\bnet\b.*user.*\b/add\b',        # Adding users
    r'\bnet\b.*localgroup.*admin',     # Adding to admin group
    r'mimikatz',                        # Password dumping tool
    r'\bcmdkey\b',                      # Credential manager
    
    # Network attacks
    r'\bnetsh\b.*firewall.*disable',   # Disable firewall
    r'\bnetsh\b.*advfirewall.*off',    # Turn off firewall
    
    # Crypto/ransomware patterns
    r'cipher.*(/e|/w)',                # Encrypt/wipe
    r'\bbitlocker\b',                   # BitLocker manipulation
    
    # Process injection
    r'Invoke-Expression.*DownloadString', # Remote code execution
    r'IEX.*Net\.WebClient',            # IEX download cradle
    r'-enc\b.*[A-Za-z0-9+/=]{20,}',   # Base64 encoded commands
]

RESTRICTED_PATHS = [
    r'C:\\Windows',
    r'C:\\Program Files',
    r'C:\\Program Files \(x86\)',
    r'C:\\ProgramData',
]

# ════════════════════════════════════════════════════════
# 🛡️ SECURITY FUNCTIONS
# ════════════════════════════════════════════════════════

def is_command_safe(command: str) -> tuple[bool, str]:
    """
    Check if a shell command is safe to execute.
    
    Returns:
        (is_safe, reason) — True if safe, False with reason if blocked
    """
    cmd_lower = command.lower().strip()
    
    # Check against blocked patterns
    for pattern in BLOCKED_COMMANDS:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return False, f"🚫 BLOCKED: Command matches dangerous pattern '{pattern}'"
    
    # Check for restricted path writes
    for path_pattern in RESTRICTED_PATHS:
        if re.search(path_pattern, command, re.IGNORECASE):
            # Allow read-only operations and app launching (dir, ls, cat, type, Get-Content, Start)
            safe_ops = ['dir ', 'ls ', 'cat ', 'type ', 'get-content', 'get-childitem', 'test-path', 'start ', 'start-process']
            if any(command.lower().strip().startswith(op) for op in safe_ops):
                continue
            return False, f"🚫 BLOCKED: Writing to restricted system path"
    
    # Check for PowerShell execution policy bypass
    if 'executionpolicy' in cmd_lower and 'bypass' in cmd_lower:
        return False, "🚫 BLOCKED: Execution policy bypass attempt"
    
    # Check for downloading and executing
    if ('download' in cmd_lower or 'wget' in cmd_lower or 'curl' in cmd_lower) and \
       ('invoke' in cmd_lower or 'iex' in cmd_lower or ('start' in cmd_lower and 'start http' not in cmd_lower)):
        return False, "🚫 BLOCKED: Download-and-execute pattern detected"
    
    return True, "✅ Safe"


def is_path_safe(path: str) -> tuple[bool, str]:
    """Check if a file path is safe to access/modify."""
    for pattern in RESTRICTED_PATHS:
        if re.search(pattern, path, re.IGNORECASE):
            return False, f"🚫 BLOCKED: Protected system path"
    return True, "✅ Safe"


# ════════════════════════════════════════════════════════
# 📋 AUDIT LOG
# ════════════════════════════════════════════════════════

def log_action(action: str, details: str, blocked: bool = False):
    """Log every action to security audit file."""
    try:
        log = []
        if SECURITY_LOG.exists():
            try:
                log = json.loads(SECURITY_LOG.read_text(encoding='utf-8'))
            except Exception:
                log = []
        
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "details": details[:200],
            "blocked": blocked,
        }
        log.append(entry)
        
        # Keep last 500 entries
        log = log[-500:]
        
        SECURITY_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass  # Don't crash agent if logging fails


def get_recent_logs(count: int = 20) -> list[dict]:
    """Get recent security log entries."""
    try:
        if SECURITY_LOG.exists():
            log = json.loads(SECURITY_LOG.read_text(encoding='utf-8'))
            return log[-count:]
    except Exception:
        pass
    return []

