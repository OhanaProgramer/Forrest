import time

from interfaces.vision_output import VisionOutput
from vision.runner import detect_runner
from vision.road import detect_road
from vision.traffic import assess_traffic
from vision.obstacle import detect_obstacles


RUNNER_CONF_MIN = 0.6
ROAD_CONF_MIN = 0.7
TRAFFIC_CONF_MIN = 0.7


class VisionCore:
    def __init__(self):
        self.frame_id = 0

    def process_frame(self, frame) -> VisionOutput:
        self.frame_id += 1
        timestamp = time.monotonic()

        runner = detect_runner(frame)
        road = detect_road(frame)
        traffic = assess_traffic(frame)
        obstacle = detect_obstacles(frame)

        overall_valid = (
            road.visible and road.confidence >= ROAD_CONF_MIN
        )

        return VisionOutput(
            frame_id=self.frame_id,
            timestamp_s=timestamp,
            runner=runner,
            road=road,
            obstacle=obstacle,
            traffic=traffic,
            overall_valid=overall_valid
        )