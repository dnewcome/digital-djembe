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

A previous attempt (speaker inside the body under the head) produced a
single-pitch squeal. That failure mode is structural: pure acoustic
feedback through one transducer converges to whichever mode has highest
loop gain and locks there. Avoiding it requires two things, and the
whole project is built around them:

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
the acoustic character. **Segmenting the coil into 4–8 wedges driven
independently lets the DSP excite specific membrane modes (m=0, m=1,
m=2, m=3)** — a capability no tactile transducer can offer. See
[PLAN.md §6](PLAN.md#6-transducer-track-b-planar-magnetic-drive-flex-pcb-coil-on-the-head),
especially [§6.3 on coil segmentation → modal selectivity](PLAN.md#63-coil-segmentation--modal-selectivity).

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

- Dayton DAEX25FHE-4 tactile transducer (body driver)
- Dayton DAEX13CT-4 tactile transducer (hoop driver)
- TPA3116 class-D amp board
- USB measurement mic (Dayton UMM-6 or similar)
- N52 neodymium discs (10 × 3 mm) for the magnetic mount
- M3 bolts + nuts for clamp pinch
- PETG filament for the printed parts

Later (DSP build):

- Daisy Seed (STM32H7 + audio codec)
- External multichannel ADC — AK5558 TDM or a pair of PCM1865s — since
  the Daisy's onboard codec is stereo only and the mic array needs four
  channels
- 3–4 WM-61A-class electrets + simple preamps
- Small UI panel (pots, encoder, OLED)

## Decision gate

The measurement results will answer: *does any mount produce
broadband coupling strong enough to sustain acoustic feedback at modest
drive levels?* If yes, the DSP work begins. If no, mount geometry gets
another iteration before writing any firmware.

## License

No license chosen yet. Treat as all rights reserved until a `LICENSE`
file appears.
