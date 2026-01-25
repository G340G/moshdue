#!/usr/bin/env python3
"""
HYPER-LUDOVICO V12 (FIXED for GitHub runners)
- Full-length V2 injection (random start)
- Optical flow smear with correct remap maps
- Personalizable: --drag --chroma --tear --stutter --chaos
- FM + granular audio synth
- Robust ffmpeg calls with error reporting
- Safe frame reads, safe probabilities, always writes frame 00000
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
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        die("ffmpeg not found on PATH. On GitHub Actions: sudo apt-get install -y ffmpeg")

def run(cmd):
    """Run command with useful error output."""
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
    img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    return img

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# -------------------- PERSONALIZABLE ARTIFACTS --------------------

def apply_chroma_bleed(img, intensity: float):
    """Analog signal rot by shifting chroma channels."""
    intensity = float(intensity)
    if intensity <= 0:
        return img

    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    shift = int(max(0, intensity) * 4)
    if shift != 0:
        yuv[:, :, 1] = np.roll(yuv[:, :, 1], shift, axis=1)     # U
        yuv[:, :, 2] = np.roll(yuv[:, :, 2], -shift, axis=1)    # V
    return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

def apply_luma_tear(img, probability: float):
    """Digital packet loss with horizontal line tearing."""
    probability = clamp01(probability)
    if random.random() > probability:
        return img

    h, w = img.shape[:2]
    if h < 20:
        return img

    y_start = random.randint(0, h - 20)
    thickness = random.randint(2, min(40, h - y_start))
    shift = random.randint(-w // 3, w // 3)

    out = img.copy()
    out[y_start:y_start + thickness] = np.roll(out[y_start:y_start + thickness], shift, axis=1)
    return out


# -------------------- SONIC ENGINE (EXPERIMENTAL) --------------------

def synth_experimental_audio(duration: float, chaos: float, stutter_prob: float):
    """FM synthesis + granular stutter. Returns int16 mono wav data + sample rate."""
    chaos = max(0.0, float(chaos))
    stutter_prob = clamp01(stutter_prob)

    sr = 44100
    n = max(1, int(duration * sr))
    t = np.linspace(0.0, max(duration, 1e-6), n, dtype=np.float32)

    # FM synthesis (carrier around 50Hz for "powerline dread", modulator higher)
    mod_freq = random.uniform(30.0, 120.0)
    mod_depth = chaos * 500.0
    modulator = np.sin(2 * np.pi * mod_freq * t) * mod_depth

    carrier = np.sin(2 * np.pi * 50.0 * t + modulator).astype(np.float32) * 0.20

    # Granular stutter
    grain = max(1, int(sr * 0.04))
    for i in range(0, n - grain, grain):
        if random.random() < stutter_prob:
            carrier[i:i + grain] = carrier[max(0, i - grain):i]

    # Saturation & level
    audio = np.tanh(carrier * (2.0 + chaos)).astype(np.float32)
    return (audio * 32767).astype(np.int16), sr


# -------------------- VIDEO CORE --------------------

def extract_frames(inp: Path, out_pattern: Path, fps: int):
    """
    Robust extraction:
    - error log if fails
    - predictable numbering
    """
    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-err_detect", "ignore_err",
        "-i", str(inp),
        "-vf", f"scale=480:360:flags=lanczos,fps={fps}",
        "-vsync", "0",
        "-start_number", "0",
        str(out_pattern)
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
        str(out_mp4)
    ]
    run(cmd)

def optical_flow(prev_bgr, curr_bgr):
    prev_g = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.calcOpticalFlowFarneback(prev_g, curr_g, None, 0.5, 3, 15, 3, 5, 1.2, 0)

def smear(canvas, flow, drag: float):
    """
    Correct remap:
    map_x, map_y must be separate float32 arrays.
    """
    h, w = canvas.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
    map_x = (grid_x + flow[:, :, 0] * float(drag)).astype(np.float32)
    map_y = (grid_y + flow[:, :, 1] * float(drag)).astype(np.float32)
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

    # seed support (optional)
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    tmp = Path(tempfile.mkdtemp(prefix="hyper_ludovico_v12_"))
    print(">> INITIALIZING V12 ENGINE | MODE: PERSONALIZED ENTROPY")
    print(f">> WORKDIR: {tmp}")

    try:
        # Extract frames
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

        # Full-length injection window
        n1, n2 = len(v1_f), len(v2_f)
        if n2 > 0:
            start_idx = random.randint(0, max(0, n1 - n2))
            print(f">> INJECTING V2 (FULL CLIP) AT FRAME {start_idx} (len={n2})")
        else:
            start_idx = -999999

        # Init
        first = safe_imread(v1_f[0])
        if first is None:
            die(f"FATAL: Failed to read first frame: {v1_f[0]}")

        canvas = first.copy()
        prev_source = first.copy()

        out_dir = tmp / "render"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Important: write frame 00000 so ffmpeg pattern matches
        cv2.imwrite(str(out_dir / "f_00000.png"), canvas)

        drag = max(0.0, float(args.drag))
        chaos = max(0.01, float(args.chaos))  # avoid div/0
        chroma = max(0.0, float(args.chroma))
        tear = clamp01(args.tear)

        # Probability of refresh (I-frame replacement)
        # higher chaos => fewer refreshes => more smearing
        refresh_p = max(0.01, min(0.20, 0.05 / chaos))

        print(f">> PARAMS: fps={args.fps} drag={drag} chaos={chaos} chroma={chroma} tear={tear} stutter={clamp01(args.stutter)}")
        print(f">> refresh_p={refresh_p:.3f}")

        for i in range(1, n1):
            curr_source = safe_imread(v1_f[i])
            if curr_source is None:
                print(f">> WARNING: unreadable frame: {v1_f[i]} (skipping)")
                continue

            flow = optical_flow(prev_source, curr_source)

            # Smear vs refresh
            if random.random() > refresh_p:
                canvas = smear(canvas, flow, drag)
            else:
                # Refresh logic: inject V2 full clip if within window
                if n2 > 0 and (start_idx <= i < (start_idx + n2)):
                    inj = safe_imread(v2_f[i - start_idx])
                    canvas = inj if inj is not None else curr_source.copy()
                else:
                    canvas = curr_source.copy()

            # Visual FX
            canvas_fx = apply_chroma_bleed(canvas, chroma)
            canvas_fx = apply_luma_tear(canvas_fx, tear)

            # Ghost blend
            final = cv2.addWeighted(canvas_fx, 0.9, curr_source, 0.1, 0.0)

            cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final)
            prev_source = curr_source

            if i % 50 == 0:
                print(f"  Progress: {int(i / max(1, n1) * 100)}% ({i}/{n1})")

        # Audio synth + mux
        duration = (n1 - 1) / float(args.fps)
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--drag", type=float, default=1.0, help="Smear intensity")
    parser.add_argument("--chaos", type=float, default=2.5, help="Global chaos")
    parser.add_argument("--chroma", type=float, default=1.0, help="Color bleeding")
    parser.add_argument("--tear", type=float, default=0.1, help="Digital tearing probability [0..1]")
    parser.add_argument("--stutter", type=float, default=0.1, help="Audio stutter probability [0..1]")
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="output_entropy.mp4")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--keep-tmp", action="store_true")
    args = parser.parse_args()
    process_video(args)

