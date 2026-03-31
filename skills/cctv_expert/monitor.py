import cv2
import sys
import os
import json
import socket
import time
import subprocess
from pathlib import Path

# --- Configuration ---
CONFIG_DIR = Path.home() / ".clawbot"
CONFIG_FILE = CONFIG_DIR / "cctv.json"

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except:
            return {"cameras": {}}
    return {"cameras": {}}

def save_config(config):
    CONFIG_DIR.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

# --- Actions ---

def scan_network():
    # Automatically find local IP subnet
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        base_ip = ".".join(local_ip.split(".")[:-1]) + "."
    except:
        base_ip = "192.168.1."
        
    print(f"🔍 Scanning subnet {base_ip}x for cameras (ports 554, 8000, 8080)...")
    found = []
    for i in range(1, 255):
        ip = base_ip + str(i)
        for port in [554, 8000, 8080]:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.05)
                if s.connect_ex((ip, port)) == 0:
                    print(f"✅ Found potential camera @ {ip}:{port}")
                    found.append(f"{ip}:{port}")
    if not found:
        print("❌ No cameras found via automatic scanning. Try adding manually.")

def register_camera(alias, url):
    config = load_config()
    config["cameras"][alias] = url
    save_config(config)
    print(f"✅ Camera '{alias}' registered at: {url}")

def list_cameras():
    config = load_config()
    if not config["cameras"]:
        print("📭 No cameras registered.")
        return
    print("🎬 REGISTERED CAMERAS:")
    for alias, url in config["cameras"].items():
        print(f"  • {alias}: {url}")

def watch_stream(url):
    print(f"🚀 Opening stream: {url}")
    # Try to use standard OpenCV first
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("❌ Failed to open stream via OpenCV. Trying VLC fallback...")
        try:
            subprocess.run(["vlc", url], check=False)
            return
        except:
            print("❌ VLC not found. Please ensure your RTSP URL is correct.")
            return

    # If OpenCV opens successfully (GUI supported)
    print("💡 Press 'q' to close the monitoring window.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Stream interrupted.")
            break
        cv2.imshow("ClawBot CCTV Monitor", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

def send_to_telegram(frame, caption="📸 CCTV Alert"):
    """Sends a frame to Telegram using environment variables."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    
    import requests
    _, img_encoded = cv2.imencode('.jpg', frame)
    files = {'photo': ('image.jpg', img_encoded.tobytes())}
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", 
                      data={'chat_id': chat_id, 'caption': caption}, 
                      files=files, timeout=10)
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def ai_monitor(alias):
    config = load_config()
    url = config["cameras"].get(alias)
    if not url:
        print(f"❌ Camera '{alias}' not found.")
        return
    
    print(f"👮 AI Security Monitor [ACTIVE] for '{alias}'")
    print("Analyzing stream for motion/human presence...")
    
    cap = cv2.VideoCapture(url)
    last_frame = None
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        # Simple Motion Detection Baseline
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if last_frame is None:
            last_frame = gray
            continue
            
        delta = cv2.absdiff(last_frame, gray)
        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        if cv2.countNonZero(thresh) > 5000: # Tune threshold
            # MOTION DETECTED
            timestamp = time.strftime('%H:%M:%S')
            print(f"⚠️ [{timestamp}] MOTION DETECTED! Sending to Telegram...")
            
            # Send to Telegram
            send_to_telegram(frame, caption=f"⚠️ MOTION DETECTED at {timestamp} on '{alias}'")
            
            # Save locally too
            cv2.imwrite("motion_alert.jpg", frame)
            time.sleep(10) # Cooldown to avoid spam
            
        last_frame = gray
        time.sleep(0.5) # Efficiency check

# --- PTZ Control (ONVIF) ---

class PTZController:
    def __init__(self, ip, user, password, port=8899):
        try:
            from onvif import ONVIFCamera
            self.mycam = ONVIFCamera(ip, port, user, password)
            self.media = self.mycam.create_media_service()
            self.ptz = self.mycam.create_ptz_service()
            self.profile = self.media.GetProfiles()[0]
            self.token = self.profile.token
            self.active = True
        except Exception as e:
            print(f"⚠️ PTZ Init failed: {e}")
            self.active = False

    def move(self, x, y, duration=0.5):
        if not self.active: return
        try:
            request = self.ptz.create_type('ContinuousMove')
            request.ProfileToken = self.token
            request.Velocity = {'PanTilt': {'x': x, 'y': y}}
            self.ptz.ContinuousMove(request)
            time.sleep(duration)
            self.ptz.Stop({'ProfileToken': self.token})
        except Exception as e:
            print(f"❌ PTZ error: {e}")

def move_camera(alias, direction):
    config = load_config()
    url = config["cameras"].get(alias)
    if not url: return "Camera not found"
    
    # Extract IP and credentials from URL
    # Format: rtsp://user:pass@ip:port/...
    try:
        parts = url.split("@")
        creds = parts[0].split("//")[1].split(":")
        ip = parts[1].split(":")[0]
        user, password = creds[0], creds[1]
        
        ptz = PTZController(ip, user, password)
        moves = {
            "left": (-0.2, 0), "right": (0.2, 0),
            "up": (0, 0.2), "down": (0, -0.2)
        }
        if direction in moves:
            ptz.move(*moves[direction])
            return f"✅ Moved {direction}"
    except Exception as e:
        return f"❌ Movement failed: {e}"

# --- Video & AI Analysis ---

def record_video_burst(url, duration=5, output_path="burst.mp4"):
    """Captures a short video clip from the RTSP stream."""
    cap = cv2.VideoCapture(url)
    if not cap.isOpened(): return None
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = 15 # Guessing for V380
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    start_time = time.time()
    while (time.time() - start_time) < duration:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame)
    
    cap.release()
    out.release()
    return output_path

async def analyze_scene(alias, llm=None):
    """Sends a frame to the AI for a situational report."""
    config = load_config()
    url = config["cameras"].get(alias)
    if not url: return "Camera not found."
    
    cap = cv2.VideoCapture(url)
    ret, frame = cap.read()
    cap.release()
    if not ret: return "Failed to capture frame."
    
    # Save temp frame
    temp_path = "temp_analyze.jpg"
    cv2.imwrite(temp_path, frame)
    
    try:
        from clawbot.computer.agent import _ask_llm, load_image_b64
        if llm is None:
            from clawbot.computer.telegram_bot import create_default_llm
            llm = create_default_llm()
            
        b64 = load_image_b64(temp_path)
        prompt = "Analyze this CCTV frame. Who is visible? Is there any security concern? Summarize concisely."
        report = await _ask_llm(llm, prompt, b64_img=b64)
        return report
    except Exception as e:
        return f"❌ AI Analysis error: {e}"

# --- CLI Entry ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m cctv_expert <command> [args]")
        sys.exit(1)
        
    cmd = sys.argv[1].lower()
    
    if cmd == "scan":
        scan_network()
    elif cmd == "register":
        register_camera(sys.argv[2], sys.argv[3])
    elif cmd == "list":
        list_cameras()
    elif cmd == "move":
        print(move_camera(sys.argv[2], sys.argv[3]))
    elif cmd == "watch":
        url = sys.argv[2]
        config = load_config()
        url = config["cameras"].get(url, url)
        watch_stream(url)
    elif cmd == "record":
        config = load_config()
        url = config["cameras"].get(sys.argv[2], sys.argv[2])
        path = record_video_burst(url)
        print(f"✅ Recorded: {path}")
    elif cmd == "ai_monitor":
        ai_monitor(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
