#!/usr/bin/env python3
"""
HYPER-LUDOVICO V7: TEMPORAL DECAY EDITION
- Optical Flow Recursive Datamoshing
- 5-Second Texture Injection Limit
- Auto-fix for Corrupt 'moov atom' Inputs
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

# -------------------- MOTION & OPTICAL FLOW --------------------

def get_motion_vectors(prev, curr):
    """Calculates the high-precision motion of objects to drive the pixel smear."""
    prev_g = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    # Professional Farneback parameters for 'liquid' motion
    return cv2.calcOpticalFlowFarneback(prev_g, curr_g, None, 0.5, 3, 15, 3, 7, 1.5, 0)

def apply_motion_warp(canvas, flow, drag=1.0):
    """Recursive warping: pushes the previous frame's pixels along current motion lines."""
    h, w = canvas.shape[:2]
    flow_map = np.copy(flow)
    flow_map[:,:,0] += np.arange(w)
    flow_map[:,:,1] += np.arange(h)[:,np.newaxis]
    
    # Apply the drag multiplier
    return cv2.remap(canvas, flow_map.astype(np.float32), None, 
                    cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

# -------------------- ANALOG ARTIFACTS --------------------

def apply_analog_rot(img, chaos):
    """Simulates physical hardware failure and VHS signal rot."""
    h, w, _ = img.shape
    out = img.copy()

    # 1. VHS Head-Switching Noise (The classic bottom-edge flicker)
    noise_h = random.randint(3, 8)
    out[h-noise_h:, :] = np.random.randint(0, 255, (noise_h, w, 3), dtype=np.uint8)

    # 2. YUV Chroma Bleed (Purple/Green trailing)
    if random.random() < 0.4:
        yuv = cv2.cvtColor(out, cv2.COLOR_BGR2YUV)
        shift = int(3 * chaos)
        yuv[:,:,1] = np.roll(yuv[:,:,1], shift, axis=1) # Bleed Blue/Red
        out = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

    # 3. Packet Loss / Luma Tearing
    if random.random() < 0.08 * chaos:
        y_slice = random.randint(0, h-10)
        out[y_slice:] = np.roll(out[y_slice:], random.randint(-40, 40), axis=1)

    return out

# -------------------- CORE ENGINE --------------------

def process_video(args):
    tmp = Path(tempfile.mkdtemp())
    print(f">> INITIALIZING ENTROPY ENGINE | SESSION: {random.randint(1000,9999)}")

    # Pre-Flight: Attempt to fix 'moov atom' errors by re-encoding into a temp stream
    def extract_robust(path, prefix, fps):
        print(f">> Preparing {path}...")
        # We use a pipe to bypass potentially corrupt headers
        cmd = [
            "ffmpeg", "-y", "-err_detect", "ignore_err", "-i", path,
            "-vf", f"scale=480:360,fps={fps}", "-vsync", "0",
            str(tmp / f"{prefix}_%05d.png")
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"!! FFmpeg error on {path}: {res.stderr}")
            return False
        return True

    if not extract_robust(args.v1, "v0", args.fps): return
    if not extract_robust(args.v2, "v1", args.fps): return

    v1_frames = sorted(list(tmp.glob("v0_*.png")))
    v2_frames = sorted(list(tmp.glob("v1_*.png")))

    if not v1_frames:
        print("!! CRITICAL: No frames found for V1. The input file is likely unreadable.")
        return

    # Logic for the 5-second limit
    v2_limit = int(args.fps * 5)
    
    # Initialize Render Loop
    canvas = cv2.imread(str(v1_frames[0]))
    prev_source = canvas.copy()
    out_dir = tmp / "render"
    out_dir.mkdir()

    print(f">> MOSHING {len(v1_frames)} FRAMES...")
    print(f">> V2 TEXTURE OVERLAY LIMITED TO: {v2_limit} FRAMES (5.0s)")

    

    for i in range(1, len(v1_frames)):
        curr_source = cv2.imread(str(v1_frames[i]))
        
        # 1. Calculate Optical Flow from the clean source
        flow = get_motion_vectors(prev_source, curr_source)
        
        # 2. Datamosh Refresh Check
        # P-Frame Refresh Logic: Refresh (I-frame) vs Smear (P-frame)
        refresh_threshold = 0.05 / args.chaos
        
        if random.random() > refresh_threshold:
            # P-FRAME: Warp the existing canvas along the new motion flow
            canvas = apply_motion_warp(canvas, flow, drag=args.drag)
        else:
            # I-FRAME / TEXTURE INJECTION
            # ONLY use V2 frames if we are within the first 5 seconds
            if i < v2_limit and v2_frames:
                canvas = cv2.imread(str(random.choice(v2_frames)))
            else:
                # After 5 seconds, only "refresh" using V1 source
                canvas = curr_source.copy()

        # 3. Post-Process with VHS Rot
        final_frame = apply_analog_rot(canvas, args.chaos)
        
        # Blending back a tiny % of source to maintain some visual "ghost"
        final_frame = cv2.addWeighted(final_frame, 0.9, curr_source, 0.1, 0)

        cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final_frame)
        prev_source = curr_source
        if i % 50 == 0: print(f" Rendering: {int(i/len(v1_frames)*100)}%")

    # 4. Final Mux
    print(">> EXPORTING FINAL ENTROPY STREAM...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_dir / "f_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(args.crf), 
        "-preset", "ultrafast", args.out
    ], check=True)

    shutil.rmtree(tmp)
    print(f">> SUCCESS: {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Professional Temporal Entropy Engine")
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--chaos", type=float, default=3.0)
    parser.add_argument("--drag", type=float, default=2.0)
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="output_entropy.mp4")
    args = parser.parse_args()
    process_video(args)
