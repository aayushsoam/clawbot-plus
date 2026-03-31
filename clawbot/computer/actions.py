"""
🎯 ClawBot Computer Agent — Reliable Action Helpers
Robust click, type, and focus functions for Windows OS automation.
Uses clipboard paste instead of pyautogui.write() for much better reliability.
"""

import time
import pyautogui
import pyperclip

pyautogui.PAUSE = 0.02
pyautogui.MINIMUM_DURATION = 0

# ════════════════════════════════════════════════════════
# 🖱️ RELIABLE CLICK
# ════════════════════════════════════════════════════════

def reliable_click(x: int, y: int, click_type: str = "click", retries: int = 2) -> bool:
    """
    Click at (x, y) with verification and retry.
    
    Args:
        x, y: Screen coordinates
        click_type: "click", "double_click", or "right_click"
        retries: Number of retry attempts
    
    Returns:
        True if click was performed successfully
    """
    for attempt in range(1, retries + 1):
        try:
            # Move to position instantly
            pyautogui.moveTo(x, y, duration=0)
            
            # Verify cursor actually reached the target (within tolerance)
            actual_x, actual_y = pyautogui.position()
            if abs(actual_x - x) > 5 or abs(actual_y - y) > 5:
                # Cursor didn't reach — try direct move
                pyautogui.moveTo(x, y, duration=0)
            
            # Perform the click
            if click_type == "click":
                pyautogui.click()
            elif click_type == "double_click":
                pyautogui.doubleClick()
            elif click_type == "right_click":
                pyautogui.rightClick()
            
            time.sleep(0.1)  # Let the app register the click
            return True
            
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5)
                continue
            return False
    
    return False


# ════════════════════════════════════════════════════════
# ⌨️ RELIABLE TYPE — Clipboard Paste Method
# ════════════════════════════════════════════════════════

def reliable_type(text: str, use_clipboard: bool = True) -> bool:
    """
    Type text reliably using clipboard paste (Ctrl+V).
    
    This handles:
    - Unicode text (Hindi, Chinese, Arabic, etc.)
    - Special characters (@, #, $, emojis, etc.)  
    - Long text that pyautogui.write() would mess up
    - Apps that don't register pyautogui keystrokes
    
    Falls back to pyautogui.write() only for simple ASCII if clipboard fails.
    
    Args:
        text: The text to type
        use_clipboard: If True (default), use clipboard paste method
    
    Returns:
        True if text was typed successfully
    """
    if not text:
        return True
    
    if use_clipboard:
        try:
            # Save current clipboard content
            old_clipboard = ""
            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                pass
            
            # Put our text on clipboard
            pyperclip.copy(text)
            time.sleep(0.05)
            
            # Paste it (Ctrl+V)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.05)  # Let app process the paste
            
            # Restore old clipboard (optional, be nice)
            try:
                if old_clipboard:
                    time.sleep(0.1)
                    pyperclip.copy(old_clipboard)
            except Exception:
                pass
            
            return True
            
        except Exception:
            # Fall through to fallback method
            pass
    
    # Fallback: pyautogui.write() for simple ASCII
    try:
        # Check if text is pure ASCII
        if text.isascii():
            pyautogui.write(text, interval=0.04)
        else:
            # For non-ASCII, type char by char using typewrite where possible
            # and clipboard for non-ASCII chars
            for char in text:
                if char.isascii():
                    pyautogui.write(char, interval=0)
                else:
                    pyperclip.copy(char)
                    pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.02)
        
        time.sleep(0.1)
        return True
        
    except Exception:
        return False


# ════════════════════════════════════════════════════════
# 🪟 FOCUS HELPERS
# ════════════════════════════════════════════════════════

