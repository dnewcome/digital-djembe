#!/usr/bin/env python3
"""
Planar-magnetic coil geometry generator for the hybrid-drum head driver.

Track B (PLAN.md s6): 2 concentric rings (radial segmentation) x 4 azimuthal
wedges = 8 independent serpentine coils on a flex PCB bonded to the head.

Topology = parallel-bar planar-magnetic (PLAN s6.2, marked "chosen"):
each coil is a serpentine whose straight runs sit OVER the gaps between
alternating-polarity magnet bars, where the field is in-plane and the
Lorentz force F = B I L is axial (drives the head perpendicular to itself).

Bars are oriented PER-QUADRANT (tangential to each wedge's bisector) so the
4 wedges stay 90-deg symmetric and the messy bar-orientation boundary lands
in the dead gutter between wedges (PLAN reconciliation of s6.2 vs s6.3).

Outputs:
  coil/coil_preview.svg  - geometry visual check
  stdout                 - electrical report (R, BL, force) vs PLAN s6.4

build_coils() exposes the trace polylines so the magpylib magnetostatic
sim can integrate B x I along the real geometry (the actual fab gate).
"""
from dataclasses import dataclass
import numpy as np

RHO_CU = 1.68e-8        # ohm*m, annealed copper
T_1OZ = 35e-6           # m, 1 oz copper finished thickness


@dataclass
class Params:
    name: str = "14in-snare"
    head_d: float = 356.0           # 14" head OD, mm (R = 178)
    rings: tuple = ((0.92, 0.055),)  # outer ~20 mm rim band (center_frac, halfwidth_frac of R)
    n_wedges: int = 4               # 4 azimuthal QUADRANTS -> 4 coils
    gutter_deg: float = 6.0         # dead angular gap between quadrants
    bar_pitch: float = 6.0          # mm, bar + gap (sets serpentine pitch)
    bar_width: float = 3.0          # mm
    trace_w: float = 0.30           # mm
    trace_space: float = 0.20       # mm (info; pitch is set by bars)
    n_layers: int = 4
    copper_oz: float = 2.0
    gap_height: float = 2.5         # mm, coil plane to magnet face
    B_gap: float = 0.40             # T, in-plane field over the gap
    sample_mm: float = 0.5          # geometry sampling step

    @property
    def R(self):
        return self.head_d / 2.0


def _polyline_len(pts):
    if len(pts) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))


def _longest_run(pts, inside):
    best = None
    n = len(inside)
    i = 0
    while i < n:
        if inside[i]:
            j = i
            while j + 1 < n and inside[j + 1]:
                j += 1
            if best is None or (j - i) > (best[1] - best[0]):
                best = (i, j)
            i = j + 1
        else:
            i += 1
    if best is None:
        return None
    return pts[best[0]:best[1] + 1]


@dataclass
class Coil:
    p: Params
    wedge: int
    ring: int
    center_deg: float
    span_deg: float
    r0: float
    r1: float
    runs: list          # list of (k, ndarray(N,2)) sorted by k

    @property
    def n_turns(self):
        return len(self.runs)

    def serpentine(self):
        """Ordered polylines forming one continuous snake (alternating run dir)."""
        path, flip = [], False
        for _, run in self.runs:
            path.append(run[::-1] if flip else run)
            flip = not flip
        return path

    def length_field_mm(self):
        """Conductor length over the gaps (the part that makes axial force)."""
        return sum(_polyline_len(run) for _, run in self.runs)

    def length_total_mm(self):
        """Field runs + serpentine end connectors."""
        path = self.serpentine()
        total = sum(_polyline_len(seg) for seg in path)
        for a, b in zip(path[:-1], path[1:]):
            total += float(np.linalg.norm(b[0] - a[-1]))
        return total

    def electrical(self):
        p = self.p
        t_cu = T_1OZ * p.copper_oz
        L1 = self.length_total_mm() / 1000.0          # m, one layer
        Lf1 = self.length_field_mm() / 1000.0         # m, in-field, one layer
        w = p.trace_w / 1000.0                          # m
        R1 = RHO_CU * L1 / (w * t_cu)
        n = p.n_layers
        return {
            "turns": self.n_turns,
            "len_field_m": Lf1,
            "R_1layer": R1,
            "R_series": R1 * n,
            "R_parallel": R1 / n,
            "R_2s2p": R1,                               # 2 series x 2 parallel
            "BL_1layer": p.B_gap * Lf1,
            "BL_series": p.B_gap * Lf1 * n,
            "BL_parallel": p.B_gap * Lf1,
            "BL_2s2p": p.B_gap * Lf1 * 2,
        }


