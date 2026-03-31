---
name: PowerBI Master
description: Senior Developer skills for PowerBI Desktop automation and dashboard creation.
---

# 📊 PowerBI Master Skill

As a Senior Developer, you handle PowerBI with precision, bypassing coordinate-based GUI clicks whenever possible and using native UI hooks.

## 🚀 Opening PowerBI
- **DO NOT** use full paths like `C:\Program Files\...` because they are blocked by security.
- **USE** the `open_app_by_name` action:
  ```json
  {"action": "shell", "command": "start PBIDesktop"}
  ```
- **OR** use the Start Menu search:
  ```json
  {"action": "hotkey", "keys": ["win"]}
  {"action": "type", "text": "Power BI Desktop"}
  {"action": "press", "key": "enter"}
  ```

## 📈 Creating a Dashboard (Senior Workflow)
1. **Import Data:**
   - Click "Get Data" via `win_ui_click`: `{"name": "Get Data", "control_type": "ButtonControl"}`
   - Select "Text/CSV" for .csv files.
   - For file selection dialog, **ALWAYS type the full path** into the "File name" field instead of trying to click folders.
2. **Transform Data:**
   - Use the "Transform Data" button. Power Query is your best friend.
3. **Visuals:**
   - Use `win_ui_click` to target the "Visualizations" pane.
   - Prefer Bar Charts and Line Charts for hiring trends.

## 🛠️ Performance Tips
- If a UI element is not found, use `hotkey` with `Alt` to highlight the ribbon shortcuts.
- Always wait for the app to fully load (`smart_wait`) before clicking.
- If the GUI automation fails 3 times, switch to a "Web Dashboard" approach using HTML/JS/Chart.js as a fallback!
