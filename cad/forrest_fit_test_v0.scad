// Forrest - fit-test strip, v0
// Print with the plate. Try a screw in each hole; the snug-but-free one
// is the size to use in the real parts.
//   Top row:    M2.5 (Pi standoffs)  2.6 2.7 2.8 2.9 3.0 3.1
//   Bottom row: M2 (camera)          2.1 2.2 2.3 2.4 2.5 2.6
// Numbers are pressed into the top face (x10, so 26 = 2.6 mm).

m25 = [2.6, 2.7, 2.8, 2.9, 3.0, 3.1];
m2  = [2.1, 2.2, 2.3, 2.4, 2.5, 2.6];
pitch = 9;
t = 3;
w = pitch * len(m25) + 4;
d = 24;
$fn = 48;

difference() {
    cube([w, d, t]);
    for (i = [0 : len(m25) - 1]) {
        x = 2 + pitch / 2 + i * pitch;
        // holes
        translate([x, 17, -1]) cylinder(d = m25[i], h = t + 2);
        translate([x, 7,  -1]) cylinder(d = m2[i],  h = t + 2);
        // labels
        translate([x, 21.2, t - 0.6]) linear_extrude(1)
            text(str(round(m25[i] * 10)), size = 2.4, halign = "center", valign = "center");
        translate([x, 2.3, t - 0.6]) linear_extrude(1)
            text(str(round(m2[i] * 10)), size = 2.4, halign = "center", valign = "center");
    }
}
