// Forrest Jr - open "cage" case for Pi 5 + Active Cooler + AI HAT+ 26 TOPS, v0
//
// Two printed parts:  TRAY (base + 4 corner posts + camera wall)  and  LID.
// Set `part` below to "tray", "lid" or "assembly" (preview only).
//
// Design intent
//  * Protect the stack (off the floor, nothing can land on the boards).
//  * Open sides at every level: ports, the PCIe ribbon, camera ribbons and
//    future cables all reach the Pi/HAT gap without a redesign.
//  * Airflow: vents under the Pi + open sides feed the Pi's Active Cooler;
//    a 40 mm fan in the lid blows down on the Hailo heatsink.
//  * GPIO stays reachable from above the HAT through a slot in the lid.
//  * Mounts: two M5 holes on a 2020-extrusion line (Jr -> Sr mounting
//    standard), plus strap slots, plus feet for the bench.
//
// Stack (unchanged from the v0/v1 plates):
//   M2.5 screw from underneath -> tray -> 6 mm standoff -> Pi 5
//   -> 16 mm standoff -> AI HAT+ -> M2.5 nut
//
// Coordinates: Pi board frame. x = 0 at the microSD / PCIe end,
// x = 85 at the USB / Ethernet end; y = 0 at the USB-C / HDMI edge,
// y = 56 at the GPIO edge. z = 0 at the top of the tray floor.
// All sizes in mm.

part = "assembly";   // "tray" | "lid" | "assembly"

/* ---------- Pi 5 ---------- */
board_x = 85;  board_y = 56;  board_t = 1.6;
hole_inset = 3.5;  hole_dx = 58;  hole_dy = 49;
corner_r = 3;

/* ---------- Stack heights (above tray floor) ---------- */
standoff_lo = 6;                         // under the Pi
standoff_hi = 16;                        // Pi -> HAT
pi_z   = standoff_lo;                    // Pi underside
hat_z  = pi_z + board_t + standoff_hi;   // HAT underside  (23.6)
hat_top = hat_z + board_t;               // (25.2)
hailo_sink_h = 9;                        // heatsink height on the HAT (measure)
gpio_head_h  = 8.5;                      // header body on top of the HAT
dupont_h     = 14;                       // room for jumper plugs on the header

/* ---------- Case ---------- */
floor_t = 3;
lid_t   = 3;
margin  = 9;            // board edge -> outside of the corner posts
post_w  = 8;
lid_z   = hat_top + gpio_head_h + dupont_h;   // underside of lid (~47.7)
feet_h  = 4;            // ribs under the floor (air in, keeps it off the bench)
ext_cam = 22;           // tray extension past the SD end for the camera wall

/* ---------- Screws ---------- */
pi_screw_d   = 2.9;   head_d = 5.6;   head_depth = 2.4;   // M2.5
lid_pilot_d  = 2.6;   // M3 self-tapping into the posts
lid_clear_d  = 3.4;   lid_head_d = 6.2;
m5_clear_d   = 5.5;   // 2020 extrusion T-nut bolts

/* ---------- Fan (40 x 40 x 10, 5 V, holes on 32 mm) ---------- */
fan_size = 40;  fan_hole_dx = 32;  fan_hole_d = 3.4;
fan_c = [33, 28];     // over the Hailo heatsink (measure and adjust)

/* ---------- Optional side fan (front / USB-C-HDMI side) ----------
   A 40 mm fan on a separate bracket, blowing into the Pi-HAT gap so the
   Active Cooler breathes fresh air. Sits to the right of the HDMI plugs
   (x 48..88) so every port stays usable. The GPIO side is not used: the
   stacking header's body is a solid wall under the HAT there. */
sf_x0 = 48;  sf_z0 = 8;                 // fan's lower-left corner
sf_c  = [sf_x0 + 20, sf_z0 + 20];       // fan centre (x, z)
sf_t  = 3;                              // bracket plate thickness
sf_boss_x = 53;                         // lower screw, into the rail boss
sf_bracket_holes = [[90, 20], [90, 40], [sf_boss_x, 5]];   // (x, z)

/* ---------- GPIO slot in the lid ---------- */
gpio_x0 = 7;  gpio_len = 52;  gpio_y = 52.5;  gpio_slot_w = 9;

/* ---------- Camera wall (same as plate v1) ---------- */
cam_w = 25;  cam_h = 24;  cam_hole_dx = 21;  cam_hole_dy = 12.5;
cam_hole_top = 2;  cam_hole_d = 2.4;  cam_slot = 3;  cam_lift = 9;
lens_win = 14;  lens_from_top = 9.5;  wall_t = 3;  boss_h = 1.5;

$fn = 40;

