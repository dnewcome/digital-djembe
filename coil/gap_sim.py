#!/usr/bin/env python3
"""
Head-deflection vs magnet-gap analytic first cut (Track B clearance gate).

The BL sim wants the magnet gap as TIGHT as possible (force ~1/gap). But the
Mylar head deflects several mm under a hard strike; if the coil annulus dips
more than the gap, the head SLAPS the magnet array. This sets the MINIMUM
gap, which fights the force requirement. This script finds that minimum.

Model: clamped circular membrane, modal (Bessel) decomposition. A strike is
a half-sine force pulse (impulse J, contact time tau) at radius r_s; each
mode's peak residual displacement is the exact undamped Duhamel response,
which gives the right temporal roll-off (a finite-duration hit can't excite
modes whose period << tau). The clearance envelope is the conservative
sum Sum_i |q_i,peak * psi_i(r)| along the strike azimuth (worst radial line).

The robust, parameter-free output is the RATIO of annulus deflection to
centre deflection (set purely by mode shapes); the hit hardness (J, tau)
only scales the absolute mm, and is calibrated to a hard hit (~few mm centre).

Units: SI. Bessel via scipy.special.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.special import jn, jn_zeros

# ---- drum (14" snare, Mylar batter) -------------------------------------
HEAD_D = 0.356            # m
R = HEAD_D / 2
SIGMA = 0.35             # kg/m^2, ~10 mil Mylar
F0 = 200.0              # Hz, fundamental (snare batter, tunable)

# ---- coil rings (from coil_gen: 0.55R inner, 0.85R outer) ----------------
RING_IN, RING_OUT = 0.55 * R, 0.85 * R

# ---- strike --------------------------------------------------------------
J_IMP = 0.4             # N*s impulse (hard stick hit: ~50 g, ~4 m/s, rebound)
TAU = 3e-3              # s contact time (stick on coated head)

# first modes (m, n)
MODES = [(0, 1), (1, 1), (2, 1), (0, 2), (3, 1), (1, 2), (4, 1), (2, 2), (0, 3)]


def mode_table():
    j01 = jn_zeros(0, 1)[0]
    rows = []
    for (m, n) in MODES:
        jmn = jn_zeros(m, n)[n - 1]
        w = 2 * np.pi * F0 * (jmn / j01)
        phi = 2 * np.pi if m == 0 else np.pi          # azimuthal integral
        M = SIGMA * phi * (R ** 2 / 2) * jn(m + 1, jmn) ** 2
        rows.append((m, n, jmn, w, M))
    return rows


def half_sine_residual(J, tau, w):
    """Peak residual modal displacement-per-(M*w) of a half-sine force pulse."""
    F0p = J * np.pi / (2 * tau)
    t = np.linspace(0, tau, 2000)
    f = F0p * np.sin(np.pi * t / tau)
    A = np.trapezoid(f * np.cos(w * t), t)
    B = np.trapezoid(f * np.sin(w * t), t)
    return np.hypot(A, B)            # = |integral F e^{-iwt}|, the SRS residual


def deflection_profile(r_s, rgrid, modes):
    """Conservative |displacement| envelope along the strike azimuth."""
    j01 = modes[0][2]
    W = np.zeros_like(rgrid)
    for (m, n, jmn, w, M) in modes:
        psi_s = jn(m, jmn * r_s / R)                 # mode shape at strike
        qpk = half_sine_residual(J_IMP, TAU, w) * abs(psi_s) / (M * w)
        W += qpk * np.abs(jn(m, jmn * rgrid / R))    # |psi| at field radius
    return W


if __name__ == "__main__":
    modes = mode_table()
    c = 2 * np.pi * F0 * R / modes[0][2]
    print(f"14\" snare Mylar head: R {R*1000:.0f} mm, sigma {SIGMA} kg/m^2, "
          f"f0 {F0:.0f} Hz -> wave speed {c:.0f} m/s, tension {c**2*SIGMA:.0f} N/m")
    print(f"hard strike: impulse {J_IMP} N*s, contact {TAU*1000:.0f} ms")
    print(f"coil rings: inner {RING_IN*1000:.0f} mm (0.55R), "
          f"outer {RING_OUT*1000:.0f} mm (0.85R)\n")

    rgrid = np.linspace(0, R, 400)
    strikes = [("centre", 0.0), ("0.30R", 0.30 * R), ("inner ring 0.55R", RING_IN),
               ("0.70R", 0.70 * R), ("outer ring 0.85R", RING_OUT)]

    def at(W, rr):
        return W[np.argmin(np.abs(rgrid - rr))]

    print(f"{'strike pos':<18}{'centre mm':>10}{'@inner mm':>11}"
          f"{'@outer mm':>11}{'peak mm':>9}")
    profiles = {}
    for name, r_s in strikes:
        W = deflection_profile(r_s, rgrid, modes) * 1000   # mm
        profiles[name] = W
        print(f"{name:<18}{at(W,0):>10.2f}{at(W,RING_IN):>11.2f}"
              f"{at(W,RING_OUT):>11.2f}{W.max():>9.2f}")

    # clearance verdict per striking discipline
    play_center = max(profiles[n][np.argmin(np.abs(rgrid-RING_IN))]
                      for n in ("centre", "0.30R"))           # hits inside inner ring
    play_center_o = max(profiles[n][np.argmin(np.abs(rgrid-RING_OUT))]
                        for n in ("centre", "0.30R"))
    hit_anywhere_in = max(profiles[n][np.argmin(np.abs(rgrid-RING_IN))]
                          for n in profiles)
    hit_anywhere_out = max(profiles[n][np.argmin(np.abs(rgrid-RING_OUT))]
                           for n in profiles)
    print("\nminimum gap needed (deflection + 0.5 mm margin):")
    print(f"  if player strikes only INSIDE the inner ring (centre play):")
    print(f"     inner-ring magnets > {play_center+0.5:.1f} mm, "
          f"outer-ring magnets > {play_center_o+0.5:.1f} mm")
    print(f"  if player strikes ANYWHERE over the coil:")
    print(f"     inner-ring magnets > {hit_anywhere_in+0.5:.1f} mm, "
          f"outer-ring magnets > {hit_anywhere_out+0.5:.1f} mm")

    # plot
    fig, ax = plt.subplots(figsize=(8, 5))
    for name, _ in strikes:
        ax.plot(rgrid / R, profiles[name], label=f"strike {name}")
    for rr, lab in ((RING_IN, "inner coil"), (RING_OUT, "outer coil")):
        ax.axvline(rr / R, color="k", ls=":", lw=0.8)
        ax.text(rr / R, ax.get_ylim()[1]*0.95, lab, rotation=90,
                va="top", ha="right", fontsize=8)
    for g in (1.5, 2.0, 3.0):
        ax.axhline(g, color="r", ls="--", lw=0.6)
        ax.text(0.01, g, f"{g} mm gap", color="r", va="bottom", fontsize=8)
    ax.set_xlabel("radius / R"); ax.set_ylabel("peak head deflection (mm)")
    ax.set_title("Hard-strike head deflection vs coil rings and candidate gaps")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig("coil/gap_deflection.png", dpi=130)
    print("\nwrote coil/gap_deflection.png")
