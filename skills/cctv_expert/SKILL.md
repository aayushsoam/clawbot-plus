name: CCTV Security Expert
description: Connect to, monitor, and analyze CCTV/IP camera feeds via RTSP. Supports live viewing and AI-based person detection.

# Commands
- `python -m cctv_expert scan`: Scans the local network for common RTSP/ONVIF ports (554, 8000, 80, 8080).
- `python -m cctv_expert watch <rtsp_url>`: Opens a live window for the specified CCTV stream.
- `python -m cctv_expert register <alias> <rtsp_url>`: Saves a camera to the bot's known registry.
- `python -m cctv_expert list`: Displays all registered cameras.
- `python -m cctv_expert ai_monitor <alias>`: Monitors the feed in the background and uses ClawBot Vision to alert on human detection.

# Usage for AI
When the user asks "Show my front door camera" or "Is anyone at the gate?", use the `memory_search` to find the URL or `list` to see registered cameras, then use `watch` or `ai_monitor`.

# Technical Notes
- Requires `opencv-python` for GUI display.
- RTSP URLs usually follow: `rtsp://<user>:<pass>@<ip>:<port>/<stream_path>`.