/* ---------- Derived ---------- */
x0 = -margin;              x1 = board_x + margin;
y0 = -margin;              y1 = board_y + margin;
tray_x0 = -ext_cam;
post_c = [[x0 + post_w/2, y0 + post_w/2], [x1 - post_w/2, y0 + post_w/2],
          [x0 + post_w/2, y1 - post_w/2], [x1 - post_w/2, y1 - post_w/2]];
pi_holes = [for (i = [0,1], j = [0,1])
            [hole_inset + i*hole_dx, hole_inset + j*hole_dy]];
cam_cy = board_y / 2;
wall_x = tray_x0 + 2;
cam_bottom = cam_lift;  cam_top = cam_bottom + cam_h;
wall_h = cam_top + 4;

module rrect(x, y, w, d, h, r = 3)
    translate([x, y, 0]) hull() for (a = [r, w - r], b = [r, d - r])
        translate([a, b, 0]) cylinder(r = r, h = h);

/* ================= TRAY ================= */
module tray() {
    difference() {
        union() {
            // floor (top at z = 0)
            translate([0, 0, -floor_t])
                rrect(tray_x0, y0, x1 - tray_x0, y1 - y0, floor_t);
            // feet ribs along x, under the floor
            for (y = [y0 + 2, cam_cy - 2, y1 - 6])
                translate([tray_x0 + 4, y, -floor_t - feet_h])
                    cube([x1 - tray_x0 - 8, 4, feet_h]);
            // corner posts
            for (p = post_c) translate([p[0] - post_w/2, p[1] - post_w/2, 0])
                cube([post_w, post_w, lid_z]);
            // low stiffening rails along the long sides (below the Pi)
            for (y = [y0, y1 - 3])
                translate([x0, y, 0]) cube([x1 - x0, 3, 4]);
            // boss on the front rail for the side-fan bracket's lower screw
            translate([sf_boss_x - 3, y0, 0]) cube([6, 3, 10]);
            camera_wall();
        }
        // Pi screws from underneath, heads recessed
        for (p = pi_holes) translate([p[0], p[1], -floor_t - feet_h - 1]) {
            cylinder(d = pi_screw_d, h = 20);
            cylinder(d = head_d, h = feet_h + 1 + head_depth);
        }
        // floor vents under the Pi (between the screw holes and the feet)
        for (x = [12 : 7 : 72]) translate([x, 10, -floor_t - 1])
            hull() for (y = [0, 36]) translate([0, y, 0]) cylinder(d = 4, h = floor_t + 2);
        // lid screw pilots in the posts
        for (p = post_c) translate([p[0], p[1], lid_z - 12]) cylinder(d = lid_pilot_d, h = 13);
        // side-fan bracket pilots: into the right front post, and the rail boss
        for (h = sf_bracket_holes) translate([h[0], y0 - 1, h[1]])
            rotate([-90, 0, 0]) cylinder(d = lid_pilot_d, h = 11);
        // 2020 rail mount: two M5 holes on the centreline
        for (x = [10, 75]) translate([x, cam_cy, -floor_t - feet_h - 1])
            cylinder(d = m5_clear_d, h = floor_t + feet_h + 2);
        // strap / zip-tie slots
        for (x = [-12, 91], s = [-1, 1])
            translate([x - 1.2, cam_cy + s*20 - 2.25, -floor_t - 1]) cube([2.4, 4.5, floor_t + 2]);
    }
}

module camera_wall() {
    hole_z1 = cam_top - cam_hole_top;  hole_z2 = hole_z1 - cam_hole_dy;
    lens_z = cam_top - lens_from_top;
    difference() {
        union() {
            translate([wall_x, cam_cy - (cam_w + 8)/2, 0]) cube([wall_t, cam_w + 8, wall_h]);
            for (dy = [-cam_hole_dx/2, cam_hole_dx/2], z = [hole_z1, hole_z2])
                translate([wall_x + wall_t, cam_cy + dy, z]) rotate([0, 90, 0]) cylinder(d = 5, h = boss_h);
            for (s = [-1, 1])
                translate([wall_x + wall_t, cam_cy + s*(cam_w + 8)/2 - (s > 0 ? 3 : 0), 0])
                    rotate([90, 0, 0]) translate([0, 0, -3]) linear_extrude(3)
                        polygon([[0, 0], [12, 0], [0, wall_h * 0.75]]);
        }
        translate([wall_x - 1, cam_cy - lens_win/2, lens_z - lens_win/2])
            cube([wall_t + boss_h + 2, lens_win, lens_win]);
        for (dy = [-cam_hole_dx/2, cam_hole_dx/2], z = [hole_z1, hole_z2])
            hull() for (o = [-cam_slot/2, cam_slot/2])
                translate([wall_x - 1, cam_cy + dy + o, z]) rotate([0, 90, 0])
                    cylinder(d = cam_hole_d, h = wall_t + boss_h + 2);
    }
}

