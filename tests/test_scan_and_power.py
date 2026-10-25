from forrest.health.pi_power import parse_temp, parse_throttled
from forrest.sensing.scan import ReplaySource, Scan, ScanPoint, sector_nearest, write_recording


def test_sector_wraps_past_360():
    scan = Scan(0, [ScanPoint(350, 2.0), ScanPoint(10, 1.0), ScanPoint(90, 0.5)])
    assert [p.angle_deg for p in scan.in_sector(337.5, 22.5)] == [350, 10]
    assert scan.nearest().distance_m == 0.5
    near = sector_nearest(scan)
    assert near["front"] == 1.0 and near["right"] == 0.5 and near["back"] is None


def test_record_and_replay(tmp_path):
    scans = [Scan(100.0 + i * 0.1, [ScanPoint(i * 10.0, 1.0 + i, 30)]) for i in range(5)]
    path = tmp_path / "rec.jsonl"
    assert write_recording(scans, path) == 5
    back = list(ReplaySource(path, realtime=False).iter_scans())
    assert [s.points[0].distance_m for s in back] == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_throttled_parsing():
    clean = parse_throttled("throttled=0x0\n")
    assert clean.ok and not clean.undervoltage_seen
    bad = parse_throttled("throttled=0x50005\n")
    assert bad.undervoltage_seen
    assert "under-voltage has occurred" in bad.problems
    assert parse_temp("temp=48.3'C\n") == 48.3
