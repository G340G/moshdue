#!/usr/bin/env python3
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

# -------------------- ADVANCED CONFIG --------------------

BASE_SETTINGS = {
    "fps": 24,
    "internal_res": (480, 360), # 4:3 aspect ratio for that old-school feel
    "decay": 0.98,
    "flow_scaling": 1.5,        # Strength of optical flow drag
    "bitflip_prob": 0.0005,     # Subtle but lethal byte corruption
    "vhs_noise_strength": 15,
}

# -------------------- THE PHYSICS OF DECAY --------------------

def apply_optical_flow_mosh(curr, prev, accumulation, flow_scale=1.0):
    """
    Uses Farneback Optical Flow to move pixels from the 'accumulation' 
    buffer based on the motion between curr and prev.
    """
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    
    # Calculate motion vectors
    flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    
    h, w = accumulation.shape[:2]
    y, x = np.mgrid[0:h, 0:w].reshape(2, -1).astype(np.float32)
    
    # Apply flow to the coordinates
    fx, fy = flow[:,:,0], flow[:,:,1]
    nx = np.clip(x + fx.reshape(-1) * flow_scale, 0, w-1)
    ny = np.clip(y + fy.reshape(-1) * flow_scale, 0, h-1)
    
    # Remap the accumulation buffer to the new moving coordinates
    moshed = cv2.remap(accumulation, nx.reshape(h, w), ny.reshape(h, w), cv2.INTER_LINEAR)
    return moshed

def vhs_tape_rot(img, chaos):
    """Adds head-switching noise and luma tracking errors."""
    h, w, _ = img.shape
    out = img.copy()
    
    # 1. Head switching noise (bottom flicker)
    noise_h = random.randint(4, 10)
    out[h-noise_h:, :] = np.random.randint(0, 255, (noise_h, w, 3), dtype=np.uint8)
    
    # 2. Horizontal Luma Tearing (Low internet style)
    if random.random() < 0.1 * chaos:
        y_line = random.randint(0, h-1)
        shift = random.randint(-20, 20)
        out[y_line:] = np.roll(out[y_line:], shift, axis=1)
        
    # 3. Color Bleed (YUV shift)
    img_yuv = cv2.cvtColor(out, cv2.COLOR_BGR2YUV)
    img_yuv[:,:,1] = np.roll(img_yuv[:,:,1], random.randint(2, 5), axis=1) # Shift U
    out = cv2.cvtColor(img_yuv, cv2.COLOR_YUV2BGR)
    
    return out

# -------------------- AUDIO SYNTH --------------------

def synth_broken_stream(duration, sr=22050):
    """Produces 'rotting' audio: white noise mixed with digital stutter."""
    n_samples = int(duration * sr)
    # White noise base
    audio = np.random.uniform(-0.2, 0.2, n_samples)
    
    # Add 'digital scream' sine sweeps
    t = np.linspace(0, duration, n_samples)
    sweep = np.sin(2 * np.pi * np.cumsum(np.random.choice([50, 200, 1000], n_samples) * t/n_samples))
    audio += sweep * 0.1
    
    # Stutter effect
    chunk_size = int(sr * 0.05)
    for i in range(0, n_samples - chunk_size, chunk_size):
        if random.random() < 0.15:
            # Repeat a small chunk (digital lag)
            audio[i:i+chunk_size] = audio[max(0, i-chunk_size):i]
            
    audio = np.tanh(audio * 5.0) # Distort
    return (audio * 32767).astype(np.int16)

# -------------------- MAIN ENGINE --------------------

def process(v1, v2, out_name, chaos=2.0):
    tmp = tempfile.mkdtemp()
    w, h = BASE_SETTINGS["internal_res"]
    fps = BASE_SETTINGS["fps"]
    
    print(f">> Extracting to {tmp}...")
    # Fix: Ensure ffmpeg scales correctly and handles differing inputs
    for i, v in enumerate([v1, v2]):
        subprocess.run([
            "ffmpeg", "-i", v, "-vf", f"scale={w}:{h},fps={fps}", 
            f"{tmp}/v{i}_%04d.png"
        ], check=True, capture_output=True)

    v1_frames = sorted([f for f in os.listdir(tmp) if f.startswith("v0_")])
    v2_frames = sorted([f for f in os.listdir(tmp) if f.startswith("v1_")])
    
    accumulation = cv2.imread(os.path.join(tmp, v1_frames[0]))
    prev_frame = accumulation.copy()
    
    out_dir = os.path.join(tmp, "out")
    os.makedirs(out_dir)

    print(">> Moshing...")
    for i in range(1, len(v1_frames)):
        curr = cv2.imread(os.path.join(tmp, v1_frames[i]))
        
        # Determine if we 'mosh' or 'reset' (I-frame logic)
        if random.random() > 0.05: # 95% chance to keep moshing
            # Drag pixels using Optical Flow
            accumulation = apply_optical_flow_mosh(curr, prev_frame, accumulation, flow_scale=chaos)
        else:
            # Sudden digital 'reset' to the other video
            if v2_frames:
                accumulation = cv2.imread(os.path.join(tmp, random.choice(v2_frames)))
        
        # Apply the "Rot" filters
        final_frame = vhs_tape_rot(accumulation, chaos)
        
        # Occasionally mix back the source to prevent total blackness
        if random.random() < 0.1:
            final_frame = cv2.addWeighted(final_frame, 0.7, curr, 0.3, 0)

        cv2.imwrite(os.path.join(out_dir, f"done_{i:04d}.png"), final_frame)
        prev_frame = curr
        if i % 24 == 0: print(f" Frame {i} processed...")

    # Render Output
    print(">> Finalizing...")
    audio_data = synth_broken_stream(len(v1_frames)/fps)
    audio_path = os.path.join(tmp, "audio.wav")
    with wave.open(audio_path, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
        wf.writeframes(audio_data.tobytes())

    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(fps), "-i", f"{out_dir}/done_%04d.png",
        "-i", audio_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", 
        "-crf", "28", "-preset", "veryfast", "-shortest", out_name
    ])
    shutil.rmtree(tmp)
    print(f">> Created: {out_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--chaos", type=float, default=2.0)
    parser.add_argument("--out", default="decay.mp4")
    args = parser.parse_args()
    process(args.v1, args.v2, args.out, args.chaos)
