#!/usr/bin/env python3
"""
Transducer-to-head coupling measurement.

Plays an exponential (log) sine sweep through the transducer under test and
records a reference mic placed over the drum head. Computes the impulse
response via Farina sweep deconvolution, then the magnitude transfer function.

Compare mounts by running with different --label values and plotting together.

Typical session:
    python measure.py --list-devices
    python measure.py --label baseline-shell-exterior --in-device 2 --out-device 3
    python measure.py --label hoop-clamp --in-device 2 --out-device 3
    python measure.py --label body-interior --in-device 2 --out-device 3
    python measure.py --compare baseline-shell-exterior hoop-clamp body-interior

Hardware expected:
    - Audio interface with one line-out (to amp -> transducer) and one mic-in
      (reference mic near head).
    - Class-D amp (TPA3116 or similar) driving the transducer.
    - Measurement mic (USB UMM-6 or interface-connected), 5 cm over head center.
    - Drum stationary during each sweep. Room as quiet as possible.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
import scipy.signal as sig
import scipy.io.wavfile as wav
import matplotlib.pyplot as plt

SR = 48000
F_START = 20.0
F_END = 8000.0
DURATION = 10.0
TAIL = 1.5  # trailing silence to capture the full IR tail
LEVEL = 0.5  # sweep amplitude (0..1). Start low, raise until mic shows clean SNR
RESULTS = Path(__file__).parent / "measurements"


def log_sweep(duration, f0, f1, sr, level=LEVEL):
    """Farina exponential sine sweep and its matched inverse filter."""
    N = int(sr * duration)
    t = np.arange(N) / sr
    L = duration / np.log(f1 / f0)
    K = 2 * np.pi * f0 * L
    sweep = np.sin(K * (np.exp(t / L) - 1.0))
    fade = int(0.02 * sr)
    sweep[:fade] *= np.linspace(0, 1, fade)
    sweep[-fade:] *= np.linspace(1, 0, fade)
    # Inverse filter: time-reversed sweep with amplitude envelope that
    # compensates for the -3 dB/oct pink coloration of the sweep.
    inv = sweep[::-1] * np.exp(-t / L) * (f1 / f0 - 1) / L
    return (level * sweep).astype(np.float32), inv.astype(np.float32)


def play_and_record(sweep, sr, in_device, out_device):
    pad = np.zeros(int(TAIL * sr), dtype=np.float32)
    out = np.concatenate([sweep, pad])[:, None]  # (N, 1) mono
    rec = sd.playrec(
        out,
        samplerate=sr,
        channels=1,
        input_mapping=[1],
        output_mapping=[1],
        device=(in_device, out_device),
        dtype="float32",
    )
    sd.wait()
    return rec.flatten()


def compute_ir(recorded, inverse_filter, sr, window_ms=500):
    """Convolve recording with inverse filter; window around peak."""
    ir_full = sig.fftconvolve(recorded, inverse_filter, mode="full")
    peak = int(np.argmax(np.abs(ir_full)))
    pre = int(0.005 * sr)
    post = int((window_ms / 1000) * sr)
    start = max(0, peak - pre)
    end = min(len(ir_full), peak + post)
    ir = ir_full[start:end]
    ir = ir / (np.max(np.abs(ir)) + 1e-12)
    return ir


def transfer_function(ir, sr, n_fft=None):
    n_fft = n_fft or max(2 ** 15, len(ir))
    H = np.fft.rfft(ir, n_fft)
    f = np.fft.rfftfreq(n_fft, 1 / sr)
    mag_db = 20 * np.log10(np.abs(H) + 1e-12)
    return f, mag_db


def smooth_fractional_octave(f, mag_db, frac=6):
    """1/frac-octave smoothing for readable plots."""
    out = np.empty_like(mag_db)
    half = 1.0 / (2.0 * frac)
    log_f = np.log2(np.maximum(f, 1e-9))
    for i, lf in enumerate(log_f):
        if f[i] < 10:
            out[i] = mag_db[i]
            continue
        mask = (log_f >= lf - half) & (log_f <= lf + half)
        out[i] = mag_db[mask].mean() if mask.any() else mag_db[i]
    return out


def measure(label, in_device, out_device):
    RESULTS.mkdir(exist_ok=True)
    sweep, inv = log_sweep(DURATION, F_START, F_END, SR)

    print(f"[{label}] sweep {F_START:.0f} -> {F_END:.0f} Hz, {DURATION:.1f} s")
    print("Keep the drum still and the room quiet. Starting in 2 s...")
    sd.sleep(2000)
    rec = play_and_record(sweep, SR, in_device, out_device)

    peak_level = np.max(np.abs(rec))
    print(f"  recorded peak: {20*np.log10(peak_level + 1e-12):.1f} dBFS")
    if peak_level < 0.02:
        print("  WARNING: very low signal. Raise gain or LEVEL.", file=sys.stderr)
    if peak_level > 0.98:
        print("  WARNING: clipping. Lower gain or LEVEL.", file=sys.stderr)

    ir = compute_ir(rec, inv, SR)
    f, mag = transfer_function(ir, SR)
    mag_s = smooth_fractional_octave(f, mag, frac=6)

    np.savez(
        RESULTS / f"{label}.npz",
        f=f, mag=mag, mag_smooth=mag_s, ir=ir, sr=SR,
    )
    wav.write(RESULTS / f"{label}_raw.wav", SR, rec)
    wav.write(RESULTS / f"{label}_ir.wav", SR, ir.astype(np.float32))
    print(f"[{label}] saved {RESULTS / (label + '.npz')}")


def plot(labels):
    fig, (ax_fr, ax_ir) = plt.subplots(2, 1, figsize=(11, 8))
    for label in labels:
        path = RESULTS / f"{label}.npz"
        if not path.exists():
            print(f"missing: {path}", file=sys.stderr)
            continue
        d = np.load(path)
        f, mag, ir, sr = d["f"], d["mag_smooth"], d["ir"], int(d["sr"])
        ax_fr.semilogx(f, mag, label=label, linewidth=1.3)
        t = np.arange(len(ir)) / sr * 1000
        ax_ir.plot(t, ir, label=label, alpha=0.75, linewidth=0.8)

    ax_fr.set_xlim(20, 8000)
    ax_fr.set_ylim(-70, 10)
    ax_fr.set_xlabel("Frequency (Hz)")
    ax_fr.set_ylabel("Magnitude (dB, relative)")
    ax_fr.set_title("Transducer -> drum head coupling (1/6-oct smoothed)")
    ax_fr.grid(True, which="both", alpha=0.3)
    ax_fr.legend()

    ax_ir.set_xlim(0, 120)
    ax_ir.set_xlabel("Time (ms)")
    ax_ir.set_ylabel("Impulse response (normalized)")
    ax_ir.grid(alpha=0.3)
    ax_ir.legend()

    fig.tight_layout()
    out = RESULTS / ("compare_" + "_".join(labels) + ".png")
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")
    plt.show()


def list_devices():
    print(sd.query_devices())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", help="Label for this measurement run.")
    p.add_argument("--compare", nargs="+", help="Compare saved runs.")
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--in-device", type=int, default=None)
    p.add_argument("--out-device", type=int, default=None)
    args = p.parse_args()

    if args.list_devices:
        list_devices()
    elif args.compare:
        plot(args.compare)
    elif args.label:
        measure(args.label, args.in_device, args.out_device)
        plot([args.label])
    else:
        p.print_help()


if __name__ == "__main__":
    main()
