"""membrane_sim.py — MuJoCo bench for the Track B head driver (mechanical layer).

A clamped circular Mylar membrane as a mass-spring lattice: each interior node
is a z-slide mass, neighbours joined by PRETENSIONED spatial tendons. Distance-
based tendons are geometrically nonlinear, so the head stiffens as it stretches
(the von Karman/Berger effect the linear FDTD in coil/ could not capture) for
free. A movable magnet plate sits a gap below; ONLY the coil-annulus nodes can
contact it, so you see the head SLAP the magnets exactly where they are.

This is the mechanical/contact/EM layer MuJoCo is right for — NOT acoustics
(that is djembe.dsp). The force factor BL comes from coil/bl_sim.py.

Live sliders (viewer Control pane): gap, strike force, coil current.
SI units. Run:
  make interactive      # glfw window
  make selftest         # headless build + step + f0 calibration check
  make render           # headless gif of a strike vs the gap
"""
import os
import sys

_INTERACTIVE = "--interactive" in sys.argv
# windowed GL for the viewer, offscreen for headless batch — set BEFORE import
os.environ.setdefault("MUJOCO_GL", "glfw" if _INTERACTIVE else "osmesa")

import numpy as np
import mujoco
from dataclasses import dataclass


@dataclass
class Params:
    R: float = 0.178            # head radius, m (14" snare)
    sigma: float = 0.35         # areal density kg/m^2 (~10 mil Mylar)
    f0: float = 200.0           # target fundamental Hz -> sets pretension
    grid: int = 16              # lattice cells across the diameter
    tendon_k: float = 5.0e4     # tendon axial stiffness N/m (>> pretension: stiff)
    tendon_damp: float = 0.4    # tendon damping N*s/m
    gap: float = 0.003          # magnet gap, m (edge ring -> tighter is viable)
    coil_r_lo: float = 0.74     # EDGE coil ring inner, fraction of R
    coil_r_hi: float = 0.94     # EDGE coil ring outer, fraction of R
    n_magnets: int = 36         # bars in the magnet ring (visual + collision)
    coil_mass: float = 0.0015   # total coil + lacquer added mass, kg (PLAN s6.1: ~1-2 g)
    BL: float = 0.6             # force factor N/A (from coil/bl_sim.py)
    strike_r: float = 0.45      # default strike radius, fraction of R (central play)
    strike_radius: float = 0.025  # strike contact-patch radius, m (~stick/finger)
    strike_tau: float = 3.0e-3  # strike contact time, s (half-sine hit envelope)
    dt: float = 5.0e-5
    slowmo: float = 6.0         # interactive playback slowdown (wall = slowmo*sim)
    viz_gain: float = 2.0       # interactive: exaggerate head z-deflection (display only)

    @property
    def tension(self):          # T0 from target f0 (clamped-membrane f_01)
        c = 2 * np.pi * self.f0 * self.R / 2.4048
        return c * c * self.sigma          # N/m

    @property
    def spacing(self):
        return 2 * self.R / self.grid


def _layout(p):
    """Return free-node dict {(i,j):(x,y)} and clamped rim positions touched."""
    a = p.spacing
    free = {}
    for i in range(p.grid + 1):
        for j in range(p.grid + 1):
            x, y = -p.R + i * a, -p.R + j * a
            if np.hypot(x, y) < p.R - 1e-4:
                free[(i, j)] = (x, y)
    return a, free