/* ================= LID ================= */
module lid() {
    difference() {
        rrect(x0, y0, x1 - x0, y1 - y0, lid_t);
        // fan opening as a grille: rings + cross ribs left solid
        translate([fan_c[0], fan_c[1], -1]) difference() {
            cylinder(d = fan_size - 3, h = lid_t + 2);
            for (r = [10, 17]) difference() {
                cylinder(r = r + 1, h = lid_t + 2);
                cylinder(r = r - 1, h = lid_t + 2);
            }
            for (a = [0, 90]) rotate([0, 0, a]) translate([-1, -fan_size/2, 0]) cube([2, fan_size, lid_t + 2]);
        }
        // fan screws
        for (i = [-1, 1], j = [-1, 1])
            translate([fan_c[0] + i*fan_hole_dx/2, fan_c[1] + j*fan_hole_dx/2, -1])
                cylinder(d = fan_hole_d, h = lid_t + 2);
        // GPIO wire slot
        translate([gpio_x0, gpio_y - gpio_slot_w/2, -1]) cube([gpio_len, gpio_slot_w, lid_t + 2]);
        // corner screws, countersunk from the top
        for (p = post_c) translate([p[0], p[1], -1]) {
            cylinder(d = lid_clear_d, h = lid_t + 2);
            translate([0, 0, lid_t - 1]) cylinder(d = lid_head_d, h = 2);
        }
        // extra vents over the USB end (hot USB/Ethernet chips, RP1)
        for (x = [62 : 6 : 80]) translate([x, 8, -1])
            hull() for (y = [0, 32]) translate([0, y, 0]) cylinder(d = 3.5, h = lid_t + 2);
    }
}

/* ================= SIDE-FAN BRACKET ================= */
// Modelled in place (plate in the x-z plane against the front of the posts).
// Print it lying flat: it is a plain 3 mm plate.
module sidefan() {
    translate([0, y0, 0]) rotate([90, 0, 0]) difference() {
        // plate: x 47..94, z 2..52, thickness sf_t (towards -y)
        translate([47, 2, 0]) cube([x1 - 47, 50, sf_t]);
        // grille opening
        translate([sf_c[0], sf_c[1], -1]) difference() {
            cylinder(d = fan_size - 3, h = sf_t + 2);
            for (r = [10, 17]) difference() {
                cylinder(r = r + 1, h = sf_t + 2);
                cylinder(r = r - 1, h = sf_t + 2);
            }
            for (a = [0, 90]) rotate([0, 0, a]) translate([-1, -fan_size/2, 0]) cube([2, fan_size, sf_t + 2]);
        }
        // fan screws
        for (i = [-1, 1], j = [-1, 1])
            translate([sf_c[0] + i*fan_hole_dx/2, sf_c[1] + j*fan_hole_dx/2, -1])
                cylinder(d = fan_hole_d, h = sf_t + 2);
        // bracket screws into the post and rail boss
        for (h = sf_bracket_holes) translate([h[0], h[1], -1])
            cylinder(d = lid_clear_d, h = sf_t + 2);
    }
}

/* ================= Ghosts (preview only) ================= */
module ghosts() {
    // Pi, cooler block, HAT, heatsink, fan
    color("green", 0.5) translate([0, 0, pi_z]) rrect(0, 0, board_x, board_y, board_t);
    color("silver", 0.4) translate([20, 8, pi_z + board_t]) cube([45, 40, 9]);
    color("green", 0.5) translate([0, 0, hat_z]) rrect(0, 0, 65, 56.5, board_t);
    color("silver", 0.6) translate([fan_c[0] - 9, fan_c[1] - 9, hat_top]) cube([18, 18, hailo_sink_h]);
    color("black", 0.5) translate([7, 50, hat_top]) cube([51, 5, gpio_head_h]);
    color("dimgray", 0.5) translate([fan_c[0] - fan_size/2, fan_c[1] - fan_size/2, lid_z - 10]) cube([fan_size, fan_size, 10]);
    for (p = pi_holes) color("gold") translate([p[0], p[1], 0]) cylinder(d = 4, h = hat_z);
}

if (part == "tray") tray();
else if (part == "lid") lid();
else if (part == "sidefan") rotate([-90, 0, 0]) translate([0, -y0, 0]) sidefan();  // flat for printing
else {
    color("orange") tray();
    color("tan", 0.85) translate([0, 0, lid_z]) lid();
    color("tan", 0.85) sidefan();
    color("dimgray", 0.5) translate([sf_x0, y0 - sf_t - 10, sf_z0]) cube([fan_size, 10, fan_size]);
    ghosts();
}
