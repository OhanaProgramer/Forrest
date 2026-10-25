// Forrest Jr - Pi 5 test holding plate, v0
// Holds: Raspberry Pi 5 + Official Active Cooler + AI HAT+ (16 mm standoffs)
//
// How the stack goes together (bottom to top):
//   M2.5 screw (from underneath, head sits in a recess)
//   -> this plate
//   -> 6 mm male-female brass standoff (female end down, on the screw)
//   -> Pi 5 (standoff's male thread pokes up through the Pi's hole)
//   -> 16 mm male-female standoff (screws onto that thread, clamps the Pi)
//   -> AI HAT+ (on the 16 mm male thread) -> M2.5 nut on top
//
// All sizes in mm. Change a number at the top, press F6, export STL.

/* ---------- Pi 5 (from the official mechanical drawing) ---------- */
board_x       = 85;    // Pi 5 length
board_y       = 56;    // Pi 5 width
corner_r      = 3;     // Pi 5 corner radius
hole_inset    = 3.5;   // hole centre from board edge
hole_dx       = 58;    // hole spacing, long direction
hole_dy       = 49;    // hole spacing, short direction

/* ---------- Plate ---------- */
plate_t       = 4;     // plate thickness
// Extra plate beyond the board edge. Kept at 0 on three sides so the
// microSD card (underside, left end), USB/Ethernet plugs (right end) and
// power/HDMI plugs (front edge) hang free. A little extra behind the GPIO edge.
margin_left   = 0;     // microSD end
margin_right  = 0;     // USB / Ethernet end
margin_front  = 0;     // USB-C power / micro-HDMI edge
margin_back   = 4;     // GPIO header edge

/* ---------- Screws ---------- */
screw_clear_d = 2.9;   // M2.5 clearance hole (prints slightly small, so a bit over 2.5)
head_d        = 5.6;   // recess for an M2.5 pan/cap head
head_depth    = 2.4;   // recess depth (head sits flush or below the bottom face)

/* ---------- Strap slots (zip ties / Velcro to a tripod plate or backpack) ---------- */
slots_on      = true;
slot_len      = 4.5;
slot_w        = 2.2;
slot_pairs_x  = [31, 76];   // x positions of the slot pairs (kept clear of the holes)
slot_gap      = 20;          // distance between the two slots in a pair

$fn = 48;

/* ---------- Derived ---------- */
plate_x0 = -margin_left;
plate_y0 = -margin_front;
plate_w  = board_x + margin_left + margin_right;
plate_d  = board_y + margin_front + margin_back;

hole_pts = [
    [hole_inset,            hole_inset],
    [hole_inset + hole_dx,  hole_inset],
    [hole_inset,            hole_inset + hole_dy],
    [hole_inset + hole_dx,  hole_inset + hole_dy]
];

module rounded_rect(w, d, h, r) {
    hull()
        for (x = [r, w - r], y = [r, d - r])
            translate([x, y, 0]) cylinder(r = r, h = h);
}

module plate() {
    difference() {
        translate([plate_x0, plate_y0, 0])
            rounded_rect(plate_w, plate_d, plate_t, corner_r);

        // Screw holes + head recesses (recess on the underside)
        for (p = hole_pts) translate([p[0], p[1], 0]) {
            translate([0, 0, -1]) cylinder(d = screw_clear_d, h = plate_t + 2);
            translate([0, 0, -1]) cylinder(d = head_d, h = head_depth + 1);
        }

        // Strap slots
        if (slots_on)
            for (sx = slot_pairs_x, s = [-1, 1])
                translate([sx - slot_w / 2,
                           board_y / 2 + s * slot_gap / 2 - slot_len / 2,
                           -1])
                    cube([slot_w, slot_len, plate_t + 2]);
    }
}

// Ghost of the Pi board, preview only (F5). Not exported.
module pi_ghost() {
    %translate([0, 0, plate_t + 6]) rounded_rect(board_x, board_y, 1.6, corner_r);
}

plate();
pi_ghost();
