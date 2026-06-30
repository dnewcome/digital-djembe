#!/usr/bin/env python3
"""
2-D FDTD membrane sim for the Track B gap-clearance gate (trustworthy).

The lumped modal model (gap_sim.py) overestimates peak deflection ~8x
because a truncated mode set can't localize a transient strike dip. This
solves the actual clamped-membrane wave equation in space and time, so the
local dimple and its propagation are resolved correctly:

    u_tt = c^2 (u_xx + u_yy) + f/sigma ,   u = 0 on r >= R   (clamped rim)

A strike is a half-sine force pulse (impulse J, contact time tau) over a
small contact disk at the strike point. We track the peak |u| reached at
every cell, then report the worst-azimuth deflection at each radius.

Key physical point for the gap: the centre deflects most, but there are NO
magnets under the centre. The magnet plate sits under the coil annulus
(0.55-0.85R), so only the deflection THERE sets the minimum gap.

Units SI. Calibrate: a hard hit should give centre peak ~2-4 mm.
"""
import numpy as np

HEAD_D = 0.356
R = HEAD_D / 2
SIGMA = 0.35                 # kg/m^2 (~10 mil Mylar)
F0 = 200.0                  # Hz fundamental
J01 = 2.4048
C = 2 * np.pi * F0 * R / J01   # wave speed from f0
T_MEM = C ** 2 * SIGMA          # tension N/m

RING_IN, RING_OUT = 0.55 * R, 0.85 * R
J_IMP = 0.4                 # N*s hard strike
TAU = 3e-3                  # s contact time
A_CONTACT = 0.006           # m contact radius (~stick tip / finger)

# Mylar elastic props for geometric (tension-stiffening) nonlinearity
E_MYLAR = 4.5e9             # Pa
H_MYLAR = 250e-6            # m (~10 mil)
NU = 0.38
K_NL = E_MYLAR * H_MYLAR / (2 * (1 - NU ** 2))   # Berger stiffening coeff, N/m

N = 181
T_SIM = 0.035               # s


def simulate(strike_r, label, nonlinear=True):
    """Clamped membrane FDTD. nonlinear=True adds Berger tension-stiffening:
    a hard strike stretches the head, raising its own tension and resisting
    further deflection (the physics the linear model misses)."""
    x = np.linspace(-R, R, N)
    dx = x[1] - x[0]
    X, Y = np.meshgrid(x, x)
    rr = np.hypot(X, Y)
    interior = rr < (R - dx)
    # dt sized so we stay stable even if tension stiffens up to ~12x
    dt = 0.9 * dx / (np.sqrt(12) * C * np.sqrt(2))
    kmax = 0.5                                    # CFL ceiling on c_eff^2 dt^2/dx^2

    contact = np.hypot(X - strike_r, Y) < A_CONTACT
    A_c = contact.sum() * dx * dx
    p0 = J_IMP * np.pi / (2 * TAU * A_c)

    u = np.zeros((N, N)); u_prev = np.zeros((N, N)); peak = np.zeros((N, N))
    nsteps = int(T_SIM / dt)
    Tmax_seen = T_MEM
    for s in range(nsteps):
        t = s * dt
        if nonlinear:
            ux = (np.roll(u, -1, 1) - np.roll(u, 1, 1)) / (2 * dx)
            uy = (np.roll(u, -1, 0) - np.roll(u, 1, 0)) / (2 * dx)
            grad2 = np.mean((ux ** 2 + uy ** 2)[interior])   # area-avg |grad u|^2
            T_eff = T_MEM + K_NL * grad2
        else:
            T_eff = T_MEM
        c2 = T_eff / SIGMA
        k = c2 * dt * dt / (dx * dx)
        k = min(k, kmax)                          # never violate CFL
        Tmax_seen = max(Tmax_seen, T_eff)
        lap = (np.roll(u, 1, 0) + np.roll(u, -1, 0)
               + np.roll(u, 1, 1) + np.roll(u, -1, 1) - 4 * u)
        f = np.zeros((N, N))
        if t < TAU:
            f[contact] = p0 * np.sin(np.pi * t / TAU)
        u_next = 2 * u - u_prev + k * lap + (dt * dt / SIGMA) * f
        u_next[~interior] = 0.0
        peak = np.maximum(peak, np.abs(u_next))
        u_prev, u = u, u_next

    rad = rr[interior]; pk = peak[interior]
    def at(r0, w=dx):
        m = np.abs(rad - r0) < w
        return pk[m].max() * 1000 if m.any() else 0.0
    return {"label": label, "centre": at(0.0), "inner": at(RING_IN),
            "outer": at(RING_OUT), "global_peak": pk.max() * 1000,
            "dt": dt, "dx": dx, "Tmax_x": Tmax_seen / T_MEM}


if __name__ == "__main__":
    print(f"14\" snare Mylar: R {R*1000:.0f} mm, f0 {F0:.0f} Hz, "
          f"c {C:.0f} m/s, tension {T_MEM:.0f} N/m")
    print(f"hard strike J {J_IMP} N*s, tau {TAU*1000:.0f} ms, "
          f"contact r {A_CONTACT*1000:.0f} mm")
    print(f"coil rings: inner {RING_IN*1000:.0f} mm, outer {RING_OUT*1000:.0f} mm")
    lin = simulate(0.0, "centre", nonlinear=False)
    print(f"\nLINEAR model, centre strike: centre dip {lin['centre']:.1f} mm "
          f"(unphysical -> nonlinear regime)")

    print(f"\nNONLINEAR (Berger tension-stiffening):")
    print(f"{'strike at':<16}{'centre mm':>11}{'@inner mm':>11}"
          f"{'@outer mm':>11}{'peak mm':>10}{'T_eff x':>9}")
    runs = []
    for r_s, lab in [(0.0, "centre"), (0.30 * R, "0.30R"),
                     (RING_IN, "inner ring"), (RING_OUT, "outer ring")]:
        res = simulate(r_s, lab)
        runs.append(res)
        print(f"{lab:<16}{res['centre']:>11.2f}{res['inner']:>11.2f}"
              f"{res['outer']:>11.2f}{res['global_peak']:>10.2f}{res['Tmax_x']:>9.1f}")

    worst_in = max(r["inner"] for r in runs)
    worst_out = max(r["outer"] for r in runs)
    print(f"\nMagnets sit ONLY under the coil annulus (0.55-0.85R), so the "
          f"\ngap is set by deflection THERE, not at the (magnet-free) centre:")
    print(f"  worst deflection at inner-ring radius: {worst_in:.2f} mm")
    print(f"  worst deflection at outer-ring radius: {worst_out:.2f} mm")
    print(f"\n  -> min gap (worst + 0.5 mm margin): inner {worst_in+0.5:.1f} mm, "
          f"outer {worst_out+0.5:.1f} mm")
    print(f"  grid dx {runs[0]['dx']*1000:.2f} mm, dt {runs[0]['dt']*1e6:.1f} us")