def _wedges(p):
    span = 360.0 / p.n_wedges - p.gutter_deg
    for i in range(p.n_wedges):
        yield i, 360.0 / p.n_wedges * i, span


def _bands(p):
    for j, (cf, hwf) in enumerate(p.rings):
        yield j, (cf - hwf) * p.R, (cf + hwf) * p.R


def build_coils(p):
    coils = []
    for i, c, span in _wedges(p):
        th = np.deg2rad(c + 90.0)                       # bar dir = tangential
        u = np.array([np.cos(th), np.sin(th)])
        nv = np.array([-np.sin(th), np.cos(th)])
        cc = np.deg2rad(c)
        half = np.deg2rad(span / 2.0)
        for j, r0, r1 in _bands(p):
            ts = np.arange(-r1, r1 + p.sample_mm, p.sample_mm)
            kmax = int(np.ceil(r1 / p.bar_pitch)) + 1
            runs = []
            for k in range(-kmax, kmax + 1):
                s = k * p.bar_pitch
                pts = s * nv[None, :] + ts[:, None] * u[None, :]
                rr = np.hypot(pts[:, 0], pts[:, 1])
                ang = np.arctan2(pts[:, 1], pts[:, 0])
                dang = np.arctan2(np.sin(ang - cc), np.cos(ang - cc))
                inside = (rr >= r0) & (rr <= r1) & (np.abs(dang) <= half)
                run = _longest_run(pts, inside)
                if run is not None and len(run) >= 2:
                    runs.append((k, run))
            if runs:
                runs.sort(key=lambda kr: kr[0])
                coils.append(Coil(p, i, j, c, span, r0, r1, runs))
    return coils


