// Toolchain sanity check: stereo sine with frequency + gain sliders.
// Run with:  faust2jack -httpd sine.dsp && ./sine -httpd
// Then open http://127.0.0.1:5510 for the slider UI.
// Stop with Ctrl-C.

import("stdfaust.lib");

freq = hslider("Frequency [unit:Hz]", 440, 40, 2000, 0.1);
gain = hslider("Gain", 0.05, 0, 0.3, 0.001);   // start quiet

process = os.osc(freq) * gain <: _, _;
