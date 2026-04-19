// Digital djembe / darbuka transducer mounts and mic jig.
// Parametric OpenSCAD. All units mm.
//
// Four parts in this file, toggled via the `part` variable at the bottom:
//   "hoop_clamp"   - C-clamp that straddles the tuning hoop, holds a tactile
//                    transducer on its outer face. Non-destructive.
//   "bolt_bracket" - L-bracket that replaces one tuning-bolt washer; the
//                    existing tuning bolt holds it down against the hoop ear.
//   "body_magnet"  - Plate that glues to the back of a transducer and carries
//                    two disc magnets, for non-destructive mounting on a
//                    metal darbuka body.
//   "mic_jig"      - Cap that drops over the hoop and positions a measurement
//                    mic a fixed distance above head center. Makes runs
//                    comparable between mounts.
//
// Measure your darbuka first and set the parameters below.

/* ============= USER PARAMETERS (MEASURE YOURS) ============= */

// Tuning hoop cross-section (the metal ring the skin wraps over).
// Most modern darbukas use 5-7 mm round or rectangular steel rod.
hoop_thickness = 6.0;     // radial (vertical) dimension of the ring stock
hoop_width     = 6.0;     // tangential (horizontal) dimension

// Head diameter, measured across the playing surface.
head_diameter  = 220.0;   // 8.66" = typical modern darbuka

// Tuning bolt thread (for bolt_bracket part). Common: M5 or M6.
tuning_bolt_d  = 5.2;     // clearance hole for M5

// Transducer footprint. Dayton DAEX13CT-4 = ~30 mm disc, M3 mount pattern.
// For DAEX25FHE-4 use transducer_od = 35, transducer_bolt_pcd = 28.
transducer_od        = 30.0;
transducer_bolt_pcd  = 24.0;  // pitch-circle diameter of its M3 holes
transducer_bolt_d    = 3.2;   // M3 clearance
transducer_bolts     = 3;     // how many mounting holes it has

// Measurement mic body diameter (for mic_jig clip).
mic_od         = 20.0;    // Dayton UMM-6 is 22 mm; small pencil condensers 20
mic_height_above_head = 50.0;  // 5 cm above the head surface

/* ============= CONSTANTS ============= */

wall = 3.0;         // general wall thickness
$fn = 96;

/* ============= HOOP CLAMP ============= */
// Two halves that pinch the hoop between them, M3 pinch bolts on each side.
// Front half carries the transducer mount pattern.

module hoop_slot() {
    // slightly oversized to slip over hoop
    translate([-hoop_width/2 - 0.3, -hoop_thickness/2 - 0.3, -50])
        cube([hoop_width + 0.6, hoop_thickness + 0.6, 100]);
}

module transducer_face_holes() {
    for (i = [0:transducer_bolts - 1]) {
        a = i * 360 / transducer_bolts;
        translate([cos(a) * transducer_bolt_pcd/2,
                   sin(a) * transducer_bolt_pcd/2,
                   0])
            cylinder(d = transducer_bolt_d, h = 100, center = true);
    }
    // central pass-through for the transducer's voice coil back
    cylinder(d = transducer_od * 0.55, h = 100, center = true);
}

module pinch_bolt_holes() {
    // two M3 bolts, one above and one below the hoop slot
    offset_y = hoop_thickness/2 + 4.5;
    for (s = [-1, 1])
        translate([0, s * offset_y, 0])
            rotate([90, 0, 0])
                cylinder(d = 3.3, h = 100, center = true);
    // captive nut pockets on the rear
    for (s = [-1, 1])
        translate([0, s * offset_y, -(wall + hoop_width/2 + 2)])
            rotate([90, 0, 0])
                cylinder(d = 6.4, h = 3.2, center = true, $fn = 6);
}