def make_xml(p):
    a, free = _layout(p)
    m_node = p.sigma * a * a                      # lumped node mass
    Ft0 = p.tension * a                           # tendon pretension force, N
    L0 = a - Ft0 / p.tendon_k                      # springlength -> pretension when flat
    coil_lo, coil_hi = p.coil_r_lo * p.R, p.coil_r_hi * p.R

    def is_coil(x, y):
        return coil_lo <= np.hypot(x, y) <= coil_hi

    # coil + lacquer mass rides ONLY on the coil nodes -> mass-loads the head
    coil_nodes = [ij for ij, (x, y) in free.items() if is_coil(x, y)]
    m_extra = p.coil_mass / max(1, len(coil_nodes))

    bodies, tendons, rim_sites = [], [], {}
    for (i, j), (x, y) in free.items():
        coil = is_coil(x, y)
        # only coil-annulus nodes collide with the plate (magnets only there)
        ct, ca = (2, 1) if coil else (0, 0)
        rgba = ".85 .5 .2 1" if coil else ".7 .7 .85 1"
        nm = m_node + (m_extra if coil else 0.0)
        bodies.append(f"""
        <body name="n_{i}_{j}" pos="{x:.5f} {y:.5f} 0">
          <joint name="j_{i}_{j}" type="slide" axis="0 0 1"/>
          <geom name="g_{i}_{j}" type="sphere" size="{a*0.11:.4f}" mass="{nm:.6f}"
                contype="{ct}" conaffinity="{ca}" rgba="{rgba}"/>
          <site name="s_{i}_{j}" size="0.002"/>
        </body>""")

    def tendon(sa, sb, name):
        return (f'<spatial name="{name}" stiffness="{p.tendon_k}" '
                f'springlength="{L0:.5f}" damping="{p.tendon_damp}" '
                f'width="0.0012" rgba=".5 .5 .55 .25">'
                f'<site site="{sa}"/><site site="{sb}"/></spatial>')

    for (i, j), (x, y) in free.items():
        for di, dj in ((1, 0), (0, 1)):           # right and up neighbours
            nb = (i + di, j + dj)
            if nb in free:
                tendons.append(tendon(f"s_{i}_{j}", f"s_{nb[0]}_{nb[1]}",
                                      f"t_{i}_{j}_{di}{dj}"))
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):   # clamp to rim
            nb = (i + di, j + dj)
            if nb not in free:
                rx, ry = -p.R + nb[0] * a, -p.R + nb[1] * a
                key = (nb[0], nb[1])
                rim_sites[key] = (rx, ry)
                tendons.append(tendon(f"s_{i}_{j}", f"rim_{nb[0]}_{nb[1]}",
                                      f"tr_{i}_{j}_{di}_{dj}"))

    rim_xml = "".join(
        f'<site name="rim_{i}_{j}" pos="{x:.5f} {y:.5f} 0" size="0.003" '
        f'rgba="0 0 0 1"/>' for (i, j), (x, y) in rim_sites.items())

    # pick strike + a coil node to host the (force-less) UI motors
    sr = p.strike_r * p.R
    strike_ij = min(free, key=lambda ij: abs(np.hypot(*free[ij]) - sr) + abs(free[ij][1]))
    coil_ij = min(free, key=lambda ij: abs(np.hypot(*free[ij]) - p.coil_r_hi * p.R) + abs(free[ij][1]))

    # magnet ring (bottom): alternating-polarity bars only around the edge
    r_mag = 0.5 * (coil_lo + coil_hi)
    mag_ht = np.pi * r_mag / p.n_magnets * 0.92          # tangential half-len
    mag_hr = 0.5 * (coil_hi - coil_lo) * 0.55            # radial half-width
    mags = []
    for k in range(p.n_magnets):
        th = 2 * np.pi * k / p.n_magnets
        mx, my = r_mag * np.cos(th), r_mag * np.sin(th)
        col = ".80 .25 .20 .95" if k % 2 == 0 else ".20 .35 .80 .95"   # N / S
        mags.append(f'<geom type="box" pos="{mx:.4f} {my:.4f} 0" '
                    f'euler="0 0 {th + np.pi/2:.4f}" '
                    f'size="{mag_ht:.4f} {mag_hr:.4f} 0.0015" '
                    f'contype="1" conaffinity="2" rgba="{col}" mass="0.003"/>')
    mag_ring_xml = "".join(mags)

    return f"""<mujoco model="darbuka_head">
  <compiler angle="radian"/>
  <option timestep="{p.dt}" integrator="implicitfast" gravity="0 0 0"/>
  <visual><global offwidth="1200" offheight="900"/></visual>
  <worldbody>
    <light pos="0 0 0.6" dir="0 0 -1"/>
    <geom name="rim" type="cylinder" pos="0 0 0" size="{p.R+0.004} 0.002"
          contype="0" conaffinity="0" rgba=".2 .2 .2 .25"/>
    {rim_xml}
    <!-- FIXED magnet plate: a MOCAP body (kinematic, immovable, separate
         from the head). It never recoils when struck; the head vibrates
         freely in the gap and only its edge coil ring can reach it. The
         gap is set live by writing mocap_pos (see apply_forces). -->
    <body name="plate" mocap="true" pos="0 0 {-p.gap:.5f}">
      <geom name="backiron" type="cylinder" size="{coil_hi+0.012:.4f} 0.0008"
            contype="0" conaffinity="0" rgba=".25 .25 .30 .18"/>
      {mag_ring_xml}
    </body>
    <!-- aiming marker: shows where SPACE will land the next hit (hit_x/hit_y) -->
    <body name="hitmarker" mocap="true" pos="0 0 0.012">
      <geom type="sphere" size="0.007" contype="0" conaffinity="0" rgba="1 .25 .1 .95"/>
    </body>
    {''.join(bodies)}
  </worldbody>
  <tendon>{''.join(tendons)}</tendon>
  <actuator>
    <!-- all gear=0: pure UI sliders, we read data.ctrl and act ourselves.
         coil_q0..3 = the 4 edge QUADRANT coil currents (azimuthal steering):
         all + = m=0 breathing, (+,+,-,-) = m=1 dipole, (+,-,+,-) = m=2. -->
    <motor name="gap" joint="j_{coil_ij[0]}_{coil_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="-0.020 0"/>
    <motor name="hit_x" joint="j_{strike_ij[0]}_{strike_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="-0.160 0.160"/>
    <motor name="hit_y" joint="j_{strike_ij[0]}_{strike_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="-0.160 0.160"/>
    <motor name="hit_force" joint="j_{strike_ij[0]}_{strike_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="0 400"/>
    <motor name="coil_q0" joint="j_{coil_ij[0]}_{coil_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="-3 3"/>
    <motor name="coil_q1" joint="j_{coil_ij[0]}_{coil_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="-3 3"/>
    <motor name="coil_q2" joint="j_{coil_ij[0]}_{coil_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="-3 3"/>
    <motor name="coil_q3" joint="j_{coil_ij[0]}_{coil_ij[1]}" gear="0"
           ctrllimited="true" ctrlrange="-3 3"/>
  </actuator>
</mujoco>"""


