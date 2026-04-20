// Digital djembe / hybrid darbuka — first DSP simulation.
//
// Closed loop:  strike → head(modal bank) → mic → DSP chain → back into head
//
// The DSP chain runs four things in parallel, summed into the return path:
//   1. direct wire (with a modulated delay as freq-shift proxy)
//   2. 3-band modal resonator bank
//   3. 2-band self-oscillating state-variable filter bank
//   4. tanh waveshaper
//
// Build:  faust2jack djembe.dsp && pw-jack ./djembe
//
// The head model is a 9-mode bank at the Bessel-zero frequency ratios of
// an ideal circular membrane. With f0 ~ 150 Hz and moderate Q this sounds
// like a hand drum when struck; with feedback engaged it drifts chaotically
// across modes instead of locking to one pitch (the whole point).

import("stdfaust.lib");

// ---------- Global controls ----------

// Layout: two columns in an outer hgroup.
// Column 1: head / strike / feedback.   Column 2: mix / svf / shape / out.

f0    = hslider("h:djembe/v:[0]col1/h:[0]head/[0] Fundamental [unit:Hz]", 150, 60, 400, 1);
qHead = hslider("h:djembe/v:[0]col1/h:[0]head/[1] Mode Q", 60, 5, 200, 1);

strike     = button ("h:djembe/v:[0]col1/h:[1]strike/[0] Strike");
strikeGain = hslider("h:djembe/v:[0]col1/h:[1]strike/[1] Strike Gain", 0.5, 0, 1, 0.001);
strikeDec  = hslider("h:djembe/v:[0]col1/h:[1]strike/[2] Strike Decay [unit:ms]", 8, 1, 60, 0.1);
// Strike position in head coordinates, normalized so r = sqrt(X^2+Y^2) = 1 is the rim.
strikeX    = hslider("h:djembe/v:[0]col1/h:[1]strike/[3] Strike X", 0.0, -0.99, 0.99, 0.01);
strikeY    = hslider("h:djembe/v:[0]col1/h:[1]strike/[4] Strike Y", 0.0, -0.99, 0.99, 0.01);

fbGain   = hslider("h:djembe/v:[0]col1/h:[2]feedback/[0] Feedback Gain [scale:log]", 0.01, 0.001, 2.0, 0.001) : si.smoo;
shiftHz  = hslider("h:djembe/v:[0]col1/h:[2]feedback/[1] Shift LFO [unit:Hz]", 6, 0.1, 30, 0.1);
shiftMs  = hslider("h:djembe/v:[0]col1/h:[2]feedback/[2] Shift Depth [unit:ms]", 3, 0.0, 20, 0.1);

modalMix = hslider("h:djembe/v:[1]col2/h:[0]mix/[0] Modal Bank", 0.3, 0, 1, 0.001);
svfMix   = hslider("h:djembe/v:[1]col2/h:[0]mix/[1] Self-osc SVF", 0.2, 0, 1, 0.001);
shapeMix = hslider("h:djembe/v:[1]col2/h:[0]mix/[2] Waveshaper", 0.1, 0, 1, 0.001);
directMix= hslider("h:djembe/v:[1]col2/h:[0]mix/[3] Direct", 0.5, 0, 1, 0.001);

svfF1 = hslider("h:djembe/v:[1]col2/h:[1]svf/[0] SVF1 Freq [unit:Hz]", 220, 60, 2000, 1);
svfF2 = hslider("h:djembe/v:[1]col2/h:[1]svf/[1] SVF2 Freq [unit:Hz]", 430, 60, 2000, 1);
svfQ  = hslider("h:djembe/v:[1]col2/h:[1]svf/[2] SVF Q", 120, 10, 500, 1);

drive = hslider("h:djembe/v:[1]col2/h:[2]shape/[0] Drive", 3, 1, 20, 0.1);

master = hslider("h:djembe/v:[1]col2/h:[3]out/Master", 0.2, 0, 1, 0.001) : si.smoo;

// ---------- Head: 9-mode modal bank at ideal-membrane ratios ----------
//
// Each of the nine modes is a circular-membrane eigenmode indexed by
// (m, n): m is the number of nodal diameters, n the number of nodal
// circles (counting the rim).  The n-th positive zero of J_m is called
// j_{m,n}; the frequency ratio f_{m,n}/f_{0,1} is j_{m,n}/j_{0,1}.
//
// A strike at (X, Y) excites each mode in proportion to its mode shape
// at that point:
//
//     w_{m,n}(r, phi) = J_m(j_{m,n} * r) * cos(m * phi)
//
// where r = sqrt(X^2 + Y^2) and phi = atan2(Y, X).  This is the
// §3.4 physical model component.