# ---------------------------------------------------------------- SVG preview
def write_svg(p, coils, out_path="coil/coil_preview.svg"):
    R = p.R
    pad = 12
    side = 2 * (R + pad)
    wedge_colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]

    def xy(pt):                     # model mm -> svg (flip y, center)
        return pt[0] + side / 2, side / 2 - pt[1]

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="0 0 {side:.1f} {side:.1f}" '
           f'width="{side:.1f}mm" height="{side:.1f}mm">']
    out.append(f'<rect width="{side:.1f}" height="{side:.1f}" fill="#fafafa"/>')
    cx = cy = side / 2
    # head outline + ring bands
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" '
               f'stroke="#bbb" stroke-width="0.8"/>')
    for _, r0, r1 in _bands(p):
        for rr in (r0, r1):
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" '
                       f'stroke="#ddd" stroke-width="0.4" '
                       f'stroke-dasharray="2 2"/>')
    # faint magnet bars per wedge, clipped to the active ring annulus
    band_lo = min(r0 for _, r0, _ in _bands(p))
    band_hi = max(r1 for _, _, r1 in _bands(p))
    for i, c, span in _wedges(p):
        th = np.deg2rad(c + 90.0)
        u = np.array([np.cos(th), np.sin(th)])
        nv = np.array([-np.sin(th), np.cos(th)])
        cc, half = np.deg2rad(c), np.deg2rad(span / 2)
        ts = np.arange(-R, R, p.sample_mm)
        kmax = int(np.ceil(R / p.bar_pitch)) + 1
        for k in range(-kmax, kmax + 1):
            s = k * p.bar_pitch + p.bar_pitch / 2.0     # bar center
            pts = s * nv[None, :] + ts[:, None] * u[None, :]
            rr = np.hypot(pts[:, 0], pts[:, 1])
            ang = np.arctan2(pts[:, 1], pts[:, 0])
            dang = np.arctan2(np.sin(ang - cc), np.cos(ang - cc))
            run = _longest_run(pts, (rr >= band_lo) & (rr <= band_hi)
                               & (np.abs(dang) <= half))
            if run is None or len(run) < 2:
                continue
            col = "#f4c2c2" if k % 2 == 0 else "#c2d4f4"   # N / S tint
            a, b = xy(run[0]), xy(run[-1])
            out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" '
                       f'x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
                       f'stroke="{col}" stroke-width="{p.bar_width}" '
                       f'stroke-linecap="round" opacity="0.5"/>')
    # coil serpentines
    for coil in coils:
        col = wedge_colors[coil.wedge % len(wedge_colors)]
        opacity = 1.0 if coil.ring == 0 else 0.6
        serp = coil.serpentine()
        d = []
        for seg in serp:
            for n, pt in enumerate(seg):
                x, y = xy(pt)
                d.append(("M" if not d else "L") + f"{x:.2f} {y:.2f}")
        out.append(f'<path d="{" ".join(d)}" fill="none" stroke="{col}" '
                   f'stroke-width="{p.trace_w*2.2:.2f}" opacity="{opacity}" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
    out.append("</svg>")
    with open(out_path, "w") as f:
        f.write("\n".join(out))
    return out_path


# ----------------------------------------------------------------- report
def report(p, coils):
    print(f"=== Coil geometry: {p.name}  (head {p.head_d:.0f} mm, R {p.R:.0f} mm) ===")
    print(f"{p.n_wedges} quadrants x {len(p.rings)} ring = {len(coils)} coils | "
          f"bar pitch {p.bar_pitch} mm | trace {p.trace_w} mm | "
          f"{p.copper_oz:.0f} oz x {p.n_layers} layers | gap {p.gap_height} mm | "
          f"B {p.B_gap} T")
    print(f"\n{'coil':<14}{'turns':>6}{'Lfield(m)':>10}"
          f"{'R_ser':>8}{'R_par':>8}{'R_2s2p':>8}"
          f"{'BL_ser':>8}{'BL_2s2p':>9}")
    agg = {}
    for coil in coils:
        e = coil.electrical()
        tag = f"quad{coil.wedge}"
        print(f"{tag:<14}{e['turns']:>6}{e['len_field_m']:>10.2f}"
              f"{e['R_series']:>8.1f}{e['R_parallel']:>8.1f}{e['R_2s2p']:>8.1f}"
              f"{e['BL_series']:>8.2f}{e['BL_2s2p']:>9.2f}")
        agg.setdefault(coil.ring, []).append(e)
    print("\nPLAN s6.4 targets: R 8-16 ohm/segment, BL 2-3 N/A, "
          "I_rms ~0.3 A sustain.")
    # force at sustain current using 2s2p as a representative wiring
    for ring, es in sorted(agg.items()):
        bl = np.mean([e["BL_2s2p"] for e in es])
        r = np.mean([e["R_2s2p"] for e in es])
        print(f"  edge ring ({len(es)} quadrant coils): "
              f"mean BL_2s2p {bl:.2f} N/A -> {bl*0.3:.2f} N at 0.3 A; "
              f"R {r:.1f} ohm; P {0.3**2*r*1000:.0f} mW at 0.3 A_rms")


if __name__ == "__main__":
    p = Params()
    coils = build_coils(p)
    svg = write_svg(p, coils)
    report(p, coils)
    print(f"\nwrote {svg}")
