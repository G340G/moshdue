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
from pathlib import Path

# -------------------- ANALOG DECAY PHYSICS --------------------

def get_flow(prev, curr):
    """Calculates professional-grade motion vectors between frames."""
    prev_g = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(prev_g, curr_g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    return flow

def apply_flow_warp(img, flow, strength=1.0):
    """Warps pixels along motion vectors to create the 'melting' effect."""
    h, w = img.shape[:2]
    flow_map = np.copy(flow)
    flow_map[:,:,0] += np.arange(w)
    flow_map[:,:,1] += np.arange(h)[:,np.newaxis]
    
    # Apply chaos multiplier to the flow
    res = cv2.remap(img, flow_map.astype(np.float32), None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return res

def apply_vhs_rot(img, chaos):
    """Simulates physical tape damage and digital packet loss."""
    h, w, c = img.shape
    out = img.copy()

    # 1. Head-Switching Noise (The flickering bar at the bottom)
    if random.random() < 0.9:
        line_h = random.randint(2, 6)
        out[h-line_h:, :] = np.random.randint(0, 255, (line_h, w, 3), dtype=np.uint8)

    # 2. Horizontal Tearing (Low internet / Tracking error)
    if random.random() < 0.1 * chaos:
        y = random.randint(0, h-1)
        shift = random.randint(-40, 40)
        out[y:] = np.roll(out[y:], shift, axis=1)

    # 3. Chroma Ghosting (Color bleeding)
    img_yuv = cv2.cvtColor(out, cv2.COLOR_BGR2YUV)
    shift_amt = int(3 * chaos)
    img_yuv[:,:,1] = np.roll(img_yuv[:,:,1], shift_amt, axis=1) # Bleed Blue/Red
    out = cv2.cvtColor(img_yuv, cv2.COLOR_YUV2BGR)

    return out

# -------------------- HARSH NOISE ENGINE --------------------

def synth_broken_audio(duration, chaos=1.0):
    sr = 22050
    n_samples = int(duration * sr)
    # White noise mixed with low-freq hum
    noise = np.random.uniform(-0.2, 0.2, n_samples)
    
    # Digital Stuttering (Granular repeats)
    grain_size = int(sr * 0.05) 
    for i in range(0, n_samples - grain_size, grain_size):
        if random.random() < 0.2 * chaos:
            noise[i:i+grain_size] = noise[max(0, i-grain_size):i]
            
    # Hard clipping distortion
    noise = np.clip(noise * (5.0 * chaos), -1, 1)
    return (noise * 32767).astype(np.int16), sr

# -------------------- CORE PROCESSOR --------------------

def process_video(args):
    tmp = Path(tempfile.mkdtemp())
    print(f">> BOOTING ENTROPY ENGINE | WORKDIR: {tmp}")

    # Step 1: Robust Frame Extraction
    # We remove 'DEVNULL' so you can see if FFmpeg crashes
    for i, v in enumerate([args.v1, args.v2]):
        print(f">> Extracting Input {i+1}...")
        res = subprocess.run([
            "ffmpeg", "-y", "-i", v, 
            "-vf", f"scale=480:360,fps={args.fps}", 
            str(tmp / f"v{i}_%05d.png")
        ])
        if res.returncode != 0:
            print(f"!! ERROR: FFmpeg failed to read {v}. Check if the file exists and is a valid video.")
            return

    v1_frames = sorted(list(tmp.glob("v0_*.png")))
    v2_frames = sorted(list(tmp.glob("v1_*.png")))

    if not v1_frames:
        print("!! ERROR: No frames were extracted. Is the input file empty?")
        return

    # Initialize Buffers
    canvas = cv2.imread(str(v1_frames[0]))
    prev_source = canvas.copy()
    
    out_dir = tmp / "out"
    out_dir.mkdir()

    print(f">> MOSHING {len(v1_frames)} FRAMES (CHAOS: {args.chaos} | DRAG: {args.drag})...")

    

    for i in range(1, len(v1_frames)):
        curr_source = cv2.imread(str(v1_frames[i]))
        
        # Calculate Motion between source frames
        flow = get_flow(prev_source, curr_source)
        
        # P-Frame Logic: Should we keep moshing or 'refresh' the frame?
        # A 'Professional' mosh skips I-frames to let pixels melt.
        if random.random() > (0.04 / args.chaos):
            # Warp the existing canvas along the new motion
            canvas = apply_flow_warp(canvas, flow, strength=args.drag)
        else:
            # Sudden 'Digital Reset' or texture injection from V2
            if v2_frames:
                tex_idx = random.randint(0, len(v2_frames)-1)
                canvas = cv2.imread(str(v2_frames[tex_idx]))

        # Apply VHS/Internet Decay Filters
        final_frame = apply_vhs_rot(canvas, args.chaos)
        
        # Subtle blend back to reality (to prevent total blackness)
        final_frame = cv2.addWeighted(final_frame, 0.9, curr_source, 0.1, 0)

        cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final_frame)
        prev_source = curr_source
        
        if i % 50 == 0: print(f" Progress: {int(i/len(v1_frames)*100)}%")

    # Step 3: Audio & Final Mux
    duration = len(v1_frames) / args.fps
    audio_data, sr = synth_broken_audio(duration, args.chaos)
    audio_path = tmp / "audio.wav"
    with wave.open(str(audio_path), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    print(">> FINAL RENDER (Applying Compression Artifacts)...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_dir / "f_%05d.png"),
        "-i", str(audio_path), "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", str(args.crf), "-preset", "ultrafast", "-shortest", args.out
    ])

    shutil.rmtree(tmp)
    print(f">> SUCCESS: Created {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--chaos", type=float, default=2.5)
    parser.add_argument("--drag", type=float, default=2.0)
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="entropy_vhs.mp4")
    args = parser.parse_args()
    process_video(args)
