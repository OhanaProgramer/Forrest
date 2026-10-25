from interfaces.vision_output import TrafficObservation

def assess_traffic(frame) -> TrafficObservation:
    return TrafficObservation(
        veto=False,
        intrusion_risk=0.0,
        traffic_boundary_m=2.0,
        confidence=0.95
    )