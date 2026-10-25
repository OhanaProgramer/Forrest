# file: /interfaces/vision_output.py
"""
VisionOutput Interface

v0 assumptions:
- Curb geometry is authoritative
- Paint markings are ignored
- Runner, traffic, obstacle observations may be present
  but are NOT used to assert validity
- overall_valid is driven by road geometry confidence only
"""
from  dataclasses import dataclass
from typing import Optional, List, Tuple

from dataclasses import dataclass

# A polyline is a list of (x, y) points in image coordinates
Polyline = List[Tuple[int, int]]

@dataclass
class RunnerObservation:
    visible: bool
    lateral_offset_m: float          # (-) left, (+) right
    forward_distance_m: float        # ahead distance
    heading_offset_deg: float        # runner heading relative to robot
    confidence: float                # 0.0..1.0

@dataclass
class RoadObservation:
    visible: bool
    left_boundary_m: float           # drivable/shoulder boundary left
    right_boundary_m: float          # drivable/shoulder boundary right
    corridor_heading_deg: float      # corridor direction relative to robot
    confidence: float                # 0.0..1.0

@dataclass
class ObstacleObservation:
    immediate_stop_required: bool
    confidence: float                # 0.0..1.0

@dataclass
class TrafficObservation:
    veto: bool                       # True => STOP now (traffic hazard)
    intrusion_risk: float            # 0.0..1.0 (probability-like risk score)
    traffic_boundary_m: float        # distance to traffic boundary (e.g., lane edge)
    confidence: float                # 0.0..1.0

@dataclass
class VisionOutput:
    frame_id: int
    timestamp_s: float

    runner: RunnerObservation
    road: RoadObservation
    obstacle: ObstacleObservation
    traffic: TrafficObservation

    overall_valid: bool              # computed by vision core (nav enforces)