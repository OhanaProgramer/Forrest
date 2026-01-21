/vision/ — Seeing, Not Deciding

This folder answers:
“What do I observe, and how confident am I?”

• runner.py
    Runner detection logic (simple → ML later)
• road.py
    Road edge, lane, corridor detection

• confidence.py
    Rules like:
        •	visibility decay
        •	occlusion handling
        •	hysteresis

• vision_core.py
    Orchestrates:
        •	grabs a frame
        •	calls runner + road
        •	assembles one vision output

🚫 Vision never issues motor commands
🚫 Vision never decides “stop” or “go”


### “At time T, runner is 0.8m left, 4.2m ahead, heading +5°, confidence 0.76; road corridor valid, right edge at 1.1m, confidence 0.92.”

