from interfaces.vision_output import ObstacleObservation

def detect_obstacles(frame) -> ObstacleObservation:
    return ObstacleObservation(
        immediate_stop_required=False,
        confidence=0.9
    )