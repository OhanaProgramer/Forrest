"""Hailo NMS output -> Detection objects (no hardware)."""

from forrest.sensing.detections import COCO_LABELS, parse_nms


def _empty():
    return [[] for _ in COCO_LABELS]


def test_parse_keeps_above_threshold_sorted_by_score():
    out = _empty()
    out[0] = [[0.1, 0.2, 0.9, 0.6, 0.92]]          # person
    out[33] = [[0.05, 0.9, 0.1, 0.95, 0.46]]       # kite, below 0.5
    out[56] = [[0.5, 0.1, 0.8, 0.3, 0.61]]         # chair
    dets = parse_nms(out, threshold=0.5)
    assert [d.label for d in dets] == ["person", "chair"]
    p = dets[0]
    # rows are [y0, x0, y1, x1, score]; Detection stores x0, y0, x1, y1
    assert (p.x0, p.y0, p.x1, p.y1) == (0.2, 0.1, 0.6, 0.9)


def test_parse_clamps_boxes_and_records():
    out = _empty()
    out[2] = [[-0.1, -0.2, 1.3, 1.1, 0.8]]
    (d,) = parse_nms(out)
    assert (d.x0, d.y0, d.x1, d.y1) == (0.0, 0.0, 1.0, 1.0)
    assert d.as_record() == {"label": "car", "score": 0.8, "box": [0.0, 0.0, 1.0, 1.0]}


def test_parse_empty():
    assert parse_nms(_empty()) == []
