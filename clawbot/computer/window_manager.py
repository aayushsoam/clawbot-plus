"""
🪟 ClawBot Window Manager Module
Control windows — focus, minimize, maximize, snap, resize, move, close.
Uses win32gui for direct Windows API access.
"""

import time
import pyautogui


# ════════════════════════════════════════════════════════
# 📋 WINDOW LISTING
# ════════════════════════════════════════════════════════

def list_windows() -> list[dict]:
    """Get all visible windows with their titles, positions, and sizes."""
    try:
        import win32gui
        
        windows = []
        
        def enum_callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                title = win32gui.GetWindowText(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                # Skip tiny/invisible windows
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if w > 50 and h > 50 and title.strip():
                    result.append({
                        "hwnd": hwnd,
                        "title": title,
                        "x": rect[0], "y": rect[1],
                        "width": w, "height": h,
                    })
        
        win32gui.EnumWindows(enum_callback, windows)
        return windows
    except Exception as e:
        return [{"error": str(e)}]


def find_window(title_substring: str) -> int | None:
    """Find a window handle by partial title match."""
    try:
        import win32gui
        
        search = title_substring.lower()
        found = []
        
        def enum_callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if search in title:
                    result.append(hwnd)
        
        win32gui.EnumWindows(enum_callback, found)
        return found[0] if found else None
    except Exception:
        return None


# ════════════════════════════════════════════════════════
# 🎯 WINDOW FOCUS
# ════════════════════════════════════════════════════════

def focus_window(title: str) -> str:
    """Bring a window to the foreground by title."""
    try:
        import win32gui
        import win32con
        
        hwnd = find_window(title)
        if not hwnd:
            return f"❌ Window '{title}' not found"
        
        # Restore if minimized
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
        
        # Bring to front
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pyautogui.press('alt')
            time.sleep(0.1)
            win32gui.SetForegroundWindow(hwnd)
        
        time.sleep(0.3)
        return f"✅ Focused: {win32gui.GetWindowText(hwnd)}"
    except Exception as e:
        return f"❌ Focus failed: {e}"


# ════════════════════════════════════════════════════════
# 📐 WINDOW MANIPULATION
# ════════════════════════════════════════════════════════

def minimize_window(title: str) -> str:
    """Minimize a window."""
    try:
        import win32gui
        import win32con
        
        hwnd = find_window(title)
        if not hwnd:
            return f"❌ Window '{title}' not found"
        
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return f"✅ Minimized: {win32gui.GetWindowText(hwnd)}"
    except Exception as e:
        return f"❌ Minimize failed: {e}"


def maximize_window(title: str) -> str:
    """Maximize a window."""
    try:
        import win32gui
        import win32con
        
        hwnd = find_window(title)
        if not hwnd:
            return f"❌ Window '{title}' not found"
        
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return f"✅ Maximized: {win32gui.GetWindowText(hwnd)}"
    except Exception as e:
        return f"❌ Maximize failed: {e}"


def close_window(title: str) -> str:
    """Close a window gracefully."""
    try:
        import win32gui
        import win32con
        
        hwnd = find_window(title)
        if not hwnd:
            return f"❌ Window '{title}' not found"
        
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        time.sleep(0.5)
        return f"✅ Closed: {title}"
    except Exception as e:
        return f"❌ Close failed: {e}"


def resize_window(title: str, width: int, height: int) -> str:
    """Resize a window to specific dimensions."""
    try:
        import win32gui
        import win32con
        
        hwnd = find_window(title)
        if not hwnd:
            return f"❌ Window '{title}' not found"
        
        rect = win32gui.GetWindowRect(hwnd)
        x, y = rect[0], rect[1]
        
        # Restore from maximize first
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)
        
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return f"✅ Resized '{title}' to {width}x{height}"
    except Exception as e:
        return f"❌ Resize failed: {e}"


def move_window(title: str, x: int, y: int) -> str:
    """Move a window to specific screen coordinates."""
    try:
        import win32gui
        import win32con
        
        hwnd = find_window(title)
        if not hwnd:
            return f"❌ Window '{title}' not found"
        
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)
        
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
        return f"✅ Moved '{title}' to ({x}, {y})"
    except Exception as e:
        return f"❌ Move failed: {e}"


def snap_window(title: str, position: str) -> str:
    """
    Snap a window to a screen position.
    Positions: 'left', 'right', 'top-left', 'top-right', 'bottom-left', 'bottom-right', 'full'
    """
    try:
        import win32gui
        import win32con
        
        hwnd = find_window(title)
        if not hwnd:
            return f"❌ Window '{title}' not found"
        
        # Get screen dimensions
        sw, sh = pyautogui.size()
        half_w, half_h = sw // 2, sh // 2
        
        # Restore first
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)
        
        positions = {
            'left':         (0, 0, half_w, sh),
            'right':        (half_w, 0, half_w, sh),
            'top-left':     (0, 0, half_w, half_h),
            'top-right':    (half_w, 0, half_w, half_h),
            'bottom-left':  (0, half_h, half_w, half_h),
            'bottom-right': (half_w, half_h, half_w, half_h),
            'full':         (0, 0, sw, sh),
        }
        
        if position not in positions:
            return f"❌ Unknown position '{position}'. Use: {', '.join(positions.keys())}"
        
        x, y, w, h = positions[position]
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
        return f"✅ Snapped '{title}' to {position}"
    except Exception as e:
        return f"❌ Snap failed: {e}"

