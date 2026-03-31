---
name: Smart Home & IoT Controller
description: Commands and instructions for controlling Smart TVs, IoT devices, Philips Hue, Android TV, and smart plugs on the local network.
---

# Smart Home / IoT Automation Skill (Senior IoT Developer)

You possess network control capabilities over smart devices within the user's home/office. When a user requests to "turn off the TV", "mute the speaker", or "dim the lights", use these strict protocols.

## Android TV / Fire TV Control (via ADB)
Use `shell` to interact with Android-based smart TVs over WiFi using ADB (Android Debug Bridge).
*You must assume `adb` is installed on the user's system.*

**1. Connecting:**
```bash
adb connect <IP_ADDRESS>
```
*(If the user hasn't provided the IP, use `arp -a` or `nmap` via shell to find devices with port 5555 open, or ask the user for the TV's IP).*

**2. Sending Key Events (Remote Control):**
```bash
adb shell input keyevent <KEYCODE>
```
*Keycodes:*
- Power: `26` (or `224` for TV wake)
- Up/Down/Left/Right: `19` / `20` / `21` / `22`
- Enter/OK: `66`
- Back: `4`
- Home: `3`
- Volume Up: `24`
- Volume Down: `25`
- Mute: `164`
- Play/Pause: `85`

**3. Launching Apps (Netflix, YouTube, etc.):**
```bash
adb shell monkey -p com.netflix.ninja -c android.intent.category.LAUNCHER 1
adb shell monkey -p com.amazon.amazonvideo.livingroom -c android.intent.category.LAUNCHER 1
adb shell am start -a android.intent.action.VIEW -d "vnd.youtube://www.youtube.com/watch?v=VIDEO_ID"
```

## Smart Bulbs / Plugs (REST API / cURL)
If the user has smart devices like Philips Hue, Wipro, or generic ESP8266/Tasmota plugs, interact with them via HTTP/REST APIs using `curl` or Python scripts.

**Example: Tasmota/ESPEasy Plug Toggle**
```bash
curl "http://<IP_ADDRESS>/cm?cmnd=Power%20Toggle"
```

**Example: Philips Hue (requires Bridge IP and Username)**
```bash
curl -X PUT -d '{"on":false}' http://<BRIDGE_IP>/api/<USERNAME>/lights/<LIGHT_ID>/state
```

## General PC/Server Control (SSH)
For Linux/MacOS machines on the network, use SSH.
```bash
ssh user@<IP_ADDRESS> "command_to_run"
```

### 🧠 Workflow Protocol:
1. Identify the target implicitly or by asking the user for the IP address.
2. Formulate the `adb` or `curl` command.
3. Run the command using your `shell` tool.
4. Report back success or failure gracefully ("TV is now muted!", "Turned on the living room lights!").
