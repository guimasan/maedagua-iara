// IARA V1 - Caixa alternativa estilizada (tema água: ondas/rios)
// Componentes: Arduino Uno + TDS Keyestudio + OLED 0.96" + bateria 18650 interna
// Exportar com: part = "base" ou part = "lid"

$fn = 64;

part = "assembled"; // "base", "lid", "assembled"
show_layout_helpers = false; // preview de disposição interna

// =====================
// Dimensões gerais
// =====================
wall = 2.4;
bottom = 2.8;
lid_thickness = 2.4;
clearance = 0.35;

inner_x = 170;
inner_y = 108;
inner_z = 34;

outer_x = inner_x + wall * 2;
outer_y = inner_y + wall * 2;
base_h = bottom + inner_z;
lid_h = 14;

corner_r = 11;

// =====================
// Furação e parafusos da tampa
// =====================
post_d = 8;
post_hole_d = 3.0;
post_core_h = inner_z - 2;
post_xy = [
    [12, 12],
    [outer_x - 12, 12],
    [outer_x - 12, outer_y - 12],
    [12, outer_y - 12]
];

// =====================
// Arduino Uno
// =====================
uno_pos = [14, 18, bottom];
standoff_d = 6.5;
standoff_h = 6;
standoff_hole_d = 2.9;
uno_holes = [
    [3.5, 2.5],
    [66.1, 7.6],
    [66.1, 35.5],
    [14.0, 50.8]
];

// recortes laterais do Uno (lado esquerdo da caixa)
usb_cut = [13, 11.5, 9.5];
usb_cut_pos = [0, uno_pos[1] + 36, 10.5];
jack_cut_d = 11;
jack_cut_pos = [0, uno_pos[1] + 16.5, 11.5];

// =====================
// TDS Keyestudio v1.0 (aprox.)
// =====================
tds_pos = [112, 20, bottom];
tds_holes = [
    [3.5, 3.5],
    [39.5, 28.5]
];

// =====================
// Bateria 18650 interna
// =====================
bat_d = 18.6 + 0.8;
bat_len = 65 + 1.2;

battery_cradle_pos = [52, 73, bottom + 2.2];
battery_cradle_w = bat_d + 8;
battery_cradle_l = bat_len + 8;
battery_cradle_h = 8.5;

// =====================
// OLED 0.96"
// =====================
oled_hole_pitch_x = 23;
oled_hole_pitch_y = 23;
oled_screen_x = 23.5;
oled_screen_y = 13.5;

oled_margin_top = 23;
oled_offset_x = 0;
oled_center = [outer_x / 2 + oled_offset_x, outer_y - oled_margin_top];

oled_hole_d = 2.4;
oled_post_d = 5.2;
oled_post_h = 4.0;
oled_post_hole_d = 1.9;

oled_cable_notch_w = 8;
oled_cable_notch_h = 4;

// =====================
// Saídas dos sensores
// =====================
cable_fit_clearance = 0.35;

// TDS: conector retangular 5x7 mm
cable_tds_w = 5 + cable_fit_clearance;
cable_tds_h = 7 + cable_fit_clearance;

// Temperatura: cabo 4 mm
cable_temp_d = 4 + cable_fit_clearance;

cable_cut_depth = wall + 2.4;

cable_tds_center_y = 32;
cable_tds_center_z = 12;
cable_tds_pos = [outer_x - cable_cut_depth, cable_tds_center_y - cable_tds_w / 2, cable_tds_center_z - cable_tds_h / 2];

cable_temp_pos = [outer_x - cable_cut_depth, 50, 11];

// recorte opcional para porta de carga da bateria (ex.: TP4056 USB-C/micro)
charge_cut = [11, wall + 2.2, 6.2];
charge_cut_pos = [outer_x / 2 - charge_cut[0] / 2, outer_y - charge_cut[1], 9.5];

echo("OLED center XY:", oled_center);

module riverstone_box(x, y, z, r) {
    hull() {
        translate([r + 8, r + 3, 0]) cylinder(h = z, r = r);
        translate([x - r - 6, r + 7, 0]) cylinder(h = z, r = r);
        translate([x - r - 8, y - r - 8, 0]) cylinder(h = z, r = r);
        translate([r + 6, y - r - 4, 0]) cylinder(h = z, r = r);
    }
}