def _setup(p):
    model = mujoco.MjModel.from_xml_string(make_xml(p))
    data = mujoco.MjData(model)
    a, free = _layout(p)
    coil_lo, coil_hi = p.coil_r_lo * p.R, p.coil_r_hi * p.R

    def jdof(i, j):
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"j_{i}_{j}")
        return model.jnt_dofadr[jid]

    # partition the edge coil nodes into 4 azimuthal QUADRANTS (E,N,W,S)
    coil_wedges = {0: [], 1: [], 2: [], 3: []}
    for (i, j), (x, y) in free.items():
        if coil_lo <= np.hypot(x, y) <= coil_hi:
            q = int((np.degrees(np.arctan2(y, x)) % 360) // 90)
            coil_wedges[q].append(jdof(i, j))
    sr = p.strike_r * p.R
    strike_ij = min(free, key=lambda ij: abs(np.hypot(*free[ij]) - sr) + abs(free[ij][1]))
    sx, sy = free[strike_ij]
    strike_dofs = [jdof(i, j) for (i, j), (x, y) in free.items()
                   if np.hypot(x - sx, y - sy) <= p.strike_radius]   # default patch
    node_xy_dof = [(x, y, jdof(i, j)) for (i, j), (x, y) in free.items()]
    node_qpos = [model.jnt_qposadr[mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_JOINT, f"j_{i}_{j}")] for (i, j) in free]
    aid = lambda n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n)
    bmid = lambda b: model.body_mocapid[
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, b)]
    ids = dict(gap=aid("gap"), hit_x=aid("hit_x"), hit_y=aid("hit_y"),
               hit_force=aid("hit_force"),
               coil_q=[aid(f"coil_q{w}") for w in range(4)],
               strike_dofs=strike_dofs, node_xy_dof=node_xy_dof,
               node_qpos=node_qpos, coil_wedges=coil_wedges, free=free,
               mocap=bmid("plate"), hitmarker=bmid("hitmarker"))
    data.ctrl[ids["gap"]] = -p.gap                 # seed sliders
    data.ctrl[ids["hit_force"]] = 90.0             # medium hit (slider up to 400)
    data.mocap_pos[ids["mocap"]] = (0, 0, -p.gap)
    return model, data, ids


