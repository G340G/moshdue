#!/usr/bin/env python3
"""
HYPER-LUDOVICO V10: QUANTUM INJECTION EDITION
- Random Full-Clip V2 Insertion
- Fully Personalizable Glitch Parameters
- Recursive Motion Smearing
- Professional FM/Granular Audio
"""

import os
import shutil
import subprocess
import random
import argparse
import tempfile
import numpy as np
import cv2
import wave
from pathlib import Path

# -------------------- PERSONALIZABLE ARTIFACTS --------------------

def apply_chroma_bleed(img, intensity):
    """Shifts color channels independently to simulate analog signal rot."""
    if intensity <= 0: return img
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    # Shift U and V channels horizontally
    shift = int(intensity * 5)
    yuv[:,:,1] = np.roll(yuv[:,:,1], shift, axis=1)
    yuv[:,:,2] = np.roll(yuv[:,:,2], -shift, axis=1)
    return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

def apply_luma_tear(img, probability):
    """Simulates packet loss or tracking errors with horizontal 'rolls'."""
    if random.random() > probability: return img
    h, w, _ = img.shape
    y_start = random.randint(0, h-20)
    slice_h = random.randint(5, 50)
    shift = random.randint(-w//4, w//4)
    img[y_start:y_start+slice_h] = np.roll(img[y_start:y_start+slice_h], shift, axis=1)
    return img

def apply_head_noise(img, frequency):
    """The classic VHS static bar at the bottom of the frame."""
    if random.random() > frequency: return img
    h, w, _ = img.shape
    noise_h = random.randint(2, 8)
    img[h-noise_h:, :] = np.random.randint(0, 255, (noise_h, w, 3), dtype=np.uint8)
    return img

# -------------------- AUDIO SYNTHESIS --------------------



[Image of frequency modulation synthesis]


def synth_professional_audio(duration, chaos, stutter_prob):
    sr = 44100
    n = int(duration * sr)
    t = np.linspace(0, duration, n)
    
    # FM Synthesis Base
    modulator = np.sin(2 * np.pi * random.uniform(20, 100) * t) * (chaos * 400)
    carrier = np.sin(2 * np.pi * 60 * t + modulator) * 0.2
    
    # Granular Stuttering
    grain = int(sr * 0.05)
    for i in range(0, n - grain, grain):
        if random.random() < stutter_prob:
            carrier[i:i+grain] = carrier[max(0, i-grain):i]
            
    # Professional Saturation
    audio = np.tanh(carrier * (2.0 + chaos))
    return (audio * 32767).astype(np.int16), sr

# -------------------- CORE ENGINE --------------------

def process_video(args):
    tmp = Path(tempfile.mkdtemp())
    print(f">> INITIALIZING QUANTUM ENGINE | TARGET: {args.out}")

    def extract(path, prefix):
        subprocess.run([
            "ffmpeg", "-y", "-err_detect", "ignore_err", "-i", path,
            "-vf", f"scale=480:360,fps={args.fps}", str(tmp / f"{prefix}_%05d.png")
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    extract(args.v1, "v1")
    extract(args.v2, "v2")

    v1_frames = sorted(list(tmp.glob("v1_*.png")))
    v2_frames = sorted(list(tmp.glob("v2_*.png")))
    
    if not v1_frames or not v2_frames:
        print("!! ERROR: Could not extract frames. Check input files.")
        return

    # Logic: Randomly place V2 (full length) inside V1
    n1, n2 = len(v1_frames), len(v2_frames)
    if n2 >= n1:
        start_idx = 0
    else:
        start_idx = random.randint(0, n1 - n2)
    
    print(f">> V2 INJECTION WINDOW: Frame {start_idx} to {start_idx + n2}")

    canvas = cv2.imread(str(v1_frames[0]))
    prev_source = canvas.copy()
    out_dir = tmp / "render"
    out_dir.mkdir()

    

    for i in range(1, n1):
        curr_source = cv2.imread(str(v1_frames[i]))
        
        # Calculate Motion Flow
        p_g = cv2.cvtColor(prev_source, cv2.COLOR_BGR2GRAY)
        c_g = cv2.cvtColor(curr_source, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(p_g, c_g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        
        # Datamosh Smear
        if random.random() > (0.05 / args.chaos):
            h, w = canvas.shape[:2]
            m = np.copy(flow)
            m[:,:,0] += np.arange(w)
            m[:,:,1] += np.arange(h)[:,np.newaxis]
            canvas = cv2.remap(canvas, m.astype(np.float32), None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        else:
            # Injection Logic
            v2_active = start_idx <= i < (start_idx + n2)
            if v2_active:
                canvas = cv2.imread(str(v2_frames[i - start_idx]))
            else:
                canvas = curr_source.copy()

        # Apply Personalized Glitches
        canvas = apply_chroma_bleed(canvas, args.chroma)
        canvas = apply_luma_tear(canvas, args.tear)
        canvas = apply_head_noise(canvas, args.head)
        
        # Subtle Blend
        final = cv2.addWeighted(canvas, 0.9, curr_source, 0.1, 0)
        cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final)
        prev_source = curr_source
        if i % 50 == 0: print(f" Rendering: {int(i/n1*100)}%")

    # Audio & Export
    duration = n1 / args.fps
    audio_data, sr = synth_professional_audio(duration, args.chaos, args.stutter)
    audio_path = tmp / "sonic.wav"
    with wave.open(str(audio_path), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_dir / "f_%05d.png"),
        "-i", str(audio_path), "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        "-crf", str(args.crf), "-preset", "ultrafast", "-shortest", args.out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    shutil.rmtree(tmp)
    print(f">> SUCCESS: {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Required Inputs
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    
    # Visual Personalization
    parser.add_argument("--chaos", type=float, default=2.5, help="Global glitch intensity")
    parser.add_argument("--chroma", type=float, default=1.0, help="Color bleeding intensity")
    parser.add_argument("--tear", type=float, default=0.1, help="Probability of luma tearing")
    parser.add_argument("--head", type=float, default=0.8, help="VHS head-noise frequency")
    
    # Audio Personalization
    parser.add_argument("--stutter", type=float, default=0.15, help="Audio grain repeat probability")
    
    # Render Settings
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="quantum_entropy.mp4")
    
    args = parser.parse_args()
    process_video(args)
