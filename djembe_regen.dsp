// Digital djembe / hybrid darbuka — regenerative (filter-bank feedback) variant.
//
// Alternative to djembe.dsp's whole-instrument closed-loop feedback.
// Rather than a positive-feedback loop around the whole system, this
// version uses a regenerative bank of per-mode resonant filters: the
// mic drives a parallel bank of BPFs tuned to the head's mode
// frequencies, and that bank's output drives the head (the transducer
// model).  The feedback is narrow-band per mode — analogous to
// per-filter feedback in a Moog ladder / SVF.
//
// Rationale: on a 2D membrane, dense inharmonic modes cause
// whole-instrument feedback to lock onto whichever mode happens to
// align with loop phase, producing an inharmonic screech rather than
// musical sustain.  Narrowing the feedback to the head-mode
// frequencies means self-oscillation can only happen at mode
// frequencies, and per-mode Q controls mode extension independently.
// See PLAN.md §3.5 for the conceptual discussion.
//
// Build:  faust2jack djembe_regen.dsp && pw-jack ./djembe_regen
//
// A/B vs djembe.dsp: set the same f0, qHead, strike position, etc.,
// in both, and compare timbre with the two augmentation models.

import("stdfaust.lib");

// ---------- Global controls ----------

f0    = hslider("h:djembe/v:[0]col1/h:[0]head/[0] Fundamental [unit:Hz]", 150, 60, 400, 1);
qHead = hslider("h:djembe/v:[0]col1/h:[0]head/[1] Mode Q", 60, 5, 200, 1);

strike     = button ("h:djembe/v:[0]col1/h:[1]strike/[0] Strike");
strikeGain = hslider("h:djembe/v:[0]col1/h:[1]strike/[1] Strike Gain", 0.5, 0, 1, 0.001);
strikeDec  = hslider("h:djembe/v:[0]col1/h:[1]strike/[2] Strike Decay [unit:ms]", 8, 1, 60, 0.1);
strikeX    = hslider("h:djembe/v:[0]col1/h:[1]strike/[3] Strike X", 0.0, -0.99, 0.99, 0.01);
strikeY    = hslider("h:djembe/v:[0]col1/h:[1]strike/[4] Strike Y", 0.0, -0.99, 0.99, 0.01);

// Regen bank: Q is the per-mode "resonance / sustain" knob (analogous
// to a Moog SVF resonance control); gain scales the return into the
// head.  Higher Q → longer mode extension; very high Q pushes modes
// toward self-sustained ring at their own frequencies.
regenQ    = hslider("h:djembe/v:[0]col1/h:[2]regen/[0] Regen Q", 120, 10, 500, 1) : si.smoo;
regenGain = hslider("h:djembe/v:[0]col1/h:[2]regen/[1] Regen Gain [scale:log]", 0.05, 0.001, 2.0, 0.001) : si.smoo;

master = hslider("h:djembe/v:[1]col2/Master", 0.2, 0, 1, 0.001) : si.smoo;

// ---------- Head: 9-mode modal bank at ideal-membrane ratios ----------
// Identical to djembe.dsp (§3.4 physical model).

modeW(r, w, x) = fi.resonbp(f0 * r, qHead, w, x);

besJ0 = ffunction(float j0f(float), "math.h", "");
besJ1 = ffunction(float j1f(float), "math.h", "");
besJn = ffunction(float jnf(int, float), "math.h", "");

j01 = 2.4048; j11 = 3.8317; j21 = 5.1356;
j02 = 5.5201; j31 = 6.3802; j12 = 7.0156;
j41 = 7.5883; j22 = 8.4172; j03 = 8.6537;

rNorm = sqrt(strikeX * strikeX + strikeY * strikeY) : min(0.99);
phi   = atan2(strikeY, strikeX);

w01 = besJ0(j01 * rNorm);
w11 = besJ1(j11 * rNorm) * cos(phi);
w21 = besJn(2, j21 * rNorm) * cos(2.0 * phi);
w02 = besJ0(j02 * rNorm);
w31 = besJn(3, j31 * rNorm) * cos(3.0 * phi);
w12 = besJ1(j12 * rNorm) * cos(phi);
w41 = besJn(4, j41 * rNorm) * cos(4.0 * phi);
w22 = besJn(2, j22 * rNorm) * cos(2.0 * phi);
w03 = besJ0(j03 * rNorm);

head(x) = x <: modeW(1.000, w01), modeW(1.593, w11), modeW(2.135, w21),
              modeW(2.295, w02), modeW(2.653, w31), modeW(2.917, w12),
              modeW(3.156, w41), modeW(3.500, w22), modeW(3.598, w03)
           :> _ * (1.0/9.0);

mic(x) = fi.highpass(2, 60, x);

// ---------- Strike source ----------

strikeEnv = strike : ba.impulsify
                   : fi.pole(ba.tau2pole(strikeDec * 0.001));
strikeSig = no.noise * strikeEnv * strikeGain;

// ---------- Regenerative bank ----------
//
// Nine BPFs tuned to the same nine mode frequencies as the head.  Loop
// signal can only ring at these frequencies, so self-oscillation (once
// the loop crosses unity gain on a mode) happens at musical mode
// pitches rather than at whatever arbitrary frequency loop phase
// happens to lock.
//
// `fi.resonbp(fc, Q, g)` has peak magnitude g*Q at resonance, so pass
// `1.0/regenQ` to normalize each filter's peak to unity regardless of
// Q.  regenGain is then the actual round-trip return amplitude at mode
// resonance, not a Q-dependent multiplier.
regenG = 1.0 / regenQ;
regenBank(x) = (fi.resonbp(f0 * 1.000, regenQ, regenG, x)
             +  fi.resonbp(f0 * 1.593, regenQ, regenG, x)
             +  fi.resonbp(f0 * 2.135, regenQ, regenG, x)
             +  fi.resonbp(f0 * 2.295, regenQ, regenG, x)
             +  fi.resonbp(f0 * 2.653, regenQ, regenG, x)
             +  fi.resonbp(f0 * 2.917, regenQ, regenG, x)
             +  fi.resonbp(f0 * 3.156, regenQ, regenG, x)
             +  fi.resonbp(f0 * 3.500, regenQ, regenG, x)
             +  fi.resonbp(f0 * 3.598, regenQ, regenG, x)) * (1.0/9.0);

// ---------- Narrow-band regenerative loop ----------
//
// Forward: (strike + return) → head → mic.
// Return:  regen bank × regenGain, soft-limited by tanh.
// No direct path, no SVFs, no waveshaper — augmentation is *only*
// per-mode.  `djembe.dsp` keeps the broadband closed-loop variant for
// comparison.

fwd(fb, s) = (s + fb) : head : mic;
returnPath(x) = ma.tanh(regenBank(x) * regenGain);

system = strikeSig : fwd ~ returnPath;

// ---------- Output: stereo with a touch of decorrelation ----------

process = system : ma.tanh <: _ , (_ : de.fdelay(256, 37)) :> _ * master, _ * master;
