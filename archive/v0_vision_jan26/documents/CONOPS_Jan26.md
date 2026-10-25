CONOPS v0.9 Final

1) Mission

    ForestBot trails a human runner on the same side of the road, maintaining:
        •	Follow distance: default ~ 3 m (10 ft) behind
        •	Lateral behavior: shoulder/road-edge biased, never drifting toward traffic

2) Absolute Safety Vetoes (Hard Stop)

    ForestBot must STOP immediately if any of these are true:
        1.	Runner confidence below threshold (cannot reliably localize runner)
        2.	Road/shoulder confidence below threshold (cannot reliably localize corridor/edge)
        3.	Obstacle veto triggers (immediate hazard)
        4.	Traffic hazard veto triggers:
        •	Any commanded motion would move the robot into traffic space
        •	Any perception indicates the robot is at risk of traffic-lane intrusion
        •	Any ambiguity about where the traffic boundary is

    Rule of operation: “Error to the side of the road always.”
    If the “safe shoulder region” is uncertain → STOP.

3) Allowed Autonomous Behavior (No Permission Needed)

    Only when all vetoes are clear and confidences are high:
        •	Maintain distance and offset
        •	Follow gentle curvature
        •	Minor debris avoidance only if it remains inside shoulder-safe region
        •	Never pass the runner; never go ahead of the runner

4) Significant Maneuvers (Permissioned Only)

    These require explicit runner intent (gesture/button/etc.) plus high-confidence safety checks:
        •	Crossing the road
        •	90° turn / intersection turn (especially if runner temporarily occludes)
        •	Detour that breaks line-of-sight or approaches traffic boundary

        Default behavior without permission: STOP → REQUEST → HOLD.

5) Modes (Minimal Set)
	•	FOLLOW: normal trailing
	•	HOLD: stopped, reacquiring runner/road
	•	REQUEST: stopped, waiting for explicit permission for a significant maneuver
	•	STOP (hard): emergency stop due to veto (obstacle/traffic/invalid corridor)

6) Future Safety Sensors (Explicitly Planned)
	•	Optional second camera for traffic observation (rear/side)
	•	Dedicated “traffic boundary” sensing (future) is compatible with this CONOPS because it plugs into the traffic hazard veto.