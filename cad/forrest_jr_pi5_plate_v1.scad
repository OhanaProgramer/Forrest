// Forrest Jr - Pi 5 holding plate, v1
// v1 adds: camera wall at the microSD end, and cable tie-down areas
// behind the USB/Ethernet end and along the power/HDMI edge.
//
// Stack (bottom to top), unchanged from v0:
//   M2.5 screw from underneath (head in recess) -> plate
//   -> 6 mm male-female standoff -> Pi 5 -> 16 mm male-female standoff
//   -> AI HAT+ -> M2.5 nut
//
// Camera (OV5647 board, 25 x 24 mm, M2 holes on 21 x 12.5 mm):
//   board sits on the INSIDE face of the wall, lens pokes out through the
//   window, M2 screws go in from the outside, nuts on the inside.
//   Holes are short slots so small differences between camera brands still fit.
//   Ribbon exits the bottom of the camera board and runs along the plate to the Pi.
//
// All sizes in mm.

/* ---------- Pi 5 (official mechanical drawing) ---------- */
board_x    = 85;
board_y    = 56;
corner_r   = 3;
hole_inset = 3.5;
hole_dx    = 58;
hole_dy    = 49;

/* ---------- Plate ---------- */
plate_t      = 4;
ext_camera   = 22;   // extension past the microSD end (camera wall lives here)
ext_cables   = 20;   // extension past the USB / Ethernet end (tie-downs)
ext_front    = 12;   // extension past the USB-C power / HDMI edge (tie-downs)
ext_back     = 4;    // extension past the GPIO edge

/* ---------- Pi screws ---------- */
screw_clear_d = 2.9;   // change after the fit-test strip comes back
head_d        = 5.6;
head_depth    = 2.4;

/* ---------- Camera wall ---------- */
cam_w        = 25;     // camera board width
cam_h        = 24;     // camera board height
cam_hole_dx  = 21;     // M2 hole spacing, across
cam_hole_dy  = 12.5;   // M2 hole spacing, up/down
cam_hole_top = 2;      // top hole row, down from the board's top edge
cam_hole_d   = 2.4;    // M2 clearance
cam_slot     = 3;      // slot length (side-to-side play)
cam_lift     = 9;      // gap under the camera board for the ribbon to bend
lens_win     = 14;     // square window for the lens holder
lens_from_top = 9.5;   // lens centre, down from the board's top edge
wall_t       = 3;
wall_x       = -ext_camera + 2;          // wall's outer face position
wall_h       = cam_lift + cam_h + 4;     // height above the plate top
boss_h       = 1.5;    // small pads that hold the board off the wall

/* ---------- Tie-down slots (zip ties) ---------- */
tie_len = 4.5;
tie_w   = 2.4;

/* ---------- Mount slots (strap to tripod plate / backpack) ---------- */
mount_x   = [31, 76];
mount_gap = 20;

$fn = 48;

/* ---------- Derived ---------- */
px0 = -ext_camera;
py0 = -ext_front;
pw  = board_x + ext_camera + ext_cables;
pd  = board_y + ext_front + ext_back;

pi_holes = [
    [hole_inset,           hole_inset],
    [hole_inset + hole_dx, hole_inset],
    [hole_inset,           hole_inset + hole_dy],
    [hole_inset + hole_dx, hole_inset + hole_dy]
];

cam_cy     = board_y / 2;                       // camera centred on the plate
cam_bottom = plate_t + cam_lift;                // board bottom height
cam_top    = cam_bottom + cam_h;

module rounded_rect(w, d, h, r) {
    hull() for (x = [r, w - r], y = [r, d - r])
        translate([x, y, 0]) cylinder(r = r, h = h);
}

// A slot cut straight through Z, centred at [x, y]
module zslot(x, y, along_x = false) {
    l = along_x ? tie_len : tie_w;
    w = along_x ? tie_w   : tie_len;
    translate([x - l / 2, y - w / 2, -1]) cube([l, w, plate_t + 2]);
}

module base() {
    difference() {
        translate([px0, py0, 0]) rounded_rect(pw, pd, plate_t, corner_r);

        // Pi screw holes + head recesses
        for (p = pi_holes) translate([p[0], p[1], 0]) {
            translate([0, 0, -1]) cylinder(d = screw_clear_d, h = plate_t + 2);
            translate([0, 0, -1]) cylinder(d = head_d, h = head_depth + 1);
        }

        // Mount slots under the Pi
        for (sx = mount_x, s = [-1, 1]) zslot(sx, board_y / 2 + s * mount_gap / 2);

        // Cable tie-downs behind USB / Ethernet: 3 pairs, one per plug stack
        for (y = [9, 27, 46], s = [-1, 1])
            zslot(board_x + ext_cables / 2 + s * 5, y, along_x = true);

        // Cable tie-downs along the power / HDMI edge: under USB-C and each HDMI
        for (x = [11, 26, 40], s = [-1, 1])
            zslot(x + s * 5, -ext_front / 2, along_x = true);

        // Ribbon tie-down between camera wall and Pi
        for (s = [-1, 1]) zslot(-ext_camera / 2 + 3, cam_cy + s * 9);
    }
}

module camera_wall() {
    hole_z1 = cam_top - cam_hole_top;
    hole_z2 = hole_z1 - cam_hole_dy;
    lens_z  = cam_top - lens_from_top;

    difference() {
        union() {
            // Wall
            translate([wall_x, cam_cy - (cam_w + 8) / 2, 0])
                cube([wall_t, cam_w + 8, wall_h]);
            // Pads that hold the board off the wall (inside face)
            for (dy = [-cam_hole_dx / 2, cam_hole_dx / 2], z = [hole_z1, hole_z2])
                translate([wall_x + wall_t, cam_cy + dy, z])
                    rotate([0, 90, 0]) cylinder(d = 5, h = boss_h);
            // Gussets (triangular braces) on each side
            for (s = [-1, 1])
                translate([wall_x + wall_t, cam_cy + s * (cam_w + 8) / 2 - (s > 0 ? 3 : 0), 0])
                    rotate([90, 0, 0]) translate([0, 0, -3])
                        linear_extrude(3)
                            polygon([[0, 0], [12, 0], [0, wall_h * 0.75]]);
        }
        // Lens window
        translate([wall_x - 1, cam_cy - lens_win / 2, lens_z - lens_win / 2])
            cube([wall_t + boss_h + 2, lens_win, lens_win]);
        // M2 slots (side-to-side)
        for (dy = [-cam_hole_dx / 2, cam_hole_dx / 2], z = [hole_z1, hole_z2])
            hull() for (o = [-cam_slot / 2, cam_slot / 2])
                translate([wall_x - 1, cam_cy + dy + o, z])
                    rotate([0, 90, 0]) cylinder(d = cam_hole_d, h = wall_t + boss_h + 2);
    }
}

// Ghosts for preview only (F5): Pi board and camera board. Not exported.
module ghosts() {
    %translate([0, 0, plate_t + 6]) rounded_rect(board_x, board_y, 1.6, corner_r);
    %translate([wall_x + wall_t + boss_h, cam_cy - cam_w / 2, cam_bottom])
        cube([1, cam_w, cam_h]);
}

base();
camera_wall();
ghosts();
