# digital-djembe

A hybrid acoustic-electric hand drum. The instrument is a **darbuka** with
its natural acoustic sound augmented by DSP-driven feedback, modal
resonance, and nonlinear processing. The goal is *controllable musical
chaos* — an electroacoustic instrument whose feedback is rich and
playable rather than a locked-pitch Larsen drone.

**Status:** early design and prototyping. No DSP code yet — the current
work is de-risking the single biggest unknown: whether a transducer can
be coupled to the drum head strongly enough to sustain feedback, without
damping the head. Two transducer tracks run in parallel:
a **tactile/off-the-shelf baseline** and a **planar magnetic flex-PCB
coil** bonded to the head (see [PLAN.md §5](PLAN.md#5-transducer-track-a-tactile--off-the-shelf-baseline)
and [§6](PLAN.md#6-transducer-track-b-planar-magnetic-drive-flex-pcb-coil-on-the-head)).

## Design thesis

Two prior attempts shape this design:

- **Speaker inside the body under the head** produced a single-pitch
  squeal. Structural failure: pure acoustic feedback through one
  transducer converges to whichever mode has highest loop gain and
  locks there.
- **Piezo discs bonded to the head** drove the head successfully but
  with a peaky, bass-weak frequency response (intrinsic 3–8 kHz piezo
  resonance, vanishing displacement at low frequency, capacitive-load
  mismatch). Validated direct head-drive as a concept; ruled out
  piezos as the actuator class.

Avoiding a locked-pitch Larsen drone requires two things, and the
whole DSP design is built around them:

1. **Phase incoherence in the loop** — a small (3–20 Hz) single-sideband
   frequency shift in the feedback path prevents any mode from
   phase-matching round-trip, so feedback drifts chaotically in pitch
   instead of locking.
2. **Multiple parallel DSP paths** — a modal resonator bank, a bank of
   self-oscillating state-variable filters, and a nonlinear waveshaper
   run in parallel with the direct feedback path, so no single mode
   dominates the system's behavior.

Compute is a **Daisy Seed**. Sensing is a **3–4 element mic array**
inside the body, doing triple duty: audio pickup, onset/velocity
detection, and hit localization via time-difference-of-arrival. Control
is **MIDI over USB**. See [PLAN.md](PLAN.md) for the full architecture,
decision log, and open questions.

## Two transducer tracks

**Track A — tactile (baseline).** Off-the-shelf tactile transducers
clamped to the darbuka's metal hoop or magnet-mounted to the body. Cheap,
available now, and the reference against which Track B is compared. This
is what `measure.py` and `brackets.scad` currently support. See
[PLAN.md §5](PLAN.md#5-transducer-track-a-tactile--off-the-shelf-baseline).

**Track B — planar magnetic flex-PCB coil on the head.** A thin
multi-layer flex PCB spiral coil is laquered to the outer annulus of the
drum head, with an alternating-polarity magnet array mounted inside the
shell directly below. The head becomes the diaphragm of a planar
magnetic driver — the same principle as a HiFiMan/Audeze headphone,
applied to a darbuka. Low added mass (~1–2 g) means minimal damping of
the acoustic character. Because force is F = BIL (proportional to
current), response is flat across the audio band — the piezo FR
problem doesn't apply.

The coil is **segmented** along three orthogonal axes (see
[§6.3](PLAN.md#63-coil-segmentation--modal-selectivity)):

- **Azimuthal** — N wedges around the ring, reaches azimuthal modes
  m=0..m=(N/2).
- **Radial** — two concentric coil rings at different radii lets in-/
  anti-phase driving pick between radial modes (n=1 fundamental vs.
  n=2 overtone).
- **Drive pattern** — the phase/amplitude per segment in real time
  selects rotating, dipole, quadrupole, or hit-location-following
  excitation.

First-prototype target: **2 concentric rings × 4 azimuthal wedges =
8 coils**, driven by two 4-channel class-D boards, reaching m=0..m=2
× n=1..n=2. Power budget (see
[§6.4](PLAN.md#64-power-efficiency-and-thermal-budget)) comes out to
~0.5 W per coil, ~4 W across the array — about 2 orders of magnitude
below the PCB's thermal ceiling, so the coil comfortably sustains
feedback; it's just not a speaker.

## Why a darbuka

The project started as a "digital djembe." It pivoted to a darbuka
because a darbuka's tensioning hoop is a **removable metal ring**,
whereas a djembe's head is held by rope. The metal hoop is rigid, in
intimate contact with the skin at its boundary, and bolt-able without
modifying the instrument — which turns the "how do we drive the head"
problem from a research question into a mechanical one.

## Repository contents

| File | Purpose |
|------|---------|
| [`PLAN.md`](PLAN.md) | Living design document. Architecture, DSP graph, decision log, next steps. |
| [`measure.py`](measure.py) | Farina log sine sweep → impulse response → transfer function. For comparing transducer mounts. |
| [`brackets.scad`](brackets.scad) | Parametric OpenSCAD for four printable parts: hoop clamp, bolt-capture bracket, magnetic body plate, measurement mic jig. |

## Measurement workflow

The coupling experiment is the current gate item. The idea is to mount a
transducer three different ways, sweep each one, and compare transfer
functions to decide which mount drives the head most usefully.

```sh
# 1. Fill in your darbuka's dimensions at the top of brackets.scad,
#    then export STLs for the parts you want to print:
#      part = "mic_jig"       // always print this
#      part = "hoop_clamp"    // non-destructive hoop mount (start here)
#      part = "bolt_bracket"  // replaces a tuning-bolt washer
#      part = "body_magnet"   // baseline for metal-body darbukas

# 2. Install measurement deps:
pip install numpy scipy sounddevice matplotlib

# 3. Identify your audio interface:
python measure.py --list-devices

# 4. Record each mount (drum still, room quiet). Use the mic_jig so the
#    reference mic sits at a fixed position between runs.
python measure.py --label hoop-clamp      --in-device 2 --out-device 3
python measure.py --label bolt-bracket    --in-device 2 --out-device 3
python measure.py --label body-magnet     --in-device 2 --out-device 3

# 5. Compare:
python measure.py --compare hoop-clamp bolt-bracket body-magnet
```

Output lands in `measurements/` (ignored by git): per-run `.npz` with
the smoothed transfer function and IR, the raw recording, and a
side-by-side comparison PNG.

## Hardware (prototype phase)

**Track A — tactile measurement baseline:**
- Dayton DAEX25FHE-4 tactile transducer (body driver)
- Dayton DAEX13CT-4 tactile transducer (hoop driver)
- TPA3116 class-D amp board
- USB measurement mic (Dayton UMM-6 or similar)
- N52 neodymium discs (10 × 3 mm) for the body-magnet mount
- M3 bolts + nuts for clamp pinch
- PETG filament for the printed parts

**Track B — planar magnetic drive:**
- 4-layer flex PCB, 2 oz copper, ~200 mm OD annular (JLCPCB/PCBWay,
  ~$10/board at MOQ 5)
- N42 bar magnets (3 × 3 × 20 mm), 16+ per drum, alternating polarity
- Two 4-channel class-D amp boards (8 channels total)
- 8-channel I2S DAC to drive the amps from the Daisy
- 3M 467MP adhesive or urethane laquer for bonding the coil to the head

**DSP build (after transducer coupling is validated):**
- Daisy Seed (STM32H7 + audio codec)
- External multichannel I2S ADC — AK5558 TDM or a pair of PCM1865s —
  since the Daisy's onboard codec is stereo only and the mic array
  needs four channels
- 3–4 WM-61A-class electrets + simple preamps
- Small UI panel (pots, encoder, OLED)

## Decision gate

Track A's measurement results will answer: *does any off-the-shelf
mount produce broadband coupling strong enough to sustain acoustic
feedback at modest drive levels?* That result also serves as the
reference the Track B flex PCB is judged against when it arrives.
If either track clears the bar, DSP work begins. If neither does,
mount/coil geometry iterates before any firmware is written.

## License

No license chosen yet. Treat as all rights reserved until a `LICENSE`
file appears.
