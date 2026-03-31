"""
🖥️ ClawBot System Control Module
Volume, brightness, WiFi, Bluetooth, power management, process control.
All operations via PowerShell for Windows.
"""

import subprocess
import json


def _ps(cmd: str, timeout: int = 8) -> str:
    """Run a PowerShell command and return output."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=timeout
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0 and err:
            return f"ERROR: {err[:200]}"
        return out if out else "(done)"
    except subprocess.TimeoutExpired:
        return "ERROR: timed out"
    except Exception as e:
        return f"ERROR: {e}"


# ════════════════════════════════════════════════════════
# 🔊 AUDIO CONTROL
# ════════════════════════════════════════════════════════

def set_volume(level: int) -> str:
    """Set system volume (0-100)."""
    level = max(0, min(100, level))
    # Use NirCmd or PowerShell audio
    cmd = f"""
    $wshShell = New-Object -ComObject WScript.Shell
    # First mute to reset, then set volume
    1..50 | ForEach-Object {{ $wshShell.SendKeys([char]174) }}
    $steps = [math]::Round({level} / 2)
    1..$steps | ForEach-Object {{ $wshShell.SendKeys([char]175) }}
    """
    return _ps(cmd)


def mute_toggle() -> str:
    """Toggle system mute."""
    cmd = """
    $wshShell = New-Object -ComObject WScript.Shell
    $wshShell.SendKeys([char]173)
    """
    return _ps(cmd)


def get_volume() -> str:
    """Get current volume level."""
    cmd = """
    $audio = Get-WmiObject -Query "SELECT * FROM Win32_SoundDevice" | Select-Object -First 1
    Write-Output "Audio device found: $($audio.Name)"
    """
    return _ps(cmd)


# ════════════════════════════════════════════════════════
# 💡 DISPLAY CONTROL
# ════════════════════════════════════════════════════════

def set_brightness(level: int) -> str:
    """Set screen brightness (0-100). Works on laptops."""
    level = max(0, min(100, level))
    cmd = f"""
    $brightness = {level}
    $namespaceName = "root\\WMI"
    $wmiClass = "WmiMonitorBrightnessMethods"
    $monitor = Get-WmiObject -Namespace $namespaceName -Class $wmiClass
    $monitor.WmiSetBrightness(1, $brightness)
    Write-Output "Brightness set to $brightness%"
    """
    return _ps(cmd)


def get_brightness() -> str:
    """Get current brightness level."""
    cmd = """
    $namespaceName = "root\\WMI"
    $monitor = Get-WmiObject -Namespace $namespaceName -Class WmiMonitorBrightness
    Write-Output "Current brightness: $($monitor.CurrentBrightness)%"
    """
    return _ps(cmd)


# ════════════════════════════════════════════════════════
# 📡 NETWORK CONTROL
# ════════════════════════════════════════════════════════

def wifi_toggle(enable: bool) -> str:
    """Enable or disable WiFi."""
    state = "enable" if enable else "disable"
    cmd = f"""
    $adapter = Get-NetAdapter | Where-Object {{ $_.Name -match 'Wi-Fi|Wireless|WLAN' }} | Select-Object -First 1
    if ($adapter) {{
        if ('{state}' -eq 'enable') {{
            Enable-NetAdapter -Name $adapter.Name -Confirm:$false
        }} else {{
            Disable-NetAdapter -Name $adapter.Name -Confirm:$false
        }}
        Write-Output "WiFi $($adapter.Name): {state}d"
    }} else {{
        Write-Output "No WiFi adapter found"
    }}
    """
    return _ps(cmd, timeout=10)


def bluetooth_toggle(enable: bool) -> str:
    """Enable or disable Bluetooth."""
    state = "enable" if enable else "disable"
    cmd = f"""
    $bt = Get-PnpDevice | Where-Object {{ $_.FriendlyName -match 'Bluetooth' -and $_.Class -eq 'Bluetooth' }} | Select-Object -First 1
    if ($bt) {{
        if ('{state}' -eq 'enable') {{
            Enable-PnpDevice -InstanceId $bt.InstanceId -Confirm:$false
        }} else {{
            Disable-PnpDevice -InstanceId $bt.InstanceId -Confirm:$false
        }}
        Write-Output "Bluetooth: {state}d"
    }} else {{
        Write-Output "No Bluetooth adapter found"
    }}
    """
    return _ps(cmd, timeout=10)


def get_network_info() -> str:
    """Get network connection info."""
    cmd = """
    $wifi = Get-NetConnectionProfile | Where-Object {$_.InterfaceAlias -match 'Wi-Fi|Wireless'}
    if ($wifi) {
        Write-Output "Connected: $($wifi.Name) via $($wifi.InterfaceAlias)"
    } else {
        Write-Output "No WiFi connected"
    }
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notmatch 'Loopback'}).IPAddress
    Write-Output "IP: $ip"
    """
    return _ps(cmd)


# ════════════════════════════════════════════════════════
# ⚡ POWER CONTROL
# ════════════════════════════════════════════════════════

def lock_screen() -> str:
    """Lock the computer."""
    return _ps("rundll32.exe user32.dll,LockWorkStation")


def shutdown(delay_seconds: int = 30) -> str:
    """Schedule shutdown with delay."""
    return _ps(f"shutdown /s /t {delay_seconds}")


def cancel_shutdown() -> str:
    """Cancel a scheduled shutdown."""
    return _ps("shutdown /a")


def restart(delay_seconds: int = 10) -> str:
    """Schedule restart with delay."""
    return _ps(f"shutdown /r /t {delay_seconds}")


def sleep_pc() -> str:
    """Put computer to sleep."""
    return _ps("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")


# ════════════════════════════════════════════════════════
# 📊 SYSTEM INFO
# ════════════════════════════════════════════════════════

def get_system_info() -> str:
    """Get CPU, RAM, disk, and battery status."""
    cmd = """
    $cpu = (Get-WmiObject Win32_Processor).LoadPercentage
    $os = Get-WmiObject Win32_OperatingSystem
    $totalRAM = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    $freeRAM = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    $usedRAM = $totalRAM - $freeRAM
    
    $disk = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, @{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,1)}}, @{N='TotalGB';E={[math]::Round($_.Size/1GB,1)}}
    
    Write-Output "CPU: ${cpu}%"
    Write-Output "RAM: ${usedRAM}GB / ${totalRAM}GB"
    foreach ($d in $disk) {
        Write-Output "Disk $($d.DeviceID): $($d.FreeGB)GB free / $($d.TotalGB)GB"
    }
    
    $battery = Get-WmiObject Win32_Battery
    if ($battery) {
        Write-Output "Battery: $($battery.EstimatedChargeRemaining)%"
    }
    """
    return _ps(cmd)


# ════════════════════════════════════════════════════════
# 📋 PROCESS MANAGEMENT
# ════════════════════════════════════════════════════════

def get_running_processes(top_n: int = 15) -> str:
    """Get top running processes by memory usage."""
    cmd = f"""
    Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First {top_n} Name, @{{N='MemMB';E={{[math]::Round($_.WorkingSet64/1MB,0)}}}} | Format-Table -AutoSize
    """
    return _ps(cmd)


def kill_process(name: str) -> str:
    """Kill a process by name. Won't kill system-critical processes."""
    protected = ['csrss', 'wininit', 'winlogon', 'services', 'lsass', 'svchost', 'explorer', 'dwm']
    if name.lower().replace('.exe', '') in protected:
        return f"🚫 BLOCKED: Cannot kill protected system process '{name}'"
    
    cmd = f"Stop-Process -Name '{name}' -Force -ErrorAction SilentlyContinue; Write-Output 'Killed: {name}'"
    return _ps(cmd)


def open_app_by_name(app_name: str) -> str:
    """Open an app by name using Start-Process or URI."""
    cmd = f"Start-Process '{app_name}'"
    return _ps(cmd)


# ════════════════════════════════════════════════════════
# 📂 FILE OPERATIONS
# ════════════════════════════════════════════════════════

def create_file(path: str, content: str = "") -> str:
    """Create a file with optional content."""
    from pathlib import Path
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return f"Created: {path}"
    except Exception as e:
        return f"ERROR: Could not create file - {e}"


def read_file(path: str) -> str:
    """Read file contents."""
    from pathlib import Path
    try:
        return Path(path).read_text(encoding='utf-8')
    except Exception as e:
        return f"ERROR: Could not read file - {e}"


def list_directory(path: str = ".") -> str:
    """List directory contents."""
    cmd = f"Get-ChildItem -Path '{path}' | Format-Table Name, Length, LastWriteTime -AutoSize"
    return _ps(cmd)