def ensure_window_focus(x: int = None, y: int = None) -> bool:
    """
    Ensure the target window is focused before performing actions.
    
    If coordinates are provided, clicks at that position to bring window to front.
    Otherwise, checks that a real window (not the IDE/terminal) is focused.
    
    Returns:
        True if focus was ensured
    """
    try:
        import win32gui
        import win32con
        
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            # No foreground window — click to focus
            if x is not None and y is not None:
                pyautogui.click(x, y)
                time.sleep(0.3)
            return True
        
        # Check if current foreground is a dev tool that might steal focus
        title = win32gui.GetWindowText(hwnd).lower()
        focus_stealers = ['visual studio code', 'code -', 'terminal', 'powershell', 
                          'cmd.exe', 'command prompt', 'windows terminal', 'gemini']
        
        is_stolen = any(stealer in title for stealer in focus_stealers)
        
        if is_stolen and x is not None and y is not None:
            # Focus was stolen by IDE/terminal — click the target coordinates
            # to bring the correct window back to front
            time.sleep(0.2)
            pyautogui.click(x, y)
            time.sleep(0.3)
        
        return True
        
    except ImportError:
        return True
    except Exception:
        return True


def bring_window_to_front(window_title_substring: str) -> bool:
    """
    Find a window by partial title and bring it to the foreground.
    
    Args:
        window_title_substring: Part of the window title to search for
        (e.g., "WhatsApp", "Chrome", "Notepad")
    
    Returns:
        True if window was found and brought to front
    """
    try:
        import win32gui
        import win32con
        
        target_hwnd = None
        search = window_title_substring.lower()
        
        def enum_callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if search in title:
                    result.append(hwnd)
        
        found = []
        win32gui.EnumWindows(enum_callback, found)
        
        if found:
            target_hwnd = found[0]
            # Restore if minimized
            import win32api
            placement = win32gui.GetWindowPlacement(target_hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
            
            # Bring to front
            try:
                win32gui.SetForegroundWindow(target_hwnd)
            except Exception:
                # SetForegroundWindow can fail if we don't have focus
                # Use Alt trick to work around Windows restriction
                pyautogui.press('alt')
                time.sleep(0.1)
                win32gui.SetForegroundWindow(target_hwnd)
            
            time.sleep(0.3)
            return True
        
        return False
        
    except ImportError:
        return False
    except Exception:
        return False


def get_active_window_info() -> dict:
    """Get info about the currently active window."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        return {
            "hwnd": hwnd,
            "title": title,
            "left": rect[0],
            "top": rect[1],
            "right": rect[2],
            "bottom": rect[3],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1],
        }
    except Exception:
        return {"hwnd": 0, "title": "Unknown", "left": 0, "top": 0, "right": 0, "bottom": 0}


# ════════════════════════════════════════════════════════
# 🔄 SMART WAIT
# ════════════════════════════════════════════════════════

def smart_wait(action_type: str):
    """
    Wait an appropriate amount of time based on the action type.
    Different actions need different settle times.
    """
    waits = {
        "click":        0.1,
        "double_click": 0.2,
        "right_click":  0.2,
        "type":         0.1,
        "press":        0.1,
        "hotkey":       0.2,
        "shell":        0.5,
        "scroll":       0.1,
    }
    time.sleep(waits.get(action_type, 0.1))


# ════════════════════════════════════════════════════════
# 🖱️ DRAG AND DROP
# ════════════════════════════════════════════════════════

def drag_and_drop(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> bool:
    """
    Drag from (x1, y1) to (x2, y2).
    
    Useful for moving files, resizing windows, rearranging items.
    """
    try:
        pyautogui.moveTo(x1, y1, duration=0.2)
        time.sleep(0.1)
        pyautogui.mouseDown()
        time.sleep(0.1)
        pyautogui.moveTo(x2, y2, duration=duration)
        time.sleep(0.1)
        pyautogui.mouseUp()
        time.sleep(0.2)
        return True
    except Exception:
        pyautogui.mouseUp()  # Safety: release mouse
        return False


# ════════════════════════════════════════════════════════
# 📋 CLIPBOARD HELPERS
# ════════════════════════════════════════════════════════

def select_all_and_copy() -> str:
    """Select all text (Ctrl+A) and copy (Ctrl+C), return clipboard content."""
    try:
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.2)
        return pyperclip.paste()
    except Exception:
        return ""


def copy_selected() -> str:
    """Copy currently selected text and return it."""
    try:
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.2)
        return pyperclip.paste()
    except Exception:
        return ""


def paste_text(text: str) -> bool:
    """Put text on clipboard and paste it."""
    return reliable_type(text, use_clipboard=True)

