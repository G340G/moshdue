#!/usr/bin/env python3
"""
HYPER-LUDOVICO: PROFESSIONAL ENTROPY ENGINE (V4.2)
- Advanced Optical Flow Datamoshing
- VHS / Low-Bitrate Internet Decay
- Harsh Noise Stutter Synth
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
import struct
from pathlib import Path

# -------------------- CORE ENGINE --------------------

def apply_optical_flow_mosh(curr, prev, accumulation, flow_scale=1.0, drag=1.0):
    """
    Calculates motion between frames and warps the persistent 'accumulation' 
    buffer to follow that motion. This is the 'Professional' datamosh look.
    """
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    
    # Calculate motion vectors (Farneback Algorithm)
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, curr_gray, None, 
        pyr_scale=0.5, levels=3, winsize=15, 
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
    )
    
    h, w = accumulation.shape[:2]
    y, x = np.mgrid[0:h, 0:w].reshape(2, -1).astype(np.float32)
    
    # Extract flow vectors
    fx, fy = flow[:,:,0], flow[:,:,1]
    
    # Warp coordinates based on motion * drag
    nx = np.clip(x + fx.reshape(-1) * flow_scale * drag, 0, w-1)
    ny = np.clip(y + fy.reshape(-1) * flow_scale * drag, 0, h-1)
    
    # Remap the accumulation buffer to new coordinates
    moshed = cv2.remap(accumulation, nx.reshape(h, w), ny.reshape(h, w), cv2.INTER_LINEAR)
    return moshed

def apply_entropy_filters(img, chaos):
    """Adds VHS head-switching noise, luma tearing, and color rot."""
    h, w, _ = img.shape
    out = img.copy()
    
    # 1. VHS Head Switching (Bottom static line)
    if random.random() < 0.9:
        noise_h = random.randint(4, 8)
        out[h-noise_h:, :] = np.random.randint(0, 255, (noise_h, w, 3), dtype=np.uint8)
    
    # 2. Horizontal Tearing (Packet Loss / Low Internet)
    if random.random() < 0.15 * chaos:
        y_start = random.randint(0, h-20)
        y_end = y_start + random.randint(5, 50)
        shift = random.randint(-30, 30)
        out[y_start:y_end] = np.roll(out[y_start:y_end], shift, axis=1)
        
    # 3. YUV Chroma Bleed (Analog Rot)
    if random.random() < 0.4:
        img_yuv = cv2.cvtColor(out, cv2.COLOR_BGR2YUV)
        img_yuv[:,:,1] = np.roll(img_yuv[:,:,1], random.randint(1, 4), axis=1) # Shift U
        out = cv2.cvtColor(img_yuv, cv2.COLOR_YUV2BGR)
    
    return out

# -------------------- AUDIO SYNTH --------------------

def synth_broken_audio(duration, chaos=2.0, drag=1.0):
    """Produces 'rotting' audio: white noise + digital stutter + clipping."""
    sr = 22050
    n_samples = int(duration * sr)
    # Harsh Noise Base
    audio = np.random.uniform(-0.3, 0.3, n_samples)
    
    # Digital Stutter (Granular repetition)
    chunk_size = int(sr * 0.04)
    for i in range(0, n_samples - chunk_size, chunk_size):
        if random.random() < (0.1 * chaos):
            # Repeat previous chunk to simulate lag
            audio[i:i+chunk_size] = audio[max(0, i-chunk_size):i]
            
    # Add digital 'screams' (sine sweeps)
    t = np.linspace(0, duration, n_samples)
    mod = np.sin(2 * np.pi * random.uniform(50, 500) * t)
    audio = (audio + mod * 0.15) * (1.5 * drag)
    
    # Extreme Distortion (Hard Clip)
    audio = np.tanh(audio * 4.0)
    return (audio * 32767).astype(np.int16), sr

# -------------------- PROCESSOR --------------------

def process_video(args):
    tmp = Path(tempfile.mkdtemp())
    w, h = 480, 360 # Classic 4:3 VHS ratio
    if args.internal_res:
        w, h = map(int, args.internal_res.split('x'))

    print(f">> INITIALIZING ENTROPY ENGINE | SEED: {random.randint(0,999)}")
    
    # Extract Frames
    for i, v in enumerate([args.v1, args.v2]):
        subprocess.run([
            "ffmpeg", "-y", "-i", v, "-vf", f"scale={w}:{h},fps={args.fps}", 
            f"{tmp}/v{i}_%05d.png"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    v1_frames = sorted(list(tmp.glob("v0_*.png")))
    v2_frames = sorted(list(tmp.glob("v1_*.png")))
    
    if not v1_frames: raise ValueError("No frames extracted from V1.")

    accumulation = cv2.imread(str(v1_frames[0]))
    prev_frame = accumulation.copy()
    
    out_dir = tmp / "out"
    out_dir.mkdir()

    print(f">> MOSHING {len(v1_frames)} FRAMES...")
    
    

    for i in range(1, len(v1_frames)):
        curr = cv2.imread(str(v1_frames[i]))
        
        # Datamosh Logic: P-Frame Smear
        # 95% of frames 'mosh' (drag accumulation), 5% 'reset' (bring in new image)
        if random.random() > (0.05 / args.chaos):
            accumulation = apply_optical_flow_mosh(
                curr, prev_frame, accumulation, 
                flow_scale=args.chaos, drag=args.drag
            )
        else:
            # Inject texture from V2
            idx2 = i % len(v2_frames) if v2_frames else 0
            accumulation = cv2.imread(str(v2_frames[idx2]))
        
        # Apply Rot/VHS Filters
        final = apply_entropy_filters(accumulation, args.chaos)
        
        # Subtle blend with source to keep some detail
        final = cv2.addWeighted(final, 0.85, curr, 0.15, 0)

        cv2.imwrite(str(out_dir / f"frame_{i:05d}.png"), final)
        prev_frame = curr
        if i % 30 == 0: print(f" Rendering: {int(i/len(v1_frames)*100)}%")

    # Audio & Mux
    duration = len(v1_frames) / args.fps
    audio_data, sr = synth_broken_audio(duration, args.chaos, args.drag)
    audio_path = tmp / "noise.wav"
    with wave.open(str(audio_path), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    print(">> MUXING FINAL OUTPUT...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", f"{out_dir}/frame_%05d.png",
        "-i", str(audio_path), "-c:v", "libx264", "-pix_fmt", "yuv420p", 
        "-crf", str(args.crf), "-preset", "ultrafast", "-shortest", args.out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    shutil.rmtree(tmp)
    print(f">> COMPLETE: {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hyper-Ludovico Entropy Engine")
    parser.add_argument("--v1", required=True, help="Base video")
    parser.add_argument("--v2", required=True, help="Texture/Glitch video")
    parser.add_argument("--out", default="entropy_mosh.mp4")
    parser.add_argument("--chaos", type=float, default=2.0, help="Glitch intensity")
    parser.add_argument("--drag", type=float, default=1.0, help="Motion smear length")
    parser.add_argument("--crf", type=int, default=24, help="Compression artifacts")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--internal-res", default="480x360")
    
    args = parser.parse_args()
    process_video(args)
