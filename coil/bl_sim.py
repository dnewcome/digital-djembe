#!/usr/bin/env python3
"""
Magnetostatic BL simulation for the planar-magnetic head driver (PLAN s6.4).

Consumes the coil geometry from coil_gen.py and computes the REAL force
factor BL by integrating the in-plane gap field B_perp along each trace:

    BL_axial = sum_runs  dir_run * integral( B_perp . dL )

where B_perp is the in-plane field component perpendicular to the local
trace (the component that crosses the conductor to make axial Lorentz
force), and dir_run alternates with the serpentine so contributions over
alternating-polarity gaps add coherently.

Field source: alternating-polarity N42 bar array (magpylib analytic
cuboids), with an optional steel-shell BACK-IRON modeled by the image
method (mirror magnets across the back plane reinforce the gap field).

This is the actual fabrication gate: it tells us whether the chosen
magnet pitch / grade / gap delivers the BL ~2-3 N/A the PLAN assumes,
and what to order against. magpylib v5 SI units: metres, tesla, amperes.
"""
import os
import sys
import numpy as np
import magpylib as mpl
from scipy.spatial.transform import Rotation as Rot

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coil_gen as cg

BR_N42 = 1.30           # T, N42 remanent polarization
BR_N52 = 1.45           # T, N52


def build_bars(p, coil, Br=BR_N42, back_iron=False, bar_height=None,
               halbach=False, halbach_dir=-1, halbach_start=0):
    """Magnet bar array under one coil (magpylib Collection, returned with nv).

    halbach=False : simple alternating +z/-z bars at every conductor gap.
    halbach=True  : bars at HALF pitch with magnetization rotating
                    [+z, +nv, -z, -nv] (period = 2 pitches, matching the
                    serpentine), which steers single-sided flux toward the
                    coil (+z). Needs ~2x as many bars, some in-plane-magnetized.
    Magnetization is given in the cuboid LOCAL frame (orientation rotates
    local-y -> nv, local-z -> z). Back-iron image flips the tangential
    components and preserves the normal one (high-mu boundary)."""
    bar_h = (bar_height if bar_height is not None else p.bar_width) / 1000.0  # m
    th = np.deg2rad(coil.center_deg + 90.0)
    nv = np.array([-np.sin(th), np.cos(th)])
    Lbar = (max(cg._polyline_len(r) for _, r in coil.runs) + 8.0) / 1000.0    # m
    ks = [k for k, _ in coil.runs]
    z_top = -p.gap_height / 1000.0          # bar top face below coil plane
    z_c = z_top - bar_h / 2.0
    z_back = z_top - bar_h
    rot = Rot.from_euler("z", th)            # long axis (local x) -> u, y -> nv
    bars = []

    def add(pol, s, w):
        cx, cy = s * nv[0], s * nv[1]
        bars.append(mpl.magnet.Cuboid(polarization=pol, dimension=(Lbar, w, bar_h),
                                      position=(cx, cy, z_c), orientation=rot))
        if back_iron:                        # high-mu image: flip tangential, keep z
            img = (-pol[0], -pol[1], pol[2])
            bars.append(mpl.magnet.Cuboid(polarization=img, dimension=(Lbar, w, bar_h),
                                          position=(cx, cy, 2 * z_back - z_c),
                                          orientation=rot))
    if halbach:
        w = p.bar_pitch / 2 / 1000.0 * 0.92
        seq = [(0, 0, Br), (0, halbach_dir * Br, 0),
               (0, 0, -Br), (0, -halbach_dir * Br, 0)]
        for n in range(2 * (min(ks) - 1), 2 * (max(ks) + 1) + 1):
            add(seq[(n + halbach_start) % 4], n * (p.bar_pitch / 2) / 1000.0, w)
    else:
        w = p.bar_width / 1000.0
        for j in range(min(ks) - 1, max(ks) + 1):
            add((0, 0, Br if j % 2 == 0 else -Br),
                (j + 0.5) * p.bar_pitch / 1000.0, w)
    return mpl.Collection(bars), nv


def best_halbach(p, coil, **kw):
    """Brute-force the Halbach phase (dir x start) that gives the most coherent
    BL — the registration that makes the serpentine forces add. Returns
    (BL_per_layer, coherence, |Bperp|, dir, start)."""
    best = (-1.0, 0.0, 0.0, -1, 0)
    for d in (+1, -1):
        for s in range(4):
            bl1, coh, bp = bl_for_coil(p, coil, halbach=True, halbach_dir=d,
                                       halbach_start=s, **kw)
            if bl1 > best[0]:
                best = (bl1, coh, bp, d, s)
    return best


def bl_for_coil(p, coil, **kw):
    """Return (BL_per_layer N/A, coherence 0..1, mean |B_perp| over gaps T)."""
    coll, nv = build_bars(p, coil, **kw)
    nv3 = np.array([nv[0], nv[1], 0.0])
    signed = absum = 0.0
    bperp_all = []
    for idx, (_, run) in enumerate(coil.runs):
        pts = np.c_[run / 1000.0, np.zeros(len(run))]        # m, coil plane z=0
        bperp = coll.getB(pts) @ nv3                         # T
        seg = np.linalg.norm(np.diff(run, axis=0), axis=1) / 1000.0
        bmid = 0.5 * (bperp[:-1] + bperp[1:])
        dir_run = 1.0 if idx % 2 == 0 else -1.0
        signed += dir_run * np.sum(bmid * seg)
        absum += np.sum(np.abs(bmid) * seg)
        bperp_all.append(bperp)
    bl1 = abs(signed)
    coh = abs(signed) / absum if absum else 0.0
    return bl1, coh, float(np.mean(np.abs(np.concatenate(bperp_all))))