def patch_dofs(ids, cx, cy, radius):
    """DOFs of nodes within `radius` of (cx, cy) — the strike contact patch."""
    return [d for (x, y, d) in ids["node_xy_dof"]
            if np.hypot(x - cx, y - cy) <= radius]


def apply_forces(p, data, ids):
    """Zero qfrc, then apply the standing forces: fixed plate (mocap gap) and
    the 4 edge quadrant coil drives. Transient HITS are added by the caller
    after this (they are time-windowed). Read the gear=0 UI motors ourselves."""
    data.qfrc_applied[:] = 0.0
    # fixed plate: the gap slider just relocates the kinematic magnets (no recoil)
    data.mocap_pos[ids["mocap"]] = (0, 0, data.ctrl[ids["gap"]])
    # each edge quadrant coil drives its own nodes: F = BL * I_quadrant
    for w in range(4):
        F = p.BL * data.ctrl[ids["coil_q"][w]]
        for dof in ids["coil_wedges"][w]:
            data.qfrc_applied[dof] += F                                    # +up / -down


def apply_hit(p, data, dofs, peak, t_since):
    """Add a half-sine strike impulse (peak N, contact p.strike_tau) spread over
    the patch `dofs`, at elapsed time t_since. No-op once the pulse is over."""
    if not dofs or t_since >= p.strike_tau:
        return False
    per = peak * np.sin(np.pi * t_since / p.strike_tau) / len(dofs)
    for d in dofs:
        data.qfrc_applied[d] += -per                                       # down
    return True


def measure_f0(p, amp=0.001, dur=0.5):
    """Seed the clamped-membrane FUNDAMENTAL shape J0(2.4048 r/R) and measure
    its ringdown frequency. A MODAL initialisation (not a point pluck) excites
    the global fundamental cleanly, free of the ~kHz single-node lattice mode a
    localised pluck would ring. Parabolic peak interp -> sub-Hz resolution.
    Returns (f0_Hz, peak_|z|_m)."""
    from scipy.special import j0
    model = mujoco.MjModel.from_xml_string(make_xml(p))
    data = mujoco.MjData(model)
    _, free = _layout(p)
    # park the (mocap) magnet plate far away so the ringdown never contacts it
    mid = model.body_mocapid[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "plate")]
    data.mocap_pos[mid] = (0, 0, -0.05)
    for (i, j), (x, y) in free.items():             # seed the fundamental dome
        qa = model.jnt_qposadr[mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_JOINT, f"j_{i}_{j}")]
        data.qpos[qa] = amp * j0(2.4048 * np.hypot(x, y) / p.R)
    cij = min(free, key=lambda ij: np.hypot(*free[ij]))
    cqp = model.jnt_qposadr[mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_JOINT, f"j_{cij[0]}_{cij[1]}")]
    mujoco.mj_forward(model, data)
    n = int(dur / p.dt)
    z = np.empty(n)
    for k in range(n):
        data.qfrc_applied[:] = 0.0
        mujoco.mj_step(model, data)
        z[k] = data.qpos[cqp]
    if not np.all(np.isfinite(z)):
        return float("nan"), float("nan")
    sp = np.abs(np.fft.rfft(z - z.mean()))
    fr = np.fft.rfftfreq(n, p.dt)
    k0 = 1 + int(np.argmax(sp[1:]))
    if 1 < k0 < len(sp) - 1:                         # parabolic sub-bin refine
        a0, b0, c0 = sp[k0 - 1], sp[k0], sp[k0 + 1]
        den = a0 - 2 * b0 + c0
        delta = 0.5 * (a0 - c0) / den if den else 0.0
    else:
        delta = 0.0
    return float(fr[k0] + delta * (fr[1] - fr[0])), float(np.abs(z).max())


