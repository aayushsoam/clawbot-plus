name: capcut-automation
description: "Use this skill to automate CapCut Desktop for video editing and typography generation."

# CapCut Desktop Automation Blueprint

When the user asks to generate a typography video or edit in CapCut, YOU MUST follow this strict UI clicking sequence. Do not guess. CapCut is a dark-mode desktop app. 
Ensure you use your standard Computer Control actions (`shell`, `click`, `type`, `wait`, `take_screenshot`).

## EXECUTION WORKFLOW:

### Phase 1: Open Application
1. Action: `shell`, Command: `start capcut:` (or navigate to Start Menu and type "CapCut" and press enter).
2. Action: `wait`, Seconds: `10`
3. Action: `take_screenshot` to confirm "New Project" screen is visible.

### Phase 2: Create Project & Import
1. Locate the **"New Project"** button (large blue button near top-center) and `click` it.
2. Action: `wait`, Seconds: `5`
3. Identify the **"Import"** button (top-left media pool area, usually a plus icon `+` or text) and `click` it.
4. Action: `wait`, Seconds: `2`
5. The Windows File Explorer dialog will open. Use `type` to enter the exact path of the generated audio or media file (e.g. `C:\Users\thaku\OneDrive\Desktop\my project\browser\make_pro_video.mp4` or your audio file) and `press` "enter".
6. Action: `wait`, Seconds: `2`
7. Click the imported media in the top-left pool and `drag` it down to the timeline at the bottom of the screen.

### Phase 3: Auto-Captions (The Typography Secret)
1. In the very top-left menu bar, find and `click` the **"Text"** tab.
2. In the secondary left panel that appears, find and `click` on **"Auto Captions"**.
3. Set the language to "English" or "Hindi" by clicking the dropdown if necessary.
4. Click the blue **"Create"** or **"Generate"** button.
5. Action: `wait`, Seconds: `10` (Wait for CapCut AI to analyze the audio and generate text clips on the timeline).
6. Action: `take_screenshot` to verify captions exist.

### Phase 4: Apply Trending Bouncing Template
1. A caption clip will be automatically selected in the timeline.
2. Look at the right-side properties panel. `Click` on the **"Templates"** tab.
3. Locate the **"Trending"** or **"Word-by-word"** / **"Typography"** category.
4. `Click` on a bouncing yellow/white template (typically the first or second option).
5. The dynamic typography is now applied to the entire video!

### Phase 5: Export
1. `Click` the bright blue **"Export"** button in the extreme top-right corner of the capcut window.
2. `Click` the final **"Export"** confirm button in the dialog popup.
3. Action: `wait`, Seconds: `10`
4. Use `done` to tell the user the video is rendering in CapCut!
