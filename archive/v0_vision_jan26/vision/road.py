#from interfaces.vision_output import RoadObservation

def road_confidence_stub(frame):
    """
    Learning stub:
    Pretend we understand the road.
    """
    return 0.9

# def detect_road(frame) -> RoadObservation:
#     return RoadObservation(
#         visible=True,
#         left_boundary_m=-1.5,
#         right_boundary_m=1.5,
#         corridor_heading_deg=0.0,
#         confidence=0.95
#     )

# def detect_road(frame) -> RoadObservation:
#     """
#     v0 stub:
#     - Assumes curb geometry is known
#     - Returns high confidence for pipeline testing
#     """