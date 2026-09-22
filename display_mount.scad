// ===================================================================
// Free-Standing Desktop Console Stand for 10.5" Display & Pi Zero 2 W
// VESA Direct Mount, Lip-Free Face, Solid Backplate, Slim Base
// ===================================================================

$fn = 60;

// --- Backplate & Tilt Dimensions ---
back_width     = 140.0;  // Width of support spine (mm)
back_height    = 130.0;  // Height of support spine (mm)
back_thick     = 6.0;    // Thickness of rear backplate (mm)
tilt_angle     = 15.0;   // Tilt back angle from vertical (degrees)

// --- Base Dimensions (Slimmed) ---
base_width     = 170.0;  // Broad stance (mm)
base_depth     = 145.0;  // Front-to-back footprint (mm)
base_thick     = 4.5;    // Slim base profile (mm)

cradle_y_pos   = -25.0;  // Forward placement so backward tilt balances center of mass

// --- 75mm VESA Mounting Holes (M4 Hardware) ---
// Two horizontal upper holes matching standard 75mm VESA pattern
vesa_spacing   = 75.0;   // Horizontal hole spacing (mm)
vesa_height    = 95.0;   // Height from bottom edge of spine (mm)
vesa_hole_dia  = 4.5;    // Clearance hole for standard M4 screws (mm)

// --- Pi Zero 2 W Standoffs (Rear Backplate) ---
pi_mount_enable = true;
pi_hole_x       = 58.0;  // Long axis of Pi Zero (mm)
pi_hole_y       = 23.0;  // Short axis of Pi Zero (mm)
pi_standoff_h   = 5.0;   // Standoff height off backplate (mm)
pi_standoff_dia = 5.5;   // Outer diameter of boss (mm)
pi_hole_dia     = 2.2;   // Pilot hole for self-tapping M2.5 screws (mm)
pi_mount_z      = 40.0;  // Centered lower on the spine below the VESA screws (mm)

module base_plate() {
    difference() {
        hull() {
            for (mx = [-base_width/2 + 10, base_width/2 - 10]) {
                for (my = [-base_depth/2 + 10, base_depth/2 - 10]) {
                    translate([mx, my, 0])
                        cylinder(r=10, h=base_thick);
                }
            }
        }
        
        // Shallow recessed pockets for rubber anti-slip feet
        for (mx = [-base_width/2 + 16, base_width/2 - 16]) {
            for (my = [-base_depth/2 + 16, base_depth/2 - 16]) {
                translate([mx, my, -0.1])
                    cylinder(r=6, h=1.0);
            }
        }
    }
}

module spine_assembly() {
    translate([0, cradle_y_pos, base_thick]) {
        rotate([-tilt_angle, 0, 0]) {
            difference() {
                union() {
                    // 1. Flush, solid front backplate (lip and cradle floor removed)
                    translate([-back_width/2, 0, 0])
                        cube([back_width, back_thick, back_height]);

                    // 2. Pi Zero 2 W mounting bosses on rear face (y = back_thick)
                    if (pi_mount_enable) {
                        translate([0, back_thick, pi_mount_z]) {
                            for (dx = [-pi_hole_x/2, pi_hole_x/2]) {
                                for (dz = [-pi_hole_y/2, pi_hole_y/2]) {
                                    translate([dx, 0, dz]) {
                                        rotate([-90, 0, 0]) {
                                            difference() {
                                                cylinder(r=pi_standoff_dia/2, h=pi_standoff_h);
                                                translate([0, 0, -0.1])
                                                    cylinder(r=pi_hole_dia/2, h=pi_standoff_h + 1);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 3. Two 75mm VESA M4 through-holes
                for (vx = [-vesa_spacing/2, vesa_spacing/2]) {
                    translate([vx, -1, vesa_height])
                        rotate([-90, 0, 0])
                            cylinder(r=vesa_hole_dia/2, h=back_thick + 2);
                }
            }
        }
    }
}

module rear_buttresses() {
    // Triangular buttresses supporting the rear of the spine
    buttress_thick  = 6.0;
    buttress_height = 80.0;
    buttress_reach  = 60.0;

    for (bx = [-back_width/2 + 4, back_width/2 - 4 - buttress_thick]) {
        hull() {
            // Footing on base plate
            translate([bx, cradle_y_pos, base_thick])
                cube([buttress_thick, buttress_reach, 2]);

            // Top anchor adhered to rear of backplate
            translate([bx, cradle_y_pos, base_thick])
                rotate([-tilt_angle, 0, 0])
                    translate([0, 0, buttress_height])
                        cube([buttress_thick, back_thick, 2]);
        }
    }
}

// --- Main Assembly ---
union() {
    base_plate();
    spine_assembly();
    rear_buttresses();
}