// Per-mode resonator.  `w` is the strike excitation weight for this
// mode; it can be negative (modes with a nodal diameter at the strike
// point flip sign across it).  Weight goes into the biquad's input
// gain, so changing strike position reshapes the chord of modes that
// ring without touching any of the downstream DSP.
modeW(r, w, x) = fi.resonbp(f0 * r, qHead, w, x);

// Bessel functions from libm via FAUST ffunction.  j0f/j1f/jnf are
// present in glibc (Linux dev) and newlib (Daisy), so no custom
// polynomial approximation is required.
besJ0 = ffunction(float j0f(float), "math.h", "");
besJ1 = ffunction(float j1f(float), "math.h", "");
besJn = ffunction(float jnf(int, float), "math.h", "");

// Bessel zeros j_{m,n} (n-th positive root of J_m).  These set the
// argument of the mode-shape function so that the shape is zero at the
// rim (r = 1), satisfying the clamped-boundary condition.
j01 = 2.4048; j11 = 3.8317; j21 = 5.1356;
j02 = 5.5201; j31 = 6.3802; j12 = 7.0156;
j41 = 7.5883; j22 = 8.4172; j03 = 8.6537;

// Polar form of the strike position.
rNorm = sqrt(strikeX * strikeX + strikeY * strikeY) : min(0.99);
phi   = atan2(strikeY, strikeX);

// Mode-shape weights.  m = 0 modes are azimuthally symmetric, so their
// weight doesn't depend on phi.
w01 = besJ0(j01 * rNorm);
w11 = besJ1(j11 * rNorm) * cos(phi);
w21 = besJn(2, j21 * rNorm) * cos(2.0 * phi);
w02 = besJ0(j02 * rNorm);
w31 = besJn(3, j31 * rNorm) * cos(3.0 * phi);
w12 = besJ1(j12 * rNorm) * cos(phi);
w41 = besJn(4, j41 * rNorm) * cos(4.0 * phi);
w22 = besJn(2, j22 * rNorm) * cos(2.0 * phi);
w03 = besJ0(j03 * rNorm);

// Summed modal response.  Pickup is modeled as a uniform average over
// the head (no per-mode readout weight on output).  A strike at the
// origin collapses to J_0(0) = 1 on the three m=0 modes and 0 on all
// others, matching the previous uniform-weight center-strike case.
head(x) = x <: modeW(1.000, w01), modeW(1.593, w11), modeW(2.135, w21),
              modeW(2.295, w02), modeW(2.653, w31), modeW(2.917, w12),
              modeW(3.156, w41), modeW(3.500, w22), modeW(3.598, w03)
           :> _ * (1.0/9.0);

// ---------- Simulated mic inside the body (HPF out DC/body thump) ----------

mic(x) = fi.highpass(2, 60, x);

// ---------- Strike source: noise burst with short exponential decay ----------

strikeEnv = strike : ba.impulsify
                   : fi.pole(ba.tau2pole(strikeDec * 0.001));

strikeSig = no.noise * strikeEnv * strikeGain;

// ---------- Freq-shift proxy: modulated delay ----------
// (Not a true SSB shifter but breaks phase coherence enough to hear the effect.
//  True Hilbert SSB comes in a later version.)

lfo = (os.osc(shiftHz) + 1.0) * 0.5;   // unipolar 0..1
shift(x) = de.fdelay(4096, 64.0 + shiftMs * 0.001 * ma.SR * lfo, x);

// ---------- Parallel DSP paths on the mic signal ----------

// Modal resonator bank picking three useful head partials
modalBank(x) = (fi.resonbp(f0 * 1.000, 80, 1.0, x)
             +  fi.resonbp(f0 * 1.593, 80, 1.0, x)
             +  fi.resonbp(f0 * 2.135, 80, 1.0, x)) * (1.0/3.0);

// Two self-oscillating state-variable filters
svfBank(x) = (fi.resonlp(svfF1, svfQ, 1.0, x)
           +  fi.resonlp(svfF2, svfQ, 1.0, x)) * 0.5;

// Nonlinear waveshaper (normalized so output stays in [-1,1])
shaper(x) = ma.tanh(drive * x) / ma.tanh(drive);

// Mix the four paths — this is the signal that goes back into the head
dspChain(x) = directMix * shift(x)
            + modalMix  * modalBank(x)
            + svfMix    * svfBank(x)
            + shapeMix  * shaper(x);

// ---------- Closed feedback loop ----------
//
// Forward path: add feedback to the strike source, run through head,
// pick up with the mic.  Return path: dspChain * fbGain, fed back via ~.

fwd(fb, s) = (s + fb) : head : mic;
returnPath(x) = ma.tanh(dspChain(x) * fbGain);

system = strikeSig : fwd ~ returnPath;

// ---------- Output: stereo, with a touch of decorrelation ----------

process = system : ma.tanh <: _ , (_ : de.fdelay(256, 37)) :> _ * master, _ * master;