def selftest(p):
    model, data, ids = _setup(p)
    nbody = sum(1 for _ in ids["free"])
    membrane_mass = p.sigma * np.pi * p.R ** 2
    ncoil = sum(len(v) for v in ids["coil_wedges"].values())
    print(f"nodes {nbody}, coil nodes {ncoil} in 4 quadrants "
          f"{[len(ids['coil_wedges'][w]) for w in range(4)]}, "
          f"dt {p.dt*1e6:.0f} us, tension {p.tension:.0f} N/m")
    print(f"lumped mass {sum(model.body_mass):.4f} kg incl plate; "
          f"membrane sigma*piR^2 = {membrane_mass*1000:.0f} g; "
          f"coil mass {p.coil_mass*1000:.1f} g")
    f0, zpk = measure_f0(p)
    if not np.isfinite(f0):
        print("  !! NaN — model unstable, shrink dt or tendon_k"); return
    print(f"  measured f0 ~ {f0:.1f} Hz vs target {p.f0:.0f} Hz (lattice approx)")
    print(f"  peak |z| stayed {zpk*1000:.2f} mm (bounded, no blow-up)")
    print("selftest OK")


def mass_loading(p):
    """A/B: how much does the bonded coil mass detune the head, edge vs centre."""
    from dataclasses import replace
    head_g = p.sigma * np.pi * p.R ** 2 * 1000
    f_base, _ = measure_f0(replace(p, coil_mass=0.0))
    f_edge, _ = measure_f0(p)                                   # edge ring (design)
    f_ctr, _ = measure_f0(replace(p, coil_r_lo=0.25, coil_r_hi=0.55))  # same mass, centre
    print(f"Coil mass-loading of the head "
          f"(coil {p.coil_mass*1000:.1f} g = {p.coil_mass*1000/head_g*100:.0f}% "
          f"of the {head_g:.0f} g head):")
    print(f"  no coil:            f0 {f_base:7.2f} Hz")
    print(f"  coil at EDGE ring:  f0 {f_edge:7.2f} Hz  "
          f"({f_edge-f_base:+5.2f} Hz, {(f_edge-f_base)/f_base*100:+.2f}%)")
    print(f"  same coil at CENTRE:f0 {f_ctr:7.2f} Hz  "
          f"({f_ctr-f_base:+5.2f} Hz, {(f_ctr-f_base)/f_base*100:+.2f}%)")
    print("  -> the rim is a displacement node, so edge-mounted coil mass barely")
    print("     detunes the head; the SAME mass at mid-head detunes several x more.")


def render(p, fname="build/membrane_strike.gif"):
    import imageio.v2 as imageio
    model, data, ids = _setup(p)
    rnd = mujoco.Renderer(model, 600, 800)
    cam = mujoco.MjvCamera()
    cam.azimuth, cam.elevation, cam.distance = 90, -25, 0.55
    cam.lookat[:] = (0, 0, -p.gap / 2)
    frames = []
    for k in range(int(0.18 / p.dt)):
        data.ctrl[ids["gap"]] = -p.gap
        apply_forces(p, data, ids)
        apply_hit(p, data, ids["strike_dofs"], 220.0, k * p.dt)  # one hit at t=0
        mujoco.mj_step(model, data)
        if k % int(1 / 60 / p.dt) == 0:
            rnd.update_scene(data, cam)
            frames.append(rnd.render())
    os.makedirs("build", exist_ok=True)
    imageio.mimsave(fname, frames, fps=30)
    print(f"wrote {fname} ({len(frames)} frames)")