module shell_base() {
    difference() {
        riverstone_box(outer_x, outer_y, base_h, corner_r);
        translate([wall, wall, bottom])
            riverstone_box(inner_x, inner_y, inner_z + 0.2, max(corner_r - wall, 2));
    }
}

module shell_lid() {
    difference() {
        riverstone_box(outer_x, outer_y, lid_h, corner_r);

        // cavidade interna da tampa
        translate([wall, wall, lid_thickness])
            riverstone_box(inner_x, inner_y, lid_h, max(corner_r - wall, 2));

        // aba de encaixe
        translate([wall + clearance, wall + clearance, 0])
            riverstone_box(inner_x - 2 * clearance, inner_y - 2 * clearance, 8.2, max(corner_r - wall - clearance, 2));

        // alívio do centro da aba
        translate([wall + 2.2, wall + 2.2, 0])
            riverstone_box(inner_x - 4.4, inner_y - 4.4, 8.4, max(corner_r - wall - 2.2, 2));
    }
}

module board_standoffs(origin, holes) {
    for (h = holes) {
        translate([origin[0] + h[0], origin[1] + h[1], origin[2]])
            difference() {
                cylinder(h = standoff_h, d = standoff_d);
                translate([0, 0, -0.1]) cylinder(h = standoff_h + 0.2, d = standoff_hole_d);
            }
    }
}

module lid_posts_for_screws() {
    for (p = post_xy) {
        translate([p[0], p[1], bottom])
            difference() {
                cylinder(h = post_core_h, d = post_d);
                translate([0, 0, -0.1]) cylinder(h = post_core_h + 0.2, d = post_hole_d);
            }
    }
}

module sensor_cable_holes() {
    // TDS retangular
    translate(cable_tds_pos)
        cube([cable_cut_depth, cable_tds_w, cable_tds_h]);

    // temperatura circular
    translate(cable_temp_pos)
        rotate([0, 90, 0]) cylinder(h = cable_cut_depth, d = cable_temp_d);
}

module uno_side_ports() {
    // USB-B
    translate([usb_cut_pos[0] - 0.5, usb_cut_pos[1], usb_cut_pos[2]])
        cube([usb_cut[0] + 1, usb_cut[1], usb_cut[2]]);

    // Jack DC
    translate([jack_cut_pos[0] - 0.5, jack_cut_pos[1], jack_cut_pos[2]])
        rotate([0, 90, 0]) cylinder(h = wall + 1.5, d = jack_cut_d);
}

module battery_charge_cutout() {
    translate(charge_cut_pos)
        cube(charge_cut);
}

module battery_cradle() {
    translate(battery_cradle_pos)
        difference() {
            cube([battery_cradle_l, battery_cradle_w, battery_cradle_h]);

            // canal semicircular para 18650
            translate([battery_cradle_l / 2, battery_cradle_w / 2, battery_cradle_h + 0.2])
                rotate([0, 90, 0])
                    cylinder(h = battery_cradle_l + 0.4, r = bat_d / 2, center = true);

            // janela inferior para reduzir material e facilitar encaixe
            translate([8, 3, -0.1])
                cube([battery_cradle_l - 16, battery_cradle_w - 6, battery_cradle_h - 2.6]);

            // slots de abraçadeira (zip tie)
            translate([18, -0.1, 1.8]) cube([3.2, battery_cradle_w + 0.2, 2.2]);
            translate([battery_cradle_l - 21.2, -0.1, 1.8]) cube([3.2, battery_cradle_w + 0.2, 2.2]);
        }
}

module battery_end_stops() {
    // batentes para a célula não deslizar
    translate([battery_cradle_pos[0] + 2.5, battery_cradle_pos[1] + 2.2, battery_cradle_pos[2] + 1.4])
        cube([2.2, battery_cradle_w - 4.4, 6]);
    translate([battery_cradle_pos[0] + battery_cradle_l - 4.7, battery_cradle_pos[1] + 2.2, battery_cradle_pos[2] + 1.4])
        cube([2.2, battery_cradle_w - 4.4, 6]);
}

module lid_oled_window_and_holes() {
    // janela do display
    translate([oled_center[0] - oled_screen_x / 2, oled_center[1] - oled_screen_y / 2, -0.2])
        cube([oled_screen_x, oled_screen_y, lid_thickness + 0.8]);

