import sys
import tkinter as tk
import time
import threading
import os
import psutil
import logging

# Log to a file to debug invisible process
log_file = os.path.join(os.path.expanduser("~"), ".clawbot_overlay_debug.log")
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s %(message)s')

logging.info(f"Overlay started with args: {sys.argv}")

def monitor_parent(ppid):
    """Exit if the parent process dies."""
    while True:
        try:
            # On Windows, ppid might be reused, but for a short session it's usually fine
            # or checks if the process is actually the same. 
            # A simpler way: if parent is gone, ppid will change to 1 or process not found
            p = psutil.Process(ppid)
            if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                logging.info(f"Parent {ppid} not running/zombie. Exiting.")
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            logging.info(f"Parent {ppid} not found/denied. Exiting.")
            break
        time.sleep(2)
    sys.exit(0)

def update_wave(label):
    waves = [
        " ▂▃▄▅", " ▃▄▅▆", " ▄▅▆▇", " ▅▆▇█", 
        " ▆▇█▇", " ▇█▇▆", " █▇▆▅", " ▇▆▅▄", 
        " ▆▅▄▃", " ▅▄▃▂"
    ]
    idx = 0
    while True:
        try:
            label.config(text=f"🎙️ Listening... {waves[idx % len(waves)]}")
            idx += 1
            time.sleep(0.1)
        except Exception:
            break

def main():
    root = tk.Tk()
    root.overrideredirect(True)  # Borderless window
    root.attributes("-topmost", True)  # Always on top
    
    # Try to make it somewhat transparent on Windows
    try:
        root.attributes("-alpha", 0.9)
    except Exception:
        pass
    
    # Dimensions and Position (Top center like Win+H)
    window_width = 220
    window_height = 45
    screen_width = root.winfo_screenwidth()
    x = (screen_width // 2) - (window_width // 2)
    y = 40  # 40px from top
    
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # Styling
    bg_color = "#1E1E1E"
    fg_color = "#00d4ff"
    
    root.configure(bg=bg_color)
    
    # Add a subtle border frame
    frame = tk.Frame(root, bg=bg_color, highlightbackground="#333333", highlightthickness=1)
    frame.pack(expand=True, fill="both")
    
    label = tk.Label(
        frame, 
        text="🎙️ Listening...", 
        bg=bg_color, 
        fg=fg_color, 
        font=("Segoe UI", 12, "bold")
    )
    label.pack(expand=True, fill="both", padx=10, pady=5)
    
    # Start the animation in a background thread
    t = threading.Thread(target=update_wave, args=(label,), daemon=True)
    t.start()
    
    # Start parent monitor if PID passed
    if len(sys.argv) > 1:
        try:
            ppid = int(sys.argv[1])
            tm = threading.Thread(target=monitor_parent, args=(ppid,), daemon=True)
            tm.start()
        except ValueError:
            pass

    # Add Right-Click to close
    def exit_now(event):
        root.destroy()
        sys.exit(0)
    
    root.bind("<Button-3>", exit_now) # Right click
    
    root.mainloop()

if __name__ == "__main__":
    main()