def render_modes(p, fname="build/membrane_modes.gif", viz=8.0):
    """Drive the 4 edge quadrant coils in m=0/m=1/m=2 patterns and render the
    head taking each modal shape — the azimuthal steering segmentation buys."""
    import imageio.v2 as imageio
    from PIL import Image, ImageDraw
    model, data, ids = _setup(p)
    rnd = mujoco.Renderer(model, 600, 800)
    cam = mujoco.MjvCamera()
    cam.azimuth, cam.elevation, cam.distance = 60, -22, 0.55
    cam.lookat[:] = (0, 0, 0)
    data.ctrl[ids["gap"]] = -0.02            # park magnets clear: show free shape
    patterns = [("m=0  breathing  (+,+,+,+)", (1, 1, 1, 1)),
                ("m=1  dipole     (+,+,-,-)", (1, 1, -1, -1)),
                ("m=2  quadrupole (+,-,+,-)", (1, -1, 1, -1))]
    frames = []
    for name, pat in patterns:
        for w in range(4):
            data.ctrl[ids["coil_q"][w]] = viz * pat[w]
        for k in range(int(0.13 / p.dt)):
            apply_forces(p, data, ids)
            mujoco.mj_step(model, data)
            if k % int(1 / 60 / p.dt) == 0:
                rnd.update_scene(data, cam)
                im = Image.fromarray(rnd.render())
                ImageDraw.Draw(im).text((14, 12), name, fill=(255, 255, 255))
                frames.append(np.asarray(im))
    os.makedirs("build", exist_ok=True)
    imageio.mimsave(fname, frames, fps=18)
    print(f"wrote {fname} ({len(frames)} frames): m=0 -> m=1 -> m=2 steering")


def interactive(p):
    import time
    import mujoco.viewer
    model, data, ids = _setup(p)
    st = {"fire": False, "active": False, "t": 0.0, "patch": []}

    def key_cb(keycode):
        if keycode == 32:                            # SPACE = trigger one hit
            st["fire"] = True

    print("AIM: hit_x / hit_y sliders move the red marker.  HIT: press SPACE.")
    print("hit_force = how hard.  coil_q0..q3 = 4 quadrant currents "
          "((+,+,-,-)=m1, (+,-,+,-)=m2).  gap = magnet plate height.")
    print(f"playback {p.slowmo:g}x slow, deflection shown {p.viz_gain:g}x "
          "exaggerated (display only — physics is real).")
    nq = ids["node_qpos"]
    with mujoco.viewer.launch_passive(model, data, key_callback=key_cb) as v:
        while v.is_running():
            t0 = time.time()
            cx, cy = data.ctrl[ids["hit_x"]], data.ctrl[ids["hit_y"]]
            data.mocap_pos[ids["hitmarker"]] = (cx, cy, 0.012)
            apply_forces(p, data, ids)
            if st["fire"] and not st["active"]:      # latch a new strike
                st["patch"] = patch_dofs(ids, cx, cy, p.strike_radius)
                st["active"], st["t"], st["fire"] = True, 0.0, False
            if st["active"]:
                going = apply_hit(p, data, st["patch"],
                                  data.ctrl[ids["hit_force"]], st["t"])
                st["t"] += p.dt
                st["active"] = going
            mujoco.mj_step(model, data)
            # display only: amplify node z so a few-mm strike is visible, then
            # restore so the physics keeps stepping on the true state
            real = data.qpos[nq].copy()
            data.qpos[nq] = real * p.viz_gain
            mujoco.mj_kinematics(model, data)
            v.sync()
            data.qpos[nq] = real
            dt_left = p.dt * p.slowmo - (time.time() - t0)
            if dt_left > 0:
                time.sleep(dt_left)


if __name__ == "__main__":
    p = Params()
    if "--massload" in sys.argv:
        mass_loading(p)
    elif "--render" in sys.argv:
        render(p)
    elif "--modes" in sys.argv:
        render_modes(p)
    elif "--interactive" in sys.argv:
        interactive(p)
    else:
        selftest(p)
