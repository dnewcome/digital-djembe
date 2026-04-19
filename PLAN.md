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
pair).

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
                        │ stereo out (to class-D amp)
            ┌───────────┴────────────┐
            ▼                        ▼
   [Shell/body transducer]  [Hoop/rim transducer]
   (excites body resonance) (direct skin coupling —
                             primary feedback path)

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

Mixing: (2)–(5) route predominantly to the **hoop transducer** (strong head
coupling, where real acoustic feedback can occur, now broken up by path 2's
freq shift so it can't lock). (1) and body-resonance-friendly content route
to the **shell/body transducer**.

### 3.3 Control surface
- MIDI-USB: CCs through a routing matrix to feedback gain, shift amount,
  modal mix, chaos/drive, waveshaper amount.
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

## 5. Highest-risk item: transducer-to-head coupling

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
- **D. Direct head driver (voice coil on skin)** — rejected for violating
  the no-damping goal. Keep in reserve only if A–C all fail.

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

## 6. Bill of materials (prototype phase)

| Item | Qty | Approx cost | Notes |
|------|-----|-------------|-------|
| Dayton DAEX25FHE-4 tactile transducer | 1 | $20 | Shell/body driver |
| Dayton DAEX13CT-4 small transducer | 1 | $12 | Hoop driver |
| TPA3116 class-D amp board | 1 | $10 | Drives both transducers |
| USB measurement mic (Dayton UMM-6 or equiv) | 1 | $80 | Reference for sweeps |
| Neodymium disc magnets (N52, 10×3 mm) | 4 | $5 | For body-magnet mount |
| M3 bolts + nuts | pack | $5 | Clamp pinch bolts |
| 3D print filament (PETG recommended) | — | — | Clamp + jig parts |

Later (DSP build):
| Item | Qty | Notes |
|------|-----|-------|
| Daisy Seed | 1 | STM32H7 + codec |
| AK5558 TDM ADC board (or PCM1865 pair) | 1 | Multichannel mic input |
| WM-61A or similar electret + preamp | 3–4 | Mic array |
| Small OLED + encoder + pots | — | UI / macros |

## 7. Decision log

- Platform: **Daisy Seed** (over ESP32, Pi Zero, OWL). §2.
- Sensing: **mic array only** — no piezos, no head-mounted sensors. §3.1.
- Control: **MIDI-USB first**, OSC deferred. §3.3.
- Instrument: **darbuka** (over djembe). §4.
- Feedback-coherence strategy: **freq-shift in loop + parallel DSP paths**,
  not a single gain-staged Larsen loop. §1, §3.2.

## 8. Next steps (in order)

1. Buy transducers + measurement mic.
2. Print `mic_jig` and `hoop_clamp`, plus `body_magnet` for the baseline.
3. Run `measure.py` for each mount; save and compare.
4. **Gate decision:** do any mounts produce usable broadband coupling? If
   yes, continue. If no, revisit mount geometry or reconsider path (D).
5. With a working mount, wire a temporary analog Larsen loop (mic → amp →
   transducer) and confirm acoustic feedback is achievable before investing
   in Daisy DSP work.
6. Begin DSP graph implementation on Daisy, one path at a time, starting
   with path (2) (freq-shifted feedback) since it's the load-bearing
   innovation relative to the failed prior attempt.

## 9. Open questions

- Exact darbuka model / hoop dimensions — affects `brackets.scad`
  parameters.
- Mic array geometry (number, spacing, placement in body) for TDOA
  resolution vs. practicality.
- Amp topology: one amp per transducer or a stereo amp? Affects total
  parts and control.
- Whether modal bank frequencies should adapt to head tuning
  automatically (input-driven pitch detection) or be set manually.
