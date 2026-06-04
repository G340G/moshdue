#!/usr/bin/env python3
"""
HYPER-LUDOVICO V13
- BUG FIX: granular stutter no longer crashes on first grain (empty slice guard)
- New glitch effects: pixel sort, block scramble, datamosh echo, vhs noise,
  luma invert, RGB split, scanline burn, feedback accumulation
- Per-frame glitch mode lottery — every frame draws from a fresh pool
- Chaos now modulates all effect intensities live
- FM + granular audio synth (fixed)
- Robust ffmpeg calls with error reporting
"""

import shutil
import subprocess
import random
import argparse
import tempfile
from pathlib import Path

import numpy as np
import cv2
import wave


# -------------------- UTIL --------------------

def die(msg: str, code: int = 1):
    raise SystemExit(msg)

def check_ffmpeg():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        die("ffmpeg not found on PATH. On GitHub Actions: sudo apt-get install -y ffmpeg")

def run(cmd):
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        die(
            "Command failed:\n"
            f"  {' '.join(cmd)}\n\n"
            f"STDOUT (tail):\n{p.stdout[-4000:]}\n\n"
            f"STDERR (tail):\n{p.stderr[-4000:]}\n"
        )
    return p

def safe_imread(p: Path):
    return cv2.imread(str(p), cv2.IMREAD_COLOR)

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def clamp_img(img):
    return np.clip(img, 0, 255).astype(np.uint8)


# -------------------- GLITCH EFFECTS --------------------

def apply_chroma_bleed(img, intensity: float):
    """Analog chroma shift — U and V channels slide in opposite directions."""
    intensity = float(intensity)
    if intensity <= 0:
        return img
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    shift = int(max(0, intensity) * 4)
    if shift:
        yuv[:, :, 1] = np.roll(yuv[:, :, 1],  shift, axis=1)
        yuv[:, :, 2] = np.roll(yuv[:, :, 2], -shift, axis=1)
    return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

def apply_luma_tear(img, probability: float):
    """Horizontal scanline tear — random number of tears per frame."""
    probability = clamp01(probability)
    if random.random() > probability:
        return img
    h, w = img.shape[:2]
    if h < 20:
        return img
    out = img.copy()
    n_tears = random.randint(1, max(1, int(probability * 8) + 1))
    for _ in range(n_tears):
        y_start = random.randint(0, h - 2)
        thickness = random.randint(1, min(40, h - y_start))
        shift = random.randint(-w // 3, w // 3)
        out[y_start:y_start + thickness] = np.roll(
            out[y_start:y_start + thickness], shift, axis=1
        )
    return out

def apply_pixel_sort(img, intensity: float):
    """
    Sort pixel rows by luma within a random horizontal band.
    Higher intensity → wider sort bands, more of them.
    """
    if intensity <= 0:
        return img
    h, w = img.shape[:2]
    out = img.copy()
    n_bands = random.randint(1, max(1, int(intensity * 4)))
    for _ in range(n_bands):
        band_h = random.randint(4, max(5, int(h * intensity * 0.4)))
        y0 = random.randint(0, max(0, h - band_h))
        band = out[y0:y0 + band_h]
        gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY).astype(np.float32)
        # Sort each row independently by luma
        for r in range(band.shape[0]):
            order = np.argsort(gray[r])
            band[r] = band[r][order]
        out[y0:y0 + band_h] = band
    return out

