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

# -------------------- PROFESSIONAL DECAY ALGORITHMS --------------------

def get_motion_vectors(prev, curr):
    """Calculates Farneback Optical Flow for professional-grade pixel melting."""
    prev_g = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    # Professional settings for deep motion tracking
    flow = cv2.calcOpticalFlowFarneback(prev_g, curr_g, None, 0.5, 3, 15, 3, 7, 1.5, 0)
    return flow

def apply_smear(img, flow, strength=1.0):
    """Warps pixels along motion paths (the liquid datamosh look)."""
    h, w = img.shape[:2]
    flow_map = np.copy(flow)
    flow_map[:,:,0] += np.arange(w)
    flow_map[:,:,1] += np.arange(h)[:,np.newaxis]
    
    # Warps the image using the calculated motion vectors
    return cv2.remap(img, flow_map.astype(np.float32), None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

def apply_analog_rot(img, chaos):
    """Simulates physical tape rot, head-switching noise, and chroma bleed."""
    h, w, c = img.shape
    out = img.copy()

    # 1. Head-Switching Noise (The classic VHS flickering bar at the bottom)
    noise_h = random.randint(3, 7)
    out[h-noise_h:, :] = np.random.randint(0, 255, (noise_h, w, 3), dtype=np.uint8)

    # 2. Chroma Desync (Purple/Green bleeding)
    if random.random() < 0.5:
        img_yuv = cv2.cvtColor(out, cv2.COLOR_BGR2YUV)
        shift = int(2 * chaos)
        img_yuv[:,:,1] = np.roll(img_yuv[:,:,1], shift, axis=1) # Shift U channel
        out = cv2.cvtColor(img_yuv, cv2.COLOR_YUV2BGR)

    # 3. Horizontal Slicing (Low bitrate 'packet loss' look)
    if random.random() < 0.1 * chaos:
        slice_y = random.randint(0, h-10)
        out[slice_y:] = np.roll(out[slice_y:], random.randint(-20, 20), axis=1)

    return out

# -------------------- NOISE SYNTHESIS --------------------

def synth_rotted_audio(duration, chaos):
    """Generates granular stuttering noise and digital screams."""
    sr = 22050
    n = int(duration * sr)
    audio = np.random.uniform(-0.15, 0.15, n)
    
    # Granular stutter (repeating tiny frames of sound)
    grain = int(sr * 0.03)
    for i in range(0, n - grain, grain):
        if random.random() < 0.15 * chaos:
            audio[i:i+grain] = audio[max(0, i-grain):i]
            
    # Add a digital 'hum' that fluctuates
    t = np.linspace(0, duration, n)
    hum = np.sin(2 * np.pi * 50 * t) * 0.1
    audio = np.clip((audio + hum) * (3.0 * chaos), -1, 1)
    return (audio * 32767).astype(np.int16), sr

# -------------------- MAIN PROCESSOR --------------------

def process_entropy(args):
    # Setup working directories
    tmp = Path(tempfile.mkdtemp())
    print(f">> INTERNAL WORKDIR: {tmp}")

    # Ensure absolute paths for FFmpeg to avoid 'No frames found'
    v1_path = os.path.abspath(args.v1)
    v2_path = os.path.abspath(args.v2)

    # 1. Extraction (Robust Mode)
    for i, v in enumerate([v1_path, v2_path]):
        print(f">> EXTRACTING V{i+1}: {v}")
        cmd = ["ffmpeg", "-y", "-i", v, "-vf", f"scale=480:360,fps={args.fps}", str(tmp / f"v{i}_%05d.png")]
        subprocess.run(cmd, check=True)

    v1_frames = sorted(list(tmp.glob("v0_*.png")))
    v2_frames = sorted(list(tmp.glob("v1_*.png")))

    if not v1_frames:
        raise FileNotFoundError("FFmpeg failed to extract frames. Check input file paths or formats.")

    # 2. The Moshing Loop
    canvas = cv2.imread(str(v1_frames[0]))
    prev_source = canvas.copy()
    
    out_dir = tmp / "render"
    out_dir.mkdir()

    print(f">> APPLYING DIGITAL ENTROPY (DRAG: {args.drag}, CHAOS: {args.chaos})...")

    

    for i in range(1, len(v1_frames)):
        curr_source = cv2.imread(str(v1_frames[i]))
        
        # Calculate Optical Flow
        flow = get_motion_vectors(prev_source, curr_source)
        
        # P-Frame Persistence Logic (The 'Melt')
        # We only 'refresh' the frame 5% of the time, causing 95% of frames to smear.
        if random.random() > (0.05 / args.chaos):
            canvas = apply_smear(canvas, flow, strength=args.drag)
        else:
            # Texture Injection from V2
            if v2_frames:
                canvas = cv2.imread(str(random.choice(v2_frames)))

        # Apply Visual Rot
        final_frame = apply_analog_rot(canvas, args.chaos)
        
        # Blend slightly with original to maintain "ghosts" of the subject
        final_frame = cv2.addWeighted(final_frame, 0.8, curr_source, 0.2, 0)

        cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final_frame)
        prev_source = curr_source
        if i % 50 == 0: print(f" Frame {i}/{len(v1_frames)} generated...")

    # 3. Audio & Muxing
    duration = len(v1_frames) / args.fps
    audio_data, sr = synth_rotted_audio(duration, args.chaos)
    audio_wav = tmp / "noise.wav"
    with wave.open(str(audio_wav), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    print(">> FINAL MUXING...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_dir / "f_%05d.png"),
        "-i", str(audio_wav), "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", str(args.crf), "-preset", "ultrafast", "-shortest", args.out
    ], check=True)

    print(f">> MISSION COMPLETE: {args.out}")
    shutil.rmtree(tmp)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Professional Entropy Video Engine")
    parser.add_argument("--v1", required=True, help="Main video input")
    parser.add_argument("--v2", required=True, help="Glitch texture input")
    parser.add_argument("--drag", type=float, default=2.5, help="Strength of pixel smearing")
    parser.add_argument("--chaos", type=float, default=3.0, help="Intensity of analog rot")
    parser.add_argument("--crf", type=int, default=24, help="Quality (higher = more artifacts)")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="output_entropy.mp4")
    args = parser.parse_args()
    process_entropy(args)