def evaluate(p, label, **kw):
    coils = cg.build_coils(p)
    rings = sorted(set(c.ring for c in coils))
    name_of = ({0: "edge"} if len(rings) == 1
               else {0: "inner", 1: "outer"})
    rows = []
    for r in rings:
        c = next(x for x in coils if x.ring == r)
        name = name_of.get(r, f"ring{r}")
        bl1, coh, bperp = bl_for_coil(p, c, **kw)
        e = c.electrical()
        rows.append((name, c.n_turns, bperp, coh, bl1,
                     bl1 * p.n_layers, e["R_series"]))
    print(f"\n--- {label} : pitch {p.bar_pitch} mm, bar {p.bar_width} mm, "
          f"gap {p.gap_height} mm, {kw} ---")
    print(f"{'ring':<7}{'turns':>6}{'|Bperp|T':>10}{'coher':>7}"
          f"{'BL/layer':>10}{'BL_4ser':>9}{'R_4ser':>8}")
    for r in rows:
        print(f"{r[0]:<7}{r[1]:>6}{r[2]:>10.3f}{r[3]:>7.2f}"
              f"{r[4]:>10.3f}{r[5]:>9.2f}{r[6]:>8.1f}")
    return rows


def force_power_summary(BL, R, label):
    """What current/power each force target needs, and is it thermally OK.

    Sustain (the intended use, PLAN s6.4.1/s6.4.5): inject the ~2.4 mW
    mechanical/period a damped mode bleeds, at modal velocity
    v_rms = 2*pi*f*x / sqrt(2) (f=150 Hz, x=0.1 mm) -> F ~ 0.04 N rms.
    """
    print(f"\n  force/power @ {label}: BL {BL:.2f} N/A, R {R:.1f} ohm "
          f"(thermal ceiling ~2-3 W/coil continuous)")
    for F, what in ((0.04, "sustain a seeded mode"),
                    (0.2, "moderate liven"),
                    (1.0, "drive head hard")):
        I = F / BL
        P = I * I * R
        ok = "OK" if P < 2.0 else ("warm" if P < 4 else "TOO HOT")
        print(f"    {F:>4.2f} N ({what:<22}) -> {I:>5.2f} A rms, "
              f"{P*1000:>6.0f} mW  [{ok}]")


if __name__ == "__main__":
    base = cg.Params()    # 14" snare default

    print("=" * 64)
    print("BASELINE (edge ring x 4 quadrants: 6 mm pitch, N42, 2.5 mm gap)")
    print("=" * 64)
    evaluate(base, "N42, no back-iron")
    rows = evaluate(base, "N42 + steel back-iron", back_iron=True)
    force_power_summary(rows[-1][5], rows[-1][6], "edge quadrant + back-iron")

    print("\n" + "=" * 64)
    print("AGGRESSIVE (N52, 1.5 mm gap, 5 mm-tall bars, 6 mm pitch, back-iron)")
    print("=" * 64)
    agg = cg.Params(gap_height=1.5)
    rows_a = evaluate(agg, "N52, tall bars, tight gap",
                      Br=BR_N52, back_iron=True, bar_height=5.0)
    force_power_summary(rows_a[-1][5], rows_a[-1][6], "aggressive edge quadrant")

    print("\n" + "=" * 64)
    print("PITCH / GAP SWEEP  (edge quadrant, N42 + steel back-iron, 4-layer series)")
    print("target: BL 2-3 N/A, R 8-16 ohm")
    print("=" * 64)
    print(f"{'pitch':>6}{'bar':>6}{'gap':>6}{'turns':>7}"
          f"{'|Bperp|T':>10}{'BL_4ser':>9}{'R_4ser':>8}")
    for pitch in (3.0, 4.0, 6.0):
        for gap in (2.0, 3.0):
            p = cg.Params(bar_pitch=pitch, bar_width=pitch / 2.0,
                          gap_height=gap)
            coils = cg.build_coils(p)
            c = coils[0]                          # representative edge quadrant
            bl1, coh, bperp = bl_for_coil(p, c, back_iron=True)
            e = c.electrical()
            print(f"{pitch:>6.1f}{pitch/2:>6.1f}{gap:>6.1f}{c.n_turns:>7}"
                  f"{bperp:>10.3f}{bl1*p.n_layers:>9.2f}{e['R_series']:>8.1f}")

    print("\n" + "=" * 64)
    print("MAGNET ARRAY: simple alternating vs HALBACH (single-sided)")
    print("the single-sided mitigation -- steer flux up to the coil")
    print("=" * 64)
    coil = cg.build_coils(base)[0]
    n = base.n_layers
    simple = bl_for_coil(base, coil)
    simple_bi = bl_for_coil(base, coil, back_iron=True)
    halb = best_halbach(base, coil)
    halb_bi = best_halbach(base, coil, back_iron=True)
    print(f"{'config':<26}{'|Bperp|mT':>10}{'coher':>7}{'BL_4ser':>9}{'vs simple':>10}")
    b0 = simple[0] * n
    for name, r in [("simple", simple), ("simple + back-iron", simple_bi),
                    (f"HALBACH (dir{halb[3]:+d},ph{halb[4]})", halb),
                    ("HALBACH + back-iron", halb_bi)]:
        print(f"{name:<26}{r[2]*1000:>10.0f}{r[1]:>7.2f}"
              f"{r[0]*n:>9.2f}{r[0]*n/b0:>9.2f}x")
    print("note: Halbach needs ~2x the bars (half-pitch), some in-plane-"
          "magnetized; coherence must stay ~1.0 or the registration is wrong.")