def apply_block_scramble(img, intensity: float):
    """
    Pick random rectangular blocks and swap or shift them around.
    """
    if intensity <= 0:
        return img
    h, w = img.shape[:2]
    out = img.copy()
    block_size = max(8, int(32 * (1.0 - clamp01(intensity) * 0.5)))
    n_swaps = max(1, int(intensity * 6))
    for _ in range(n_swaps):
        bw = random.randint(block_size // 2, block_size * 2)
        bh = random.randint(block_size // 2, block_size * 2)
        if bw >= w or bh >= h:
            continue
        x1 = random.randint(0, w - bw)
        y1 = random.randint(0, h - bh)
        x2 = random.randint(0, w - bw)
        y2 = random.randint(0, h - bh)
        tmp_block = out[y1:y1 + bh, x1:x1 + bw].copy()
        out[y1:y1 + bh, x1:x1 + bw] = out[y2:y2 + bh, x2:x2 + bw]
        out[y2:y2 + bh, x2:x2 + bw] = tmp_block
    return out

def apply_rgb_split(img, intensity: float):
    """
    Pull the R, G, B channels apart with independent sub-pixel offsets.
    """
    if intensity <= 0:
        return img
    max_shift = max(1, int(intensity * 12))
    b, g, r = cv2.split(img)
    r = np.roll(r, random.randint(-max_shift, max_shift), axis=1)
    r = np.roll(r, random.randint(-max_shift // 2, max_shift // 2), axis=0)
    b = np.roll(b, random.randint(-max_shift, max_shift), axis=1)
    b = np.roll(b, random.randint(-max_shift // 2, max_shift // 2), axis=0)
    return cv2.merge([b, g, r])

def apply_scanline_burn(img, intensity: float):
    """
    Darken alternating scanlines, with occasional bright flicker rows.
    """
    if intensity <= 0:
        return img
    out = img.astype(np.float32)
    h = out.shape[0]
    step = max(2, int(4 / intensity))
    # Dark rows
    out[::step] = out[::step] * (1.0 - 0.5 * clamp01(intensity))
    # Occasional bright row
    if random.random() < intensity * 0.3:
        row = random.randint(0, h - 1)
        out[row] = np.clip(out[row] * 2.0, 0, 255)
    return clamp_img(out)

def apply_vhs_noise(img, intensity: float):
    """
    Luminance noise + occasional full-width white noise bands (VHS dropout).
    """
    if intensity <= 0:
        return img
    h, w = img.shape[:2]
    out = img.astype(np.float32)
    # General noise
    noise = np.random.normal(0, intensity * 25, out.shape).astype(np.float32)
    out = out + noise
    # Dropout bands
    if random.random() < intensity * 0.4:
        n_drops = random.randint(1, max(1, int(intensity * 3)))
        for _ in range(n_drops):
            y = random.randint(0, h - 1)
            thickness = random.randint(1, max(2, int(intensity * 6)))
            out[y:y + thickness] = np.random.randint(0, 256, (min(thickness, h - y), w, 3), dtype=np.uint8)
    return clamp_img(out)

def apply_luma_invert(img, probability: float):
    """
    Invert brightness inside a random region — feels like a CRT gamma spike.
    """
    if random.random() > probability:
        return img
    h, w = img.shape[:2]
    out = img.copy()
    rh = random.randint(h // 8, h // 2)
    rw = random.randint(w // 4, w)
    y0 = random.randint(0, h - rh)
    x0 = random.randint(0, w - rw)
    region = out[y0:y0 + rh, x0:x0 + rw]
    yuv = cv2.cvtColor(region, cv2.COLOR_BGR2YUV)
    yuv[:, :, 0] = 255 - yuv[:, :, 0]
    out[y0:y0 + rh, x0:x0 + rw] = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
    return out

def apply_datamosh_echo(canvas, prev_canvas, intensity: float):
    """
    Blend an older frame back in with heavy motion — pure datamosh feel.
    """
    if intensity <= 0 or prev_canvas is None:
        return canvas
    alpha = clamp01(intensity * 0.6)
    return clamp_img(cv2.addWeighted(canvas, 1.0 - alpha, prev_canvas, alpha, 0.0))

def apply_feedback_accumulator(canvas, accumulator, intensity: float):
    """
    Blend a decaying residual buffer into the frame — trails & burn-in.
    Returns (new_frame, updated_accumulator).
    """
    if intensity <= 0 or accumulator is None:
        return canvas, canvas.copy().astype(np.float32)
    acc = accumulator.astype(np.float32)
    frm = canvas.astype(np.float32)
    decay = max(0.5, 1.0 - intensity * 0.3)
    new_acc = acc * decay + frm * (1.0 - decay)
    blended = clamp_img(frm * (1.0 - intensity * 0.4) + new_acc * intensity * 0.4)
    return blended, new_acc


# -------------------- GLITCH LOTTERY --------------------

# Effect names → weight function(chaos).
# Weight increases with chaos so more extreme effects kick in at higher settings.
_EFFECTS = {
    "chroma":      lambda c: 1.0,
    "tear":        lambda c: 1.0,
    "rgb_split":   lambda c: 0.5 + c * 0.3,
    "vhs_noise":   lambda c: 0.4 + c * 0.2,
    "pixel_sort":  lambda c: 0.3 + c * 0.4,
    "block":       lambda c: 0.2 + c * 0.5,
    "scanline":    lambda c: 0.3 + c * 0.2,
    "luma_invert": lambda c: 0.1 + c * 0.3,
    "echo":        lambda c: 0.2 + c * 0.4,
    "feedback":    lambda c: 0.3 + c * 0.3,
}

def pick_glitch_modes(chaos: float, n_min: int = 1, n_max: int = 4) -> set:
    """
    Draw a random subset of effects each frame.
    Higher chaos → more effects fire simultaneously.
    """
    n_max_adj = min(n_max, max(n_min, int(n_min + chaos)))
    n = random.randint(n_min, n_max_adj)
    names = list(_EFFECTS.keys())
    weights = [_EFFECTS[k](chaos) for k in names]
    total = sum(weights)
    probs = [w / total for w in weights]
    chosen = set()
    while len(chosen) < min(n, len(names)):
        pick = random.choices(names, weights=probs, k=1)[0]
        chosen.add(pick)
    return chosen


# -------------------- SONIC ENGINE --------------------

def synth_experimental_audio(duration: float, chaos: float, stutter_prob: float):
    """
    FM synthesis + granular stutter.
    FIX: stutter only fires when a full prior grain exists (i >= grain).
    """
    chaos = max(0.0, float(chaos))
    stutter_prob = clamp01(stutter_prob)

    sr = 44100
    n = max(sr, int(duration * sr))   # at least 1 second to avoid edge cases
    t = np.linspace(0.0, duration, n, dtype=np.float32)

    # Layered FM: two carriers for richer texture
    mod_freq1 = random.uniform(30.0, 120.0)
    mod_freq2 = random.uniform(60.0, 240.0)
    mod_depth = chaos * 500.0
    mod1 = np.sin(2 * np.pi * mod_freq1 * t) * mod_depth
    mod2 = np.sin(2 * np.pi * mod_freq2 * t) * (mod_depth * 0.4)

    carrier = (
        np.sin(2 * np.pi * 50.0 * t + mod1) * 0.15
        + np.sin(2 * np.pi * 80.0 * t + mod2) * 0.08
    ).astype(np.float32)

    # Granular stutter — FIXED: only copy when i >= grain (non-empty source slice)
    grain = max(1, int(sr * 0.04))
    for i in range(0, n - grain, grain):
        if i >= grain and random.random() < stutter_prob:
            carrier[i:i + grain] = carrier[i - grain:i]

    # Chaos-driven pitch sweep section (adds an eerie whine at high chaos)
    if chaos > 1.5:
        sweep_len = int(sr * random.uniform(0.1, 0.5))
        sweep_start = random.randint(0, max(0, n - sweep_len))
        sweep_t = t[sweep_start:sweep_start + sweep_len]
        sweep_freq = np.linspace(200, 2000 * chaos, len(sweep_t))
        carrier[sweep_start:sweep_start + sweep_len] += (
            np.sin(2 * np.pi * sweep_freq * sweep_t) * 0.05
        ).astype(np.float32)

    # Saturation
    audio = np.tanh(carrier * (2.0 + chaos)).astype(np.float32)
    return (audio * 32767).astype(np.int16), sr


# -------------------- VIDEO CORE --------------------

def extract_frames(inp: Path, out_pattern: Path, fps: int):
    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-err_detect", "ignore_err",
        "-i", str(inp),
        "-vf", f"scale=480:360:flags=lanczos,fps={fps}",
        "-vsync", "0",
        "-start_number", "0",
        str(out_pattern),
    ]
    run(cmd)

def mux(frames_pattern: Path, fps: int, wav_path: Path, out_mp4: Path, crf: int):
    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", str(frames_pattern),
        "-i", str(wav_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-crf", str(crf),
        "-preset", "ultrafast",
        "-shortest",
        str(out_mp4),
    ]
    run(cmd)

def optical_flow(prev_bgr, curr_bgr):
    prev_g = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.calcOpticalFlowFarneback(prev_g, curr_g, None, 0.5, 3, 15, 3, 5, 1.2, 0)

def smear(canvas, flow, drag: float):
    h, w = canvas.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    map_x = (gx + flow[:, :, 0] * float(drag)).astype(np.float32)
    map_y = (gy + flow[:, :, 1] * float(drag)).astype(np.float32)
    return cv2.remap(canvas, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# -------------------- MAIN PROCESSING LOOP --------------------

def process_video(args):
    check_ffmpeg()

    v1 = Path(args.v1).expanduser().resolve()
    v2 = Path(args.v2).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()

    if not v1.exists():
        die(f"V1 not found: {v1}")
    if not v2.exists():
        die(f"V2 not found: {v2}")

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    tmp = Path(tempfile.mkdtemp(prefix="hyper_ludovico_v13_"))
    print(">> INITIALIZING V13 ENGINE | MODE: FULL ENTROPY LOTTERY")
    print(f">> WORKDIR: {tmp}")

    try:
        print(f">> Extracting V1: {v1}")
        extract_frames(v1, tmp / "v1_%05d.png", args.fps)

        print(f">> Extracting V2: {v2}")
        extract_frames(v2, tmp / "v2_%05d.png", args.fps)

        v1_f = sorted(tmp.glob("v1_*.png"))
        v2_f = sorted(tmp.glob("v2_*.png"))

        if not v1_f:
            die("FATAL: Could not extract frames from V1.")
        if not v2_f:
            print(">> WARNING: V2 extracted 0 frames; injection will be disabled.")

        n1, n2 = len(v1_f), len(v2_f)
        if n2 > 0:
            start_idx = random.randint(0, max(0, n1 - n2))
            print(f">> INJECTING V2 (FULL CLIP) AT FRAME {start_idx} (len={n2})")
        else:
            start_idx = -999999

        first = safe_imread(v1_f[0])
        if first is None:
            die(f"FATAL: Failed to read first frame: {v1_f[0]}")

        canvas = first.copy()
        prev_source = first.copy()
        echo_buffer = None          # for datamosh_echo
        accumulator = None          # for feedback

        out_dir = tmp / "render"
        out_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_dir / "f_00000.png"), canvas)

        drag   = max(0.0, float(args.drag))
        chaos  = max(0.01, float(args.chaos))
        chroma = max(0.0, float(args.chroma))
        tear   = clamp01(args.tear)

        refresh_p = max(0.01, min(0.20, 0.05 / chaos))

        print(f">> PARAMS: fps={args.fps} drag={drag} chaos={chaos} chroma={chroma} "
              f"tear={tear} stutter={clamp01(args.stutter)}")
        print(f">> refresh_p={refresh_p:.3f}")

        for i in range(1, n1):
            curr_source = safe_imread(v1_f[i])
            if curr_source is None:
                print(f">> WARNING: unreadable frame {v1_f[i]} (skipping)")
                continue

            flow = optical_flow(prev_source, curr_source)

            # ---- Smear or refresh ----
            if random.random() > refresh_p:
                canvas = smear(canvas, flow, drag)
            else:
                if n2 > 0 and (start_idx <= i < start_idx + n2):
                    inj = safe_imread(v2_f[i - start_idx])
                    canvas = inj if inj is not None else curr_source.copy()
                else:
                    canvas = curr_source.copy()

            # ---- Per-frame glitch lottery ----
            modes = pick_glitch_modes(chaos)
            fx = canvas.copy()

            if "chroma" in modes:
                fx = apply_chroma_bleed(fx, chroma * random.uniform(0.5, 2.0))

            if "tear" in modes:
                fx = apply_luma_tear(fx, tear * random.uniform(0.5, 2.5))

            if "rgb_split" in modes:
                fx = apply_rgb_split(fx, clamp01(chaos * 0.25) * random.uniform(0.5, 1.5))

            if "vhs_noise" in modes:
                fx = apply_vhs_noise(fx, clamp01(chaos * 0.15) * random.uniform(0.5, 1.5))

            if "pixel_sort" in modes:
                fx = apply_pixel_sort(fx, clamp01(chaos * 0.2) * random.uniform(0.3, 1.0))

            if "block" in modes:
                fx = apply_block_scramble(fx, clamp01(chaos * 0.2) * random.uniform(0.3, 1.2))

            if "scanline" in modes:
                fx = apply_scanline_burn(fx, clamp01(chaos * 0.2) * random.uniform(0.4, 1.5))

            if "luma_invert" in modes:
                fx = apply_luma_invert(fx, clamp01(chaos * 0.1) * random.uniform(0.3, 1.0))

            if "echo" in modes:
                fx = apply_datamosh_echo(fx, echo_buffer, clamp01(chaos * 0.2))

            if "feedback" in modes:
                fx, accumulator = apply_feedback_accumulator(
                    fx, accumulator, clamp01(chaos * 0.2)
                )
            elif accumulator is None:
                accumulator = fx.copy().astype(np.float32)

            # Update echo buffer periodically (not every frame, or it's just current)
            if i % max(1, int(args.fps * 0.25)) == 0:
                echo_buffer = canvas.copy()

            # Ghost blend with source
            final = cv2.addWeighted(fx, 0.88, curr_source, 0.12, 0.0)
            cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final)
            prev_source = curr_source

            if i % 50 == 0:
                pct = int(i / max(1, n1) * 100)
                print(f"  Progress: {pct}% ({i}/{n1})  modes={sorted(modes)}")

        # ---- Audio ----
        duration = max(1.0, (n1 - 1) / float(args.fps))
        audio_data, sr = synth_experimental_audio(duration, chaos, args.stutter)

        audio_path = tmp / "s.wav"
        with wave.open(str(audio_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(audio_data.tobytes())

        print(">> FINAL MUXING...")
        mux(out_dir / "f_%05d.png", args.fps, audio_path, out, args.crf)
        print(f">> SUCCESS: {out}")

    finally:
        if args.keep_tmp:
            print(f">> KEEPING WORKDIR: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HYPER-LUDOVICO V13 video mosher")
    parser.add_argument("--v1",      required=True,          help="Primary input video")
    parser.add_argument("--v2",      required=True,          help="Injection video")
    parser.add_argument("--drag",    type=float, default=1.0,  help="Optical-flow smear intensity")
    parser.add_argument("--chaos",   type=float, default=2.5,  help="Global chaos (scales all effects)")
    parser.add_argument("--chroma",  type=float, default=1.0,  help="Chroma bleed base intensity")
    parser.add_argument("--tear",    type=float, default=0.1,  help="Luma-tear probability [0..1]")
    parser.add_argument("--stutter", type=float, default=0.1,  help="Audio stutter probability [0..1]")
    parser.add_argument("--crf",     type=int,   default=24,   help="Video CRF quality")
    parser.add_argument("--fps",     type=int,   default=24,   help="Output frame rate")
    parser.add_argument("--out",     default="output_entropy.mp4")
    parser.add_argument("--seed",    type=int,   default=None, help="RNG seed for reproducibility")
    parser.add_argument("--keep-tmp", action="store_true",    help="Keep temp working directory")
    args = parser.parse_args()
    process_video(args)