    // furos da placa OLED
    for (sx = [-oled_hole_pitch_x / 2, oled_hole_pitch_x / 2])
        for (sy = [-oled_hole_pitch_y / 2, oled_hole_pitch_y / 2])
            translate([oled_center[0] + sx, oled_center[1] + sy, -0.2])
                cylinder(h = lid_thickness + 1.3, d = oled_hole_d);

    // canal para fios do OLED
    translate([oled_center[0] - oled_cable_notch_w / 2, oled_center[1] + oled_hole_pitch_y / 2 - 1, -0.2])
        cube([oled_cable_notch_w, oled_cable_notch_h, lid_thickness + 0.8]);
}

module lid_oled_posts() {
    for (sx = [-oled_hole_pitch_x / 2, oled_hole_pitch_x / 2])
        for (sy = [-oled_hole_pitch_y / 2, oled_hole_pitch_y / 2])
            translate([oled_center[0] + sx, oled_center[1] + sy, lid_thickness])
                difference() {
                    cylinder(h = oled_post_h, d = oled_post_d);
                    translate([0, 0, -0.1]) cylinder(h = oled_post_h + 0.2, d = oled_post_hole_d);
                }
}

module lid_screw_holes() {
    for (p = post_xy) {
        translate([p[0], p[1], -0.2])
            cylinder(h = lid_h + 0.4, d = 3.4);
        translate([p[0], p[1], lid_h - 2.2])
            cylinder(h = 2.5, d = 6.2);
    }
}

// ranhuras decorativas em forma de onda (relevo negativo)
module wave_slot(y0, amp, phase, depth = 1.15, radius = 1.5) {
    for (x = [14:10:outer_x - 24]) {
        x2 = x + 10;
        y1 = y0 + amp * sin((x + phase) * 2.6);
        y2 = y0 + amp * sin((x2 + phase) * 2.6);
        hull() {
            translate([x, y1, lid_h - depth]) cylinder(h = depth + 0.35, r = radius);
            translate([x2, y2, lid_h - depth]) cylinder(h = depth + 0.35, r = radius);
        }
    }
}

module lid_wave_pattern() {
    wave_slot(30, 2.0, 0);
    wave_slot(41, 2.4, 35);
    wave_slot(52, 2.0, 70);
}

module base_part() {
    difference() {
        shell_base();
        sensor_cable_holes();
        uno_side_ports();
        battery_charge_cutout();
    }

    board_standoffs(uno_pos, uno_holes);
    board_standoffs(tds_pos, [[3.5, 3.5], [39.5, 28.5]]);
    lid_posts_for_screws();

    battery_cradle();
    battery_end_stops();
}

module lid_part() {
    union() {
        difference() {
            shell_lid();
            lid_oled_window_and_holes();
            lid_screw_holes();
            lid_wave_pattern();
        }
        lid_oled_posts();
    }
}

module layout_helpers() {
    if (show_layout_helpers) {
        // Arduino
        %color([0.1, 0.5, 0.95, 0.35]) translate([uno_pos[0], uno_pos[1], uno_pos[2] + standoff_h]) cube([68.6, 53.4, 14]);

        // TDS
        %color([0.2, 0.9, 0.35, 0.35]) translate([tds_pos[0], tds_pos[1], tds_pos[2] + standoff_h]) cube([43, 32, 12]);

        // Bateria
        %color([0.95, 0.75, 0.15, 0.35])
            translate([battery_cradle_pos[0] + 4, battery_cradle_pos[1] + battery_cradle_w / 2, battery_cradle_pos[2] + battery_cradle_h - 0.2])
                rotate([0, 90, 0]) cylinder(h = bat_len, r = bat_d / 2);

        // Guias de saídas sensores
        %color([0.2, 0.9, 0.3, 0.45]) translate(cable_tds_pos) cube([cable_cut_depth, cable_tds_w, cable_tds_h]);
        %color([0.2, 0.9, 0.3, 0.45]) translate(cable_temp_pos) rotate([0, 90, 0]) cylinder(h = cable_cut_depth, d = cable_temp_d);
    }
}

if (part == "base") {
    base_part();
    layout_helpers();
}

if (part == "lid") {
    lid_part();
}

if (part == "assembled") {
    color("#1f2937") base_part();
    layout_helpers();
    translate([0, 0, base_h + 0.2]) color("#334155") lid_part();
}