module hoop_clamp_front() {
    difference() {
        union() {
            // transducer mounting face - a disc offset outward from the hoop
            translate([0, 0, hoop_width/2 + wall])
                cylinder(d = transducer_od + 8, h = wall);
            // body of the clamp half
            translate([-(transducer_od + 8)/2, -(hoop_thickness/2 + 8),
                       -hoop_width/2])
                cube([transducer_od + 8, hoop_thickness + 16, hoop_width/2 + wall]);
        }
        hoop_slot();
        translate([0, 0, hoop_width/2 + wall]) transducer_face_holes();
        pinch_bolt_holes();
    }
}

module hoop_clamp_back() {
    difference() {
        translate([-(transducer_od + 8)/2, -(hoop_thickness/2 + 8),
                   -(hoop_width/2 + wall)])
            cube([transducer_od + 8, hoop_thickness + 16, wall]);
        pinch_bolt_holes();
    }
}

module hoop_clamp() {
    hoop_clamp_front();
    // print the back flipped alongside so both print in one job
    translate([transducer_od + 20, 0, hoop_width/2 + wall])
        rotate([180, 0, 0])
            hoop_clamp_back();
}

/* ============= BOLT-BRACKET (replaces one tuning-bolt washer) ============= */

module bolt_bracket() {
    L = transducer_od + 14;
    H = transducer_od + 14;
    difference() {
        union() {
            // horizontal foot that sits under the tuning bolt head
            cube([L, 12, wall]);
            // vertical face for the transducer
            translate([0, 0, wall])
                cube([L, wall, H]);
        }
        // bolt clearance in the foot
        translate([L/2, 6, -1])
            cylinder(d = tuning_bolt_d, h = wall + 2);
        // transducer pattern in the face
        translate([L/2, wall + 1, H/2 + wall])
            rotate([90, 0, 0])
                transducer_face_holes();
    }
    // small gusset for stiffness
    translate([L/2 - 1, 0, wall])
        cube([2, 10, H * 0.6]);
}

/* ============= BODY MAGNET PLATE ============= */
// Glues to back of transducer; two disc magnets clip it to a metal body.

magnet_d = 10.2;
magnet_h = 3.2;

module body_magnet() {
    difference() {
        hull() {
            for (s = [-1, 1])
                translate([s * (transducer_od/2), 0, 0])
                    cylinder(d = magnet_d + 6, h = 4);
        }
        for (s = [-1, 1])
            translate([s * (transducer_od/2), 0, 4 - magnet_h])
                cylinder(d = magnet_d, h = magnet_h + 1);
        translate([0, 0, -1]) transducer_face_holes();
    }
}

/* ============= MIC JIG ============= */
// A cap that rests on the hoop (doesn't touch the head) with a centered arm
// holding the mic at a fixed height. Only used DURING measurement, removed
// before playing.

module mic_jig() {
    ring_od = head_diameter + 12;
    ring_id = head_diameter - 10;
    rim_h   = 8;

    difference() {
        union() {
            // rim that rests on the hoop
            difference() {
                cylinder(d = ring_od, h = rim_h);
                translate([0, 0, -1]) cylinder(d = ring_id, h = rim_h + 2);
            }
            // crossbar diameter to hold center arm
            translate([-ring_od/2, -6, 0])
                cube([ring_od, 12, rim_h]);
            // mic arm rising from center
            translate([0, 0, rim_h])
                cylinder(d = 10, h = mic_height_above_head + 10);
            // mic clip ring at the top
            translate([0, 0, rim_h + mic_height_above_head])
                cylinder(d = mic_od + 8, h = 14);
        }
        // through-hole for mic
        translate([0, 0, rim_h + mic_height_above_head - 1])
            cylinder(d = mic_od + 0.3, h = 20);
        // slit so the mic clip flexes
        translate([-0.8, 0, rim_h + mic_height_above_head])
            cube([1.6, ring_od/2, 16]);
    }
}

/* ============= PART SELECTOR ============= */
// Set this to one of: "hoop_clamp" | "bolt_bracket" | "body_magnet" | "mic_jig"
part = "hoop_clamp";

if (part == "hoop_clamp")   hoop_clamp();
else if (part == "bolt_bracket") bolt_bracket();
else if (part == "body_magnet")  body_magnet();
else if (part == "mic_jig")      mic_jig();
