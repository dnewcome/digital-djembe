#!/usr/bin/env python3
"""Force-direction overlay — validate the coil geometry visually.

Draws every coil trace coloured by the AXIAL Lorentz-force direction it
produces in the real magnet field (B from magpylib, F ~ I_dir x B_perp). If
every trace pushes the SAME way (one colour), the serpentine is phased
correctly over the alternating-polarity bars — the picture version of
bl_sim's coherence=1.00, i.e. Fostex "Regular Phase" (whole diaphragm moves
together). A few opposite-colour segments would mean a phasing bug.

Writes coil/coil_forcemap.png.
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coil_gen as cg
import bl_sim as bl


def main():
    p = cg.Params()
    coils = cg.build_coils(p)
    fig, ax = plt.subplots(figsize=(8, 8))
    total = up = 0.0
    for coil in coils:
        coll, nv = bl.build_bars(p, coil, back_iron=False)
        nv3 = np.array([nv[0], nv[1], 0.0])
        # magnet bars: long axis, coloured by polarity (N=+z red, S=-z blue)
        for src in coll.sources:
            pos = np.asarray(src.position) * 1000.0
            dim = np.asarray(src.dimension) * 1000.0
            half = src.orientation.as_matrix() @ np.array([dim[0] / 2, 0, 0])
            a, b = pos[:2] - half[:2], pos[:2] + half[:2]
            c = "#e8a0a0" if src.polarization[2] > 0 else "#a0b4e8"
            ax.plot([a[0], b[0]], [a[1], b[1]], color=c, lw=2.6, alpha=0.45,
                    solid_capstyle="round", zorder=1)
        # traces: coloured by axial force sign (I_dir alternates per serpentine run)
        for idx, (k, run) in enumerate(coil.runs):
            pts3 = np.c_[run / 1000.0, np.zeros(len(run))]
            bperp = coll.getB(pts3) @ nv3
            cdir = 1.0 if idx % 2 == 0 else -1.0
            fz = cdir * bperp                              # axial force per point
            for i in range(1, len(run)):
                seglen = float(np.linalg.norm(run[i] - run[i - 1]))
                s = 0.5 * (fz[i] + fz[i - 1])
                ax.plot(run[i - 1:i + 1, 0], run[i - 1:i + 1, 1],
                        color="#2ca02c" if s > 0 else "#d62728", lw=1.7, zorder=3)
                total += seglen
                up += seglen if s > 0 else 0.0
    coherent = max(up, total - up) / total * 100.0
    ax.legend([Line2D([0], [0], color="#2ca02c", lw=3),
               Line2D([0], [0], color="#d62728", lw=3),
               Line2D([0], [0], color="#e8a0a0", lw=3),
               Line2D([0], [0], color="#a0b4e8", lw=3)],
              ["trace force +z (up)", "trace force -z (down)",
               "magnet N (+z)", "magnet S (-z)"], loc="lower right", fontsize=9)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Coil force-direction overlay — "
                 f"{coherent:.0f}% of trace length pushes one way (coherent)\n"
                 "all-one-colour traces = serpentine phased right vs the bars "
                 "(Fostex 'Regular Phase')")
    fig.tight_layout()
    fig.savefig("coil/coil_forcemap.png", dpi=120)
    print(f"wrote coil/coil_forcemap.png  ({coherent:.1f}% of trace length "
          f"produces force in one direction -> geometry coherent)")


if __name__ == "__main__":
    main()
