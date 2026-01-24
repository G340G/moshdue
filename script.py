#!/usr/bin/env python3
"""
HYPER-LUDOVICO V9: TOTAL ENTROPY ENGINE
- Professional Optical Flow (Farneback)
- 5-Second Texture Injection (V2)
- Experimental FM + Granular Sonic Engine
- Corrupt-Header (moov atom) Robustness
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

# -------------------- SONIC EXPERIMENTATION (FM SYNTH) --------------------

def synth_experimental_audio(duration, chaos):
    """
    Generates professional glitch-art audio using FM Synthesis.
    A 'Modulator' wave shifts the frequency of a 'Carrier' wave.
    """
    sr = 44100
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples)
    
    # 1. FM Synthesis: Carrier (pitch) modulated by a high-depth Modulator
    # This creates metallic, 'robotic' screaming textures
    mod_freq = random.uniform(20, 150)
    mod_depth = 500 * chaos
    modulator = np.sin(2 * np.pi * mod_freq * t) * mod_depth
    
    carrier_freq = 60 # Low bass hum
    audio = np.sin(2 * np.pi * carrier_freq * t + modulator) * 0.2
    
    # 2. Granular Stutter
    # Repeats tiny fragments of audio to simulate a digital crash
    grain_size = int(sr * 0.04) 
    for i in range(0, n_samples - grain_size, grain_size):
        if random.random() < (0.12 * chaos):
            audio[i:i+grain_size] = audio[max(0, i-grain_size):i]
            
    # 3. Harsh Distortion & Soft Clipping
    audio = np.clip(audio * (3.0 * chaos), -0.9, 0.9)
    audio = np.tanh(audio * 2.0) # Professional saturation
    
    return (audio * 32767).astype(np.int16), sr

# -------------------- VISUAL RECURSION ENGINE --------------------

def get_motion_vectors(prev, curr):
    """Calculates professional motion flow between frames."""
    prev_g = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    # Farneback algorithm for 'liquid' motion tracking
    return cv2.calcOpticalFlowFarneback(prev_g, curr_g, None, 0.5, 3, 15, 3, 5, 1.2, 0)

def apply_mosh_warp(canvas, flow, drag=1.0):
    """Recursive pixel dragging: pushes existing pixels along motion vectors."""
    h, w = canvas.shape[:2]
    flow_map = np.copy(flow)
    flow_map[:,:,0] += np.arange(w)
    flow_map[:,:,1] += np.arange(h)[:,np.newaxis]
    return cv2.remap(canvas, flow_map.astype(np.float32), None, 
                    cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

# -------------------- MAIN PROCESSOR --------------------

def process_entropy(args):
    tmp = Path(tempfile.mkdtemp())
    print(f">> INITIALIZING ENGINE | SESSION_ID: {random.randint(100,999)}")

    # Robust Frame Extraction (Ignores header errors / moov atom issues)
    def extract_robust(path, prefix):
        print(f">> Analyzing {path}...")
        subprocess.run([
            "ffmpeg", "-y", "-err_detect", "ignore_err", "-i", path,
            "-vf", f"scale=480:360,fps={args.fps}", str(tmp / f"{prefix}_%05d.png")
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    extract_robust(args.v1, "v1")
    extract_robust(args.v2, "v2")

    v1_frames = sorted(list(tmp.glob("v1_*.png")))
    v2_frames = sorted(list(tmp.glob("v2_*.png")))

    if not v1_frames:
        print("!! ERROR: V1 extraction failed. Ensure input.mp4 is not empty.")
        return

    # Logic: Texture (V2) is only used for the first 5 seconds
    v2_limit = int(args.fps * 5)
    
    canvas = cv2.imread(str(v1_frames[0]))
    prev_source = canvas.copy()
    out_dir = tmp / "render"
    out_dir.mkdir()

    print(f">> MOSHING {len(v1_frames)} FRAMES...")

    

    for i in range(1, len(v1_frames)):
        curr_source = cv2.imread(str(v1_frames[i]))
        
        # Calculate Optical Flow for professional smearing
        flow = get_motion_vectors(prev_source, curr_source)
        
        # Datamosh Logic: Refresh vs Smear
        if random.random() > (0.05 / args.chaos):
            # SMEAR: Warp the previous canvas based on current motion
            canvas = apply_mosh_warp(canvas, flow, drag=args.drag)
        else:
            # REFRESH / INJECT
            if i < v2_limit and v2_frames:
                # Use a random texture frame from V2 (First 5 seconds only)
                canvas = cv2.imread(str(random.choice(v2_frames)))
            else:
                # Use the current real frame from V1
                canvas = curr_source.copy()

        # Apply Analog Visual Rot (Chroma Bleed)
        yuv = cv2.cvtColor(canvas, cv2.COLOR_BGR2YUV)
        yuv[:,:,1] = np.roll(yuv[:,:,1], int(3 * args.chaos), axis=1)
        canvas = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        
        # Overlay tiny bit of original for 'ghosting' effect
        final = cv2.addWeighted(canvas, 0.9, curr_source, 0.1, 0)
        
        cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final)
        prev_source = curr_source
        if i % 30 == 0: print(f" Rendering: {int(i/len(v1_frames)*100)}%")

    # Audio Muxing
    duration = len(v1_frames) / args.fps
    print(f">> SYNTHESIZING SONIC ENTROPY ({duration:.2f}s)...")
    audio_data, sr = synth_experimental_audio(duration, args.chaos)
    audio_path = tmp / "sonic.wav"
    with wave.open(str(audio_path), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    print(">> FINAL MULTIPLEXING...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_dir / "f_%05d.png"),
        "-i", str(audio_path), "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-crf", str(args.crf), "-preset", "ultrafast", 
        "-shortest", args.out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    shutil.rmtree(tmp)
    print(f">> SUCCESS: {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--chaos", type=float, default=2.5)
    parser.add_argument("--drag", type=float, default=1.0)
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="entropy_final.mp4")
    args = parser.parse_args()
    process_entropy(args)
