#!/usr/bin/env python3
"""Single-sided vs double-sided vs Halbach — visualize what the magnet
arrangement does to the in-plane field B_perp the coil feels (and thus BL).

The coil makes axial force from the IN-PLANE field component (Bx here, since
traces run along y) at the coil plane. This maps that field for:
  1. single-sided, simple alternating bars  (what we're forced into: the
     playing surface is on top, so no magnets above the head)
  2. single-sided HALBACH array             (concentrates flux toward the
     coil side -> the key single-sided mitigation)
  3. double-sided push-pull                 (headphone ideal; needs magnets
     on BOTH sides -> not possible here)

Prints the coil-plane mean |B_perp| and the BL ratio vs case 1.
Writes coil/field_compare.png. magpylib v5 SI units (m, T).
"""
import numpy as np
import magpylib as mpl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BR = 1.30                # N42
PITCH = 6e-3
BAR = 3e-3               # square cross-section
BLEN = 40e-3            # long axis (y)
GAP = 2e-3              # coil plane (z=0) to magnet face
ZC = GAP + BAR / 2     # magnet-bar centre offset from coil plane
KS = range(-4, 5)      # 9 bars


def _cuboid(pol, x, z):
    return mpl.magnet.Cuboid(polarization=pol, dimension=(BAR, BLEN, BAR),
                             position=(x, 0, z))


def build(kind, halbach_dir=+1, top_sign=+1):
    bars = []
    for k in KS:
        x = k * PITCH
        if kind == "halbach":
            seq = [(0, 0, BR), (halbach_dir * BR, 0, 0),
                   (0, 0, -BR), (-halbach_dir * BR, 0, 0)]
            bars.append(_cuboid(seq[k % 4], x, -ZC))
        else:
            bars.append(_cuboid((0, 0, BR if k % 2 == 0 else -BR), x, -ZC))
        if kind == "double":                       # second array above the coil
            # push-pull: top polarity chosen so the in-plane fields ADD at z=0
            bars.append(_cuboid((0, 0, top_sign * (BR if k % 2 == 0 else -BR)),
                                x, +ZC))
    return mpl.Collection(bars)


def field(coll, xs, zs):
    X, Z = np.meshgrid(xs, zs)
    pts = np.c_[X.ravel(), np.zeros(X.size), Z.ravel()]
    B = coll.getB(pts).reshape(zs.size, xs.size, 3)
    return B[..., 0], B[..., 2]                     # Bx (in-plane), Bz


def coilplane_bperp(coll, xs):
    pts = np.c_[xs, np.zeros(xs.size), np.zeros(xs.size)]  # z=0 coil plane
    return coll.getB(pts)[:, 0]                     # Bx = B_perp


if __name__ == "__main__":
    xs = np.linspace(-15e-3, 15e-3, 151)
    zs = np.linspace(-7e-3, 7e-3, 81)
    central = np.abs(xs) <= 9e-3                     # avoid edge bars

    # pick the Halbach rotation / push-pull top polarity that maximize the
    # in-plane field at the coil plane (z=0)
    hdir = max((+1, -1), key=lambda d:
               np.mean(np.abs(coilplane_bperp(build("halbach", d), xs)[central])))
    tsgn = max((+1, -1), key=lambda s:
               np.mean(np.abs(coilplane_bperp(build("double", top_sign=s), xs)[central])))

    configs = [("single-sided\n(simple alternating)", build("single")),
               (f"single-sided HALBACH\n(flux steered up)", build("halbach", hdir)),
               ("double-sided push-pull\n(can't do: magnets on top)",
                build("double", top_sign=tsgn))]

    fig, axs = plt.subplots(1, 3, figsize=(15, 5.2), sharex=True, sharey=True)
    base = None
    for ax, (name, coll) in zip(axs, configs):
        Bx, Bz = field(coll, xs, zs)
        mag = np.hypot(Bx, Bz)
        bp = np.mean(np.abs(coilplane_bperp(coll, xs)[central]))
        if base is None:
            base = bp
        pcm = ax.pcolormesh(xs * 1e3, zs * 1e3, np.abs(Bx), cmap="magma",
                            shading="gouraud", vmin=0, vmax=0.45)
        ax.streamplot(xs * 1e3, zs * 1e3, Bx, Bz, color="white",
                      density=1.1, linewidth=0.5, arrowsize=0.6)
        # draw magnet bars
        for k in KS:
            for zc in ([-ZC, ZC] if "double" in name else [-ZC]):
                ax.add_patch(Rectangle(((k*PITCH - BAR/2)*1e3, (zc - BAR/2)*1e3),
                                       BAR*1e3, BAR*1e3, color="#39c", alpha=.85))
        ax.axhline(0, color="#0f0", lw=1.4, ls="--")     # coil plane
        ax.text(-14, 0.6, "coil plane", color="#0f0", fontsize=8)
        ax.set_title(f"{name}\nmean |B_perp| at coil = {bp*1000:.0f} mT "
                     f"(BL x{bp/base:.2f})", fontsize=10)
        ax.set_xlabel("x across bars (mm)")
        ax.set_ylim(-7, 7)
    axs[0].set_ylabel("z, height (mm)")
    fig.colorbar(pcm, ax=axs, label="|B_perp| (T)", shrink=0.8)
    fig.suptitle("What 'single-sided' costs us: in-plane field the coil feels "
                 "(brighter = more force)", fontsize=12)
    fig.savefig("coil/field_compare.png", dpi=120, bbox_inches="tight")

    print("coil-plane mean |B_perp| (the BL driver):")
    for name, coll in configs:
        bp = np.mean(np.abs(coilplane_bperp(coll, xs)[central]))
        print(f"  {name.splitlines()[0]:<26} {bp*1000:5.0f} mT   "
              f"BL x{bp/base:.2f}")
    print(f"(Halbach rotation dir = {hdir:+d}; wrote coil/field_compare.png)")
