"""The `forrest` command: bench tools for B1 (LIDAR) and B2 (power soak).

    forrest lidar check  [--port P]             # info, health, live 8-sector view
    forrest lidar record OUT.jsonl [--seconds N]
    forrest lidar view   [--replay FILE.jsonl]  # plot (needs the [viz] extra)
    forrest soak         [--minutes 60]         # B2: LIDAR spinning + power log
    forrest power                               # one-shot Pi power/heat check
    forrest view [--threshold 0.5]              # desktop window: live view + boxes
    forrest dash [--host H] [--port 8090] [--camera]      # dashboard web server
    forrest pico check [--port P] [--polls 5]   # is the Pico answering? (read-only)
    forrest pico monitor [--every 1]            # forrest-pico service: state file + daily log
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from forrest.health.pi_power import read_temp_c, read_throttled
from forrest.sensing.scan import ReplaySource, Scan, sector_nearest

DEFAULT_PORT = "/dev/ttyUSB0"


def _open_lidar(port: str):
    from forrest.drivers.lidar_c1 import LidarC1
    return LidarC1(port)


def _fmt(d):
    return "  --  " if d is None else f"{d:5.2f}m"


# ---------------------------------------------------------------------------
# lidar check  (B1: "walk around it and see yourself as a moving blob")
# ---------------------------------------------------------------------------

def cmd_lidar_check(args) -> int:
    with _open_lidar(args.port) as lidar:
        info = lidar.info()
        health = lidar.health()
        print(f"RPLIDAR model {info.model}  firmware {info.firmware}  "
              f"hardware {info.hardware}  serial {info.serial}")
        print(f"health: {health.status} (error code {health.error_code})")
        if health.status != "good":
            print("LIDAR reports a problem; try `forrest lidar check` again after a power cycle.")
            return 1

        print("\nNearest object per sector (Ctrl-C to stop):")
        last = time.time()
        rate = 0.0
        for scan in lidar.iter_scans():
            now = time.time()
            rate = 0.8 * rate + 0.2 * (1.0 / max(now - last, 1e-3))
            last = now
            near = sector_nearest(scan)
            line = " ".join(f"{k}:{_fmt(v)}" for k, v in near.items())
            sys.stdout.write(f"\r{rate:4.1f} Hz {len(scan.points):4d} pts | {line}   ")
            sys.stdout.flush()
    return 0


# ---------------------------------------------------------------------------
# lidar record  (capture real scans to replay on the Mac)
# ---------------------------------------------------------------------------

def cmd_lidar_record(args) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    end = time.time() + args.seconds
    with _open_lidar(args.port) as lidar, out.open("w") as f:
        for scan in lidar.iter_scans():
            f.write(scan.to_json() + "\n")
            n += 1
            if time.time() >= end:
                break
    print(f"wrote {n} scans to {out}")
    return 0


# ---------------------------------------------------------------------------
# lidar view  (live on the Pi desktop, or replay anywhere)
# ---------------------------------------------------------------------------

def cmd_lidar_view(args) -> int:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Plotting needs matplotlib: pip install -e '.[viz]'")
        return 1
    import math

    source = ReplaySource(args.replay, loop=True) if args.replay else None
    ctx = _open_lidar(args.port) if source is None else None
    scans = (ctx.iter_scans() if ctx else source.iter_scans())

    plt.ion()
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)  # clockwise, like the LIDAR
    ax.set_rmax(args.range)
    dots = ax.scatter([], [], s=4)
    try:
        for scan in scans:
            if not plt.fignum_exists(fig.number):
                break
            dots.set_offsets([[math.radians(p.angle_deg), p.distance_m] for p in scan.points]
                             or [[0, 0]])
            ax.set_title(f"{len(scan.points)} points")
            plt.pause(0.001)
    finally:
        if ctx:
            ctx.close()
    return 0


# ---------------------------------------------------------------------------
# soak  (B2: one hour on the battery with the LIDAR spinning)
# ---------------------------------------------------------------------------

def cmd_soak(args) -> int:
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    end = time.time() + args.minutes * 60
    next_log = 0.0
    scans = 0
    worst_temp = 0.0
    first = read_throttled()
    if first is None:
        print("Not on a Pi (no vcgencmd); the soak test needs the Pi.")
        return 1
    if not first.ok:
        print(f"Note: the Pi already shows {first.problems} since boot. "
              "Reboot on the battery before the soak for a clean result.")

    with _open_lidar(args.port) as lidar, log_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["elapsed_s", "temp_c", "throttled_hex", "scans", "problems"])
        start = time.time()
        for _scan in lidar.iter_scans():
            scans += 1
            now = time.time()
            if now >= next_log:
                t = read_throttled()
                temp = read_temp_c() or 0.0
                worst_temp = max(worst_temp, temp)
                w.writerow([int(now - start), temp, hex(t.raw), scans, "; ".join(t.problems)])
                f.flush()
                print(f"{int(now - start):5d}s  {temp:4.1f}C  {hex(t.raw)}  scans={scans}")
                next_log = now + args.every
            if now >= end:
                break

    final = read_throttled()
    print("\n=== B2 soak result ===")
    print(f"duration: {args.minutes} min   scans: {scans}   hottest: {worst_temp:.1f} C")
    if final.undervoltage_seen:
        print("FAIL: the Pi saw under-voltage. Check the buck converter, wiring and battery.")
        return 2
    if final.ok:
        print("PASS: no power or heat warnings.")
    else:
        print(f"PASS on power, but note: {final.problems}")
    print(f"log: {log_path}")
    return 0


def cmd_power(args) -> int:
    t = read_throttled()
    if t is None:
        print("Not on a Pi (no vcgencmd).")
        return 1
    temp = read_temp_c()
    print(f"temperature: {temp} C")
    print(f"throttled: {hex(t.raw)} -> {'all clear' if t.ok else '; '.join(t.problems)}")
    return 0 if not t.undervoltage_seen else 2


# ---------------------------------------------------------------------------
# dash  (dashboard web server; owns the camera + Hailo while it runs)
# ---------------------------------------------------------------------------

def cmd_view(args) -> int:
    """Desktop window on the Pi: live view, boxes, fps and temperature. q or Esc quits."""
    import cv2
    from forrest.drivers.camera_hailo import VisionLoop
    vision = VisionLoop(threshold=args.threshold, view_size=(960, 720), view_fps=15,
                        encode_jpeg=False)
    vision.start()
    win = "Forrest Jr - camera + Hailo"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 960, 720)
    seq, last_temp, temp = 0, 0.0, None
    try:
        while vision.is_alive():
            with vision.new_frame:
                vision.new_frame.wait_for(lambda: vision.jpeg_seq != seq, timeout=1)
                img, seq = vision.latest_view, vision.jpeg_seq
            if img is not None:
                if time.time() - last_temp > 2:
                    temp, last_temp = read_temp_c(), time.time()
                st = vision.status()
                line = f"{st['fps']:.1f} fps   {temp if temp is not None else '-'} C   threshold {st['threshold']}"
                frame = img.copy()
                cv2.putText(frame, line, (10, frame.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 255, 255), 2)
                cv2.imshow(win, frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                break  # window closed with the X button
        err = vision.status()["error"]
        if err:
            print(f"vision stopped: {err}")
            return 1
    finally:
        vision.stop()
        vision.join(timeout=5)
        cv2.destroyAllWindows()
    return 0


def cmd_dash(args) -> int:
    from forrest.dashboard.server import serve, tailscale_ip
    host = args.host or tailscale_ip() or "127.0.0.1"
    vision = None
    if args.camera:
        from forrest.drivers.camera_hailo import VisionLoop
        vision = VisionLoop(threshold=args.threshold)
        vision.start()
    httpd = serve(host, args.port, vision)
    print(f"dashboard: http://{host}:{args.port}/   (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        if vision:
            vision.stop()
            vision.join(timeout=5)
    return 0


# ---------------------------------------------------------------------------
# pico check  (is the Pico alive and answering? read-only: never sends drive commands)
# ---------------------------------------------------------------------------

def _ago(ms: int) -> str:
    s = ms / 1000
    if s < 60:
        return f"{s:.1f} s ago"
    m = int(s // 60)
    return f"{m // 60} h {m % 60} min ago" if m >= 60 else f"{m} min ago"


def cmd_pico_check(args) -> int:
    from forrest.drivers.pico import Pico, PicoError

    try:
        pico = Pico(args.port)
    except (PicoError, OSError) as e:
        print(f"Pico: {e}")
        if "lock" in str(e):
            print("Another program has the Pico open (only one may). "
                  "Stop it first, e.g. `systemctl --user stop forrest-pico` or close mpremote.")
        return 1
    answered, rtts = 0, []
    print(f"Pico on {pico.port}. Polling status {args.polls}x (read-only, no drive commands).")
    try:
        for i in range(args.polls):
            t0 = time.monotonic()
            try:
                stat = pico.status()
            except OSError as e:          # unplugged mid-run (SerialException is an OSError)
                print(f"  {i + 1}: link lost: {e}")
                break
            for ev in list(pico.events):
                print(f"  event: {ev.text}")
            pico.events.clear()
            if stat is None:
                print(f"  {i + 1}: no reply in 0.5 s")
            else:
                answered += 1
                rtts.append(1000 * (time.monotonic() - t0))
                f = stat.fields
                state = "FAILSAFE (throttle cut)" if f["age_ms"] > 500 else "commanded"
                print(f"  {i + 1}: {state:24s} throttle {f['throttle']:5d}  steer {f['steer']:5d}  "
                      f"esc {f['esc_ns'] / 1e6:.3f} ms  last cmd {_ago(f['age_ms'])}  "
                      f"loop gap {f['max_gap_ms']} ms  trips {f.get('trips', '?')}")
            if i + 1 < args.polls:
                time.sleep(args.every)
    finally:
        try:
            pico.close()
        except OSError:
            pass
    rtts.sort()
    rtt = f", round trip {rtts[len(rtts) // 2]:.1f} ms median" if rtts else ""
    print(f"Link {'UP' if answered == args.polls else 'DOWN' if not answered else 'FLAKY'}: "
          f"{answered}/{args.polls} answered{rtt}.")
    return 0 if answered == args.polls else 1


def cmd_pico_monitor(args) -> int:
    from pathlib import Path as _P

    from forrest.health import pico_monitor as pm

    state = _P(args.state) if args.state else pm.default_state_path()
    print(f"Pico monitor (read-only). State: {state}  Log: {args.log_dir}/pico_YYYYMMDD.jsonl  "
          f"Poll every {args.every} s. Ctrl-C to stop.", flush=True)
    pm.run(state, _P(args.log_dir), every_s=args.every,
           say=lambda line: print(line, flush=True))
    return 0


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="forrest", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    lidar = sub.add_parser("lidar", help="LIDAR bench tools (B1)")
    lsub = lidar.add_subparsers(dest="lidar_cmd", required=True)

    c = lsub.add_parser("check", help="info, health and a live sector view")
    c.add_argument("--port", default=DEFAULT_PORT)
    c.set_defaults(func=cmd_lidar_check)

    r = lsub.add_parser("record", help="save scans to a .jsonl file")
    r.add_argument("out")
    r.add_argument("--seconds", type=float, default=30)
    r.add_argument("--port", default=DEFAULT_PORT)
    r.set_defaults(func=cmd_lidar_record)

    v = lsub.add_parser("view", help="polar plot, live or from a recording")
    v.add_argument("--replay", help="a .jsonl recording (no hardware needed)")
    v.add_argument("--range", type=float, default=4.0, help="plot radius in metres")
    v.add_argument("--port", default=DEFAULT_PORT)
    v.set_defaults(func=cmd_lidar_view)

    s = sub.add_parser("soak", help="B2: LIDAR spinning + power log on battery")
    s.add_argument("--minutes", type=float, default=60)
    s.add_argument("--every", type=float, default=10, help="seconds between log lines")
    s.add_argument("--log", default=f"data/soak_{time.strftime('%Y%m%d_%H%M')}.csv")
    s.add_argument("--port", default=DEFAULT_PORT)
    s.set_defaults(func=cmd_soak)

    pw = sub.add_parser("power", help="one-shot Pi power and heat check")
    pw.set_defaults(func=cmd_power)

    vw = sub.add_parser("view", help="desktop window on the Pi: live view + detections")
    vw.add_argument("--threshold", type=float, default=0.5, help="minimum detection score")
    vw.set_defaults(func=cmd_view)

    d = sub.add_parser("dash", help="dashboard web server (camera, detections, Pi status)")
    d.add_argument("--host", help="bind address (default: this Pi's Tailscale IP)")
    d.add_argument("--port", type=int, default=8090)
    d.add_argument("--threshold", type=float, default=0.5, help="minimum detection score")
    d.add_argument("--camera", action="store_true",
                   help="also run camera + Hailo detection (holds the camera)")
    d.set_defaults(func=cmd_dash)

    pico = sub.add_parser("pico", help="Pico 2 drive controller tools")
    psub = pico.add_subparsers(dest="pico_cmd", required=True)
    pc = psub.add_parser("check", help="poll the Pico's status (read-only)")
    pc.add_argument("--port", help="serial port (default: find the Pico by USB id)")
    pc.add_argument("--polls", type=int, default=5)
    pc.add_argument("--every", type=float, default=1.0, help="seconds between polls")
    pc.set_defaults(func=cmd_pico_check)
    pm = psub.add_parser("monitor", help="watch the Pico; write state for the dashboard + a daily log")
    pm.add_argument("--every", type=float, default=1.0, help="seconds between polls")
    pm.add_argument("--state", help="state file (default: $XDG_RUNTIME_DIR/forrest/pico.json)")
    pm.add_argument("--log-dir", default="data/pico")
    pm.set_defaults(func=cmd_pico_monitor)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
