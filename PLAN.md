# Digital Djembe / Hybrid Acoustic-Electric Darbuka — Design Plan

A living design document. Captures the discussion so far; each section is
intended to be edited as the build progresses.

## 1. Goal

Build a hybrid acoustic-electric hand drum (originally a djembe, now a
**darbuka** — see §4) that sounds like an acoustic drum when played, but with
controllable electronic augmentation: feedback, resonances, inharmonic
overtones, and DSP-shaped sustain. The target sound is *controllable musical
chaos*, **not** a drone.

Previous attempt: a speaker mounted inside the body under the head produced a
single-pitch Larsen feedback that was unpleasant and uninteresting. Avoiding
that failure mode is a central design constraint.

### Design thesis
Pure acoustic feedback through one transducer converges to whichever mode has
highest loop gain → one pitch, locked. Musical chaos requires **phase
incoherence** (so no single mode dominates) and **multiple parallel paths**
(so the system can't settle into a fixed point). Every DSP choice below
serves this thesis.

## 2. Compute platform

**Chosen: Daisy Seed** (STM32H7 @ 480 MHz, 64 MB SDRAM, onboard audio codec).

Considered:
- ESP32 — too weak for multi-channel DSP with low latency.
- Raspberry Pi Zero 2W — viable with PREEMPT_RT but more OS overhead.
- OWL pedal — similar capability, more expensive and larger.
- **Daisy Seed** — small, cheap (~$30), first-class audio DSP, FAUST/C++ toolchain, strong community.

Known limitation: the onboard codec is stereo in/out only. A 3–4 element mic
array needs an **external multichannel I2S/TDM ADC** (AK5558 eval or PCM1865
pair). The planar magnetic drive (§6) also needs multichannel output for
segmented coil drive.

Control: **MIDI over USB** (Daisy has USB host/device). Add OSC over WiFi
later only if needed — simpler is better to start.

## 3. High-level architecture

```
  [3–4 electret mics in body]
            │
            ▼
   ┌──────────────────┐
   │ External I2S TDM │   (Daisy's onboard codec is stereo only)
   │ ADC (AK5558)     │
   └────────┬─────────┘
            │ 4ch audio
            ▼
   ┌────────────────────────────────────────────────┐
   │               Daisy Seed (DSP core)            │
   │  ┌──────────────┐   ┌──────────────────────┐  │
   │  │ Hit analysis │   │ Audio processing     │  │
   │  │ (onset, TDOA │──▶│ graph (§3.2)         │  │
   │  │  location,   │   │                      │  │
   │  │  velocity)   │   │                      │  │
   │  └──────┬───────┘   └──────────┬───────────┘  │
   │         └──── modulates ───────┘              │
   └────────────────────┬───────────────────────────┘
                        │ multichannel out (to class-D amp)
            ┌───────────┴────────────┐
            ▼                        ▼
   [Shell/body transducer]  [Head driver — track A or B]
   (excites body resonance) (primary feedback path; see §5 / §6)

   MIDI-USB in  ────▶  Daisy (CC → param matrix)
   Pots on panel ────▶  global macros (chaos, shift, mix)
```

### 3.1 Sensing — one mic array, three jobs
- **Audio pickup** → summed input to DSP graph.
- **Onset + velocity** → envelope follower triggers modal bank, resets LFOs.
- **Hit localization** → TDOA (time-difference-of-arrival) cross-correlation
  across mic pairs gives (x, y) of each strike. Maps to parameter
  modulation: e.g., edge hits raise drive/chaos, center hits favor sustain.

Chosen over piezos, optical, or head-mounted sensors because it adds **zero
mass** to the head and provides all three jobs from the same hardware.

### 3.2 DSP graph — parallel paths, not one loop

1. **Dry path.** Summed mic array → HPF → light compression → output mix.
2. **Frequency-shifted feedback.** Single-sideband shift of 3–20 Hz in the
   loop. Key trick: small shift breaks phase-coherent Larsen pileup, so
   feedback drifts chaotically in pitch instead of locking.
3. **Modal resonator bank.** 6–12 tuned biquads/waveguides pumped by the
   input envelope. Simulates head modes (fundamental + first few circular
   modes); gives "feedback-like" sustain *without* needing acoustic
   round-trip. Designer controls which modes ring.
4. **Self-oscillating SVF bank.** 2–4 state-variable filters with Q past
   oscillation threshold; input perturbs them. Inharmonic sine pads that
   modulate chaotically from strikes.
5. **Nonlinear waveshaper.** Soft saturation before the output sum —
   generates harmonics from whatever fundamentals come in.

Mixing: (2)–(5) route predominantly to the **head driver** (strong head
coupling, where real acoustic feedback can occur, now broken up by path 2's
freq shift so it can't lock). (1) and body-resonance-friendly content route
to the **shell/body transducer**. With a segmented planar magnetic drive
(§6), each DSP path can additionally route to a *specific coil segment* to
excite a specific mode.

### 3.3 Control surface
- MIDI-USB: CCs through a routing matrix to feedback gain, shift amount,
  modal mix, chaos/drive, waveshaper amount, **and per-segment gain/phase
  for the planar coil (§6)**.
- Pots on Daisy's ADCs: 4–6 most-used macros for standalone play.
- Hit (x, y, velocity) is itself a modulation source — treat as a 3D
  controller.

## 4. Pivot: djembe → darbuka

Switched because a **darbuka has a removable metal hoop** tensioning the
head, whereas a djembe uses rope. The metal hoop is:
- Rigid and in direct intimate contact with the skin at its boundary.
- Bolt-able without destroying the instrument.
- A better mechanical transmission path than any wood route.

This makes the single highest-risk item — mechanically coupling a transducer
to the head without damping it — much more tractable.

## 5. Transducer track A: tactile / off-the-shelf (baseline)

### 5.1 Physics
A clamped membrane has zero displacement at its boundary. But if you *move
the boundary itself* (shake the hoop), every mode with radial slope at the
edge — all of them — gets excited in proportion to hoop velocity. Rimshots
work for this reason on a snare.

### 5.2 Mount options to test
- **A. Hoop clamp** — C-shaped clamp that straddles the darbuka's tuning
  hoop between two bolts. Non-destructive. Likely best coupling.
- **B. Tuning-bolt-replacement bracket** — L-bracket captured under an
  existing tuning bolt. Uses stock hardware; no drilling, no clamp force
  loss.
- **C. Body-interior (magnetic for metal bodies)** — magnet-mounted tactile
  transducer on the inside wall of the goblet. Baseline for comparison;
  excites body modes, couples to head only via air + edge.
- **D. Direct head driver (voice coil on skin)** — formerly rejected for
  violating the no-damping goal, now revived in a low-mass form as the
  planar magnetic track (§6).

### 5.3 Measurement protocol
Before committing to any permanent build:
1. Use `measure.py` (Farina log sine sweep → IR deconvolution → magnitude
   transfer function).
2. Measurement mic: 5 cm above head center, held by the `mic_jig` printed
   cap so runs are reproducible across mounts.
3. Run the sweep with each mount (A/B/C). Save labeled results.
4. `measure.py --compare A B C` overlays the transfer functions.
5. Decision criteria:
   - Most energy into head-mode peaks (80–400 Hz range for a 220 mm head).
   - Flattest/broadest response (more modes available for DSP to pump).
   - Whether any mount gets loud enough to cause acoustic feedback at
     modest drive — the actual go/no-go for the feedback DSP concept.

### 5.4 Hardware (this repo)
- `measure.py` — measurement script (log sweep, deconvolution, plotting).
- `brackets.scad` — parametric OpenSCAD for the four printed parts:
  `hoop_clamp`, `bolt_bracket`, `body_magnet`, `mic_jig`.

### 5.5 Role of this track
Serves as the **baseline / known-works reference**. Cheap, off-the-shelf,
and ready to measure now. Protects against the failure mode where a fabbed
flex PCB underperforms and we can't tell whether the fault is in the coil,
the magnets, the DSP, or the conceptual approach.

## 6. Transducer track B: planar magnetic drive (flex-PCB coil on the head)

A more ambitious transducer track. Rather than mount a moving-mass tactile
transducer to the body or hoop, bond a **thin flex PCB spiral coil** to the
outer annulus of the drum head and mount an **alternating-polarity magnet
array** inside the shell directly below it. The head itself becomes the
diaphragm of a **planar magnetic driver** — same operating principle as a
HiFiMan/Audeze headphone or a Magnepan speaker, applied to the darbuka head.

### 6.1 Why this is compelling
- **Very low added mass** (~1–2 g for flex PCB + laquer) → negligible
  damping of the head's natural acoustic character. This was the blocker
  that killed option D earlier; the flex PCB form factor removes it.
- **Distributed force** over the coil area rather than point coupling.
- **Modal-selective drive** via coil segmentation — a capability no tactile
  transducer can offer (see §6.3).

### 6.2 Key design constraint: B-field geometry

A flat spiral coil in a uniform *axial* B-field produces **zero net axial
force** — the Lorentz force is radial, not up/down. To drive the head
perpendicular to itself, the field at the coil plane must be **radial**
(in-plane). Three magnet topologies achieve this:

- **Planar-magnetic-headphone style (chosen).** Parallel magnet bars with
  alternating N-S-N-S polarity on a plate inside the shell, a few mm below
  the head. Serpentine coil traces run *between* adjacent bars; each trace
  sees an opposite field from its neighbor, and if the coil's current also
  alternates between traces, all Lorentz forces add coherently.
- **Radially-magnetized ring magnet.** Specialty hardware, expensive, hard
  to source.
- **Push-pull disc magnets above and below the head.** Efficient, but puts
  hardware above the playing surface — defeats the whole point.

The magnet plate lives inside the darbuka body, invisible to the player,
non-contact with the head. 2–4 mm clearance to the head is enough.

### 6.3 Coil segmentation → modal selectivity

This is the capability the tactile path cannot replicate and the main
reason to pursue this track.

A uniform *axisymmetric* spiral coil applies uniform force around the
annulus. Under this excitation, only **m=0 modes** (the "breathing" /
concentric-ring modes) respond. Non-axisymmetric modes (m=1, m=2, m=3) have
a cos(mφ) azimuthal dependence; their response to uniform annular force
integrates to zero — they are **unreachable** by an axisymmetric coil.

m≥1 modes are what give a drum its expressive tom/djun character, so
reaching them matters. **Split the coil into N wedge segments driven from
separate DSP channels.** Drive patterns become:

| Drive pattern (N=4) | Modes excited |
|---------------------|---------------|
| All segments in phase, same amplitude | m=0 (breathing) |
| Opposing pairs (+,+,-,-) | m=1 (sloshing / tom-like) |
| Alternating (+,-,+,-) | m=2 (quadrupole) |
| Phased quadrature (+, j, -, -j) | m=1 rotating around head |

With N=8 we reach m=3. With separate amplitude + phase control per segment
we can synthesize arbitrary azimuthal excitation patterns in real time and
**set up different resonances by segmenting the coil in different ways** —
effectively the drum becomes a *modally-controllable* instrument where DSP
chooses which mode gets pumped, independent of which mode the player
struck.

Combined with the DSP graph (§3.2), this opens new musical moves:
- Strike center (m=0 energy) but have the feedback loop drive m=1,
  producing a wobble/roll rather than a pitch.
- Hit-location (x, y) from TDOA (§3.1) → automatically route feedback into
  whichever azimuthal mode matches where the player hit.
- Rotating mode patterns (quadrature phasing between segments) for
  spatialized/phasing timbres.

### 6.4 Impedance / power budget

Flex PCB coils are resistive. Rough numbers for a single-layer 1 oz copper,
0.2 mm traces, 50 turns at ~80 mm mean diameter: ~60–100 Ω per segment.
Far from the 4–8 Ω a standard class-D amp expects.

Levers to pull:
- **2 oz copper** (R halves).
- **4-layer flex with the four copies wired in parallel** (~4× R drop).
- **Wider traces**, trading turn count for resistance.

Target: **8–16 Ω per segment**, 1–3 W continuous, which is plenty given how
efficiently force couples into a 1–2 g moving system. A multichannel
class-D amp (4–8 channels at a few watts each) drives the segments.

### 6.5 Fabrication path
- **PCB**: JLCPCB or PCBWay flex PCB service. 4-layer, 2 oz outer copper,
  polyimide substrate. First prototype: 80 mm OD, 60 mm ID, 4 wedge
  segments. Cost ~$5/board at MOQ 5, lead time ~1–2 weeks.
- **Adhesion**: thin-film contact adhesive (3M 467MP) or clear urethane
  laquer. Needs an acoustic test to confirm it doesn't stiffen the head
  perceptibly.
- **Magnet plate**: 3D-printed fixture holding 8–16 N42 bar magnets
  (~3×3×20 mm) in alternating polarity, suspended from the inside lip of
  the shell by a cross-brace. Will be designed in `brackets.scad` alongside
  the existing parts.
- **Amp**: multichannel class-D (4× TPA3116 modules or a TAS5825 eval with
  per-channel control), driven from the Daisy via external DAC/codec if
  more than the onboard stereo output is needed.

### 6.6 Relationship to track A

**Run both tracks in parallel.** Track A (§5) is the baseline measurement
platform — cheap, off-the-shelf, ready now. Track B has a 1–2 week PCB
lead time per iteration, so designing it now doesn't delay the measurement
work. The final instrument is expected to use the flex-PCB planar drive as
its primary head transducer; the tactile body/hoop mounts may survive as
secondary body-resonance drivers in the stereo (or multichannel) output.

## 7. Bill of materials (prototype phase)

### Track A — tactile measurement baseline
| Item | Qty | Approx cost | Notes |
|------|-----|-------------|-------|
| Dayton DAEX25FHE-4 tactile transducer | 1 | $20 | Shell/body driver |
| Dayton DAEX13CT-4 small transducer | 1 | $12 | Hoop driver |
| TPA3116 class-D amp board | 1 | $10 | Drives both transducers |
| USB measurement mic (Dayton UMM-6 or equiv) | 1 | $80 | Reference for sweeps |
| Neodymium disc magnets (N52, 10×3 mm) | 4 | $5 | For body-magnet mount |
| M3 bolts + nuts | pack | $5 | Clamp pinch bolts |
| 3D print filament (PETG recommended) | — | — | Clamp + jig parts |

### Track B — planar magnetic drive
| Item | Qty | Approx cost | Notes |
|------|-----|-------------|-------|
| 4-layer flex PCB (JLCPCB/PCBWay) | 5 | $25 | 2 oz copper, polyimide |
| N42 bar magnets (3×3×20 mm) | 16 | $15 | Alternating-polarity plate |
| Multichannel class-D amp (4×) | 1 | $40 | e.g. 4× TPA3116 modules |
| 3M 467MP adhesive or urethane laquer | — | $10 | Bond coil to head |
| 4-layer flex revisions | as needed | $5/board | Iteration headroom |

### Later (DSP build)
| Item | Qty | Notes |
|------|-----|-------|
| Daisy Seed | 1 | STM32H7 + codec |
| AK5558 TDM ADC board (or PCM1865 pair) | 1 | Multichannel mic input |
| External I2S DAC (multichannel) | 1 | Only if >2ch output needed for Track B |
| WM-61A or similar electret + preamp | 3–4 | Mic array |
| Small OLED + encoder + pots | — | UI / macros |

## 8. Decision log

- Platform: **Daisy Seed** (over ESP32, Pi Zero, OWL). §2.
- Sensing: **mic array only** — no piezos, no head-mounted sensors. §3.1.
- Control: **MIDI-USB first**, OSC deferred. §3.3.
- Instrument: **darbuka** (over djembe). §4.
- Feedback-coherence strategy: **freq-shift in loop + parallel DSP paths**,
  not a single gain-staged Larsen loop. §1, §3.2.
- Transducer strategy: **dual-track** — Track A tactile (baseline /
  measurement), Track B planar magnetic flex PCB (target final
  instrument). §5, §6.

## 9. Next steps

Run the two tracks in parallel:

**Track A (immediate)**
1. Buy transducers + measurement mic.
2. Print `mic_jig` and `hoop_clamp`, plus `body_magnet` for the baseline.
3. Run `measure.py` for each mount; save and compare.
4. **Gate decision:** do any mounts produce usable broadband coupling? If
   yes, continue. If no, revisit mount geometry.
5. With a working mount, wire a temporary analog Larsen loop
   (mic → amp → transducer) and confirm acoustic feedback is achievable
   before investing in Daisy DSP work.

**Track B (parallel, 1–2 week cadence)**
6. Design flex PCB coil geometry in KiCad: 4-segment annular spiral, 4
   layers, 2 oz copper, 80 mm OD / 60 mm ID. Submit first order.
7. Design magnet plate + shell-mounted cross-brace in `brackets.scad`.
   Source N42 bar magnets.
8. On PCB arrival, bench-test each segment's force output with a laser
   displacement sensor or mic-at-a-fixed-position sweep. Compare against
   Track A baseline data.
9. Acoustic test of laquer / adhesive on a spare head before committing to
   the real drum head.

**Joint (after either track demonstrates viable coupling)**
10. Begin DSP graph implementation on Daisy, one path at a time, starting
    with path (2) (freq-shifted feedback) — the load-bearing innovation
    relative to the failed prior attempt.
11. If Track B is primary, wire multichannel output routing so DSP can
    address each coil segment independently (§3.2, §6.3).

## 10. Open questions

- Exact darbuka model / hoop dimensions — affects `brackets.scad`
  parameters.
- Mic array geometry (number, spacing, placement in body) for TDOA
  resolution vs. practicality.
- Amp topology: one amp per transducer or a stereo amp? Multichannel amp
  for segmented coil drive — how many channels before it's overkill?
- Whether modal bank frequencies should adapt to head tuning automatically
  (input-driven pitch detection) or be set manually.
- Segment count for the flex PCB: 4 (hits m=0, m=1), 8 (up to m=3), or
  variable? More segments = more amp channels + more PCB complexity.
- Coil adhesive: does 3M 467MP / urethane laquer perceptibly stiffen or
  damp the head? Needs a side-by-side acoustic test on a spare head.
- Magnet-to-head clearance: what's the minimum that remains playable given
  head deflection on a hard strike?
- Can segmented drive be done from a stereo Daisy output with analog
  switching/routing, or does it require multichannel DAC output?
