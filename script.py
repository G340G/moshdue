#!/usr/bin/env python3
"""
HYPER-LUDOVICO V8: SONIC DECAY EDITION
- Optical Flow Motion Smearing
- 5-Second V2 Texture Limit
- Experimental Granular/FM Audio Synth
- Robust FFmpeg Piping
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

# -------------------- AUDIO EXPERIMENTATION ENGINE --------------------

def synth_experimental_audio(duration, chaos, fps):
    """Generates a professional 'glitch-art' soundscape."""
    sr = 44100
    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples)
    
    # 1. Base Layer: VHS Noise Floor + 50Hz Hum
    # We add 'wow and flutter' by modulating the frequency of the hum
    flutter = np.sin(2 * np.pi * 3.0 * t) * 2.0  # 3Hz oscillation
    hum = np.sin(2 * np.pi * (50 + flutter) * t) * 0.1
    noise = np.random.uniform(-0.05, 0.05, n_samples)
    
    audio = hum + noise
    
    # 

[Image of frequency modulation synthesis]

    
    # 2. Granular Stutter (Digital 'Hang-ups')
    # We repeat tiny slices of the buffer to sound like a crash
    grain_size = int(sr * 0.05) 
    for i in range(0, n_samples - grain_size, grain_size):
        if random.random() < (0.15 * chaos):
            # Repeat the previous grain
            audio[i:i+grain_size] = audio[max(0, i-grain_size):i]
            
    # 3. FM Screams (Frequency Modulation)
    # Violent digital spikes that trigger during high-chaos moments
    for _ in range(int(duration * chaos)):
        start = random.randint(0, n_samples - int(sr*0.2))
        length = random.randint(int(sr*0.01), int(sr*0.1))
        freq = random.uniform(400, 2000)
        audio[start:start+length] += np.sin(2 * np.pi * freq * t[start:start+length]) * 0.3

    # 4. Bit-Crushing & Distortion
    # Reducing the 'precision' of the audio for a harsh digital look
    steps = 16 - int(chaos * 2) # Higher chaos = fewer bits
    audio = np.round(audio * steps) / steps
    audio = np.tanh(audio * (2.0 * chaos)) # Professional saturation
    
    return (audio * 32767).astype(np.int16), sr

# -------------------- VISUAL DECAY ENGINE --------------------

def get_flow(prev, curr):
    """Tracks pixel velocity to drive the 'liquid' smear."""
    p_g = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    c_g = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    return cv2.calcOpticalFlowFarneback(p_g, c_g, None, 0.5, 3, 15, 3, 5, 1.2, 0)

def apply_mosh_warp(canvas, flow, drag):
    h, w = canvas.shape[:2]
    m = np.copy(flow)
    m[:,:,0] += np.arange(w)
    m[:,:,1] += np.arange(h)[:,np.newaxis]
    return cv2.remap(canvas, m.astype(np.float32), None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

# -------------------- MAIN PROCESSOR --------------------

def process_video(args):
    tmp = Path(tempfile.mkdtemp())
    print(f">> INITIALIZING EXPERIMENTAL ENGINE | WORKDIR: {tmp}")

    # Robust Frame Extraction (Skips corrupt MOOV atoms)
    def extract(path, prefix):
        print(f">> Extracting {path}...")
        subprocess.run([
            "ffmpeg", "-y", "-err_detect", "ignore_err", "-i", path,
            "-vf", f"scale=480:360,fps={args.fps}", str(tmp / f"{prefix}_%05d.png")
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    extract(args.v1, "v1")
    extract(args.v2, "v2")

    v1_frames = sorted(list(tmp.glob("v1_*.png")))
    v2_frames = sorted(list(tmp.glob("v2_*.png")))
    
    if not v1_frames: raise ValueError("V1 extraction failed. Check if file is valid.")

    v2_limit = int(args.fps * 5) # Exactly 5 seconds
    canvas = cv2.imread(str(v1_frames[0]))
    prev_source = canvas.copy()
    out_dir = tmp / "frames"
    out_dir.mkdir()

    print(f">> MOSHING {len(v1_frames)} FRAMES (V2 LIMIT: 5s)...")

    for i in range(1, len(v1_frames)):
        curr_source = cv2.imread(str(v1_frames[i]))
        flow = get_flow(prev_source, curr_source)
        
        # Datamosh logic: Smear unless we trigger a 'refresh'
        if random.random() > (0.05 / args.chaos):
            canvas = apply_mosh_warp(canvas, flow, args.drag)
        else:
            # Texture injection only for first 5 seconds
            if i < v2_limit and v2_frames:
                canvas = cv2.imread(str(random.choice(v2_frames)))
            else:
                canvas = curr_source.copy()

        # Add VHS analog artifacts
        h, w, _ = canvas.shape
        # Chroma Bleed
        yuv = cv2.cvtColor(canvas, cv2.COLOR_BGR2YUV)
        yuv[:,:,1] = np.roll(yuv[:,:,1], int(2 * args.chaos), axis=1)
        canvas = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        
        # Save frame
        cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), canvas)
        prev_source = curr_source
        if i % 50 == 0: print(f"  Rendering: {int(i/len(v1_frames)*100)}%")

    # Audio Generation
    duration = len(v1_frames) / args.fps
    print(f">> SYNTHESIZING EXPERIMENTAL AUDIO ({duration:.2f}s)...")
    audio_data, sr = synth_experimental_audio(duration, args.chaos, args.fps)
    audio_path = tmp / "experimental.wav"
    with wave.open(str(audio_path), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    # Final Mux (Corrected with Audio Mapping)
    print(">> FINAL MULTIPLEXING...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_dir / "f_%05d.png"),
        "-i", str(audio_path), "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-crf", str(args.crf), "-preset", "ultrafast", 
        "-shortest", args.out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    shutil.rmtree(tmp)
    print(f">> PROCESS COMPLETE: {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--chaos", type=float, default=2.5)
    parser.add_argument("--drag", type=float, default=1.0)
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="decay_output.mp4")
    args = parser.parse_args()
    process_video(args)
