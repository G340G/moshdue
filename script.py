#!/usr/bin/env python3
"""
HYPER-LUDOVICO V12: THE FINAL ENTROPY ENGINE
- Random Full-Length V2 Injection
- Fully Personalizable: --drag, --chroma, --tear, --stutter, --chaos
- Optical Flow Recursive Smearing
- FM Synthesis / Granular Audio Synth
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
    """Simulates analog signal rot by shifting color channels."""
    if intensity <= 0: return img
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    shift = int(intensity * 4)
    yuv[:,:,1] = np.roll(yuv[:,:,1], shift, axis=1) # U-Channel shift
    yuv[:,:,2] = np.roll(yuv[:,:,2], -shift, axis=1) # V-Channel shift
    return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

def apply_luma_tear(img, probability):
    """Simulates digital packet loss with horizontal line tearing."""
    if random.random() > probability: return img
    h, w, _ = img.shape
    y_start = random.randint(0, h-20)
    thickness = random.randint(2, 40)
    shift = random.randint(-w//3, w//3)
    img[y_start:y_start+thickness] = np.roll(img[y_start:y_start+thickness], shift, axis=1)
    return img

# -------------------- SONIC ENGINE (EXPERIMENTAL) --------------------

def synth_experimental_audio(duration, chaos, stutter_prob):
    """Generates a professional glitch-art soundscape."""
    sr = 44100
    n = int(duration * sr)
    t = np.linspace(0, duration, n)
    
    # Frequency Modulation (FM) Synthesis
    # 

[Image of frequency modulation synthesis]

    mod_freq = random.uniform(30, 120)
    mod_depth = chaos * 500
    modulator = np.sin(2 * np.pi * mod_freq * t) * mod_depth
    carrier = np.sin(2 * np.pi * 50 * t + modulator) * 0.2
    
    # Granular Stutter
    grain = int(sr * 0.04)
    for i in range(0, n - grain, grain):
        if random.random() < stutter_prob:
            carrier[i:i+grain] = carrier[max(0, i-grain):i]
            
    audio = np.tanh(carrier * (2.0 + chaos)) # Saturation
    return (audio * 32767).astype(np.int16), sr

# -------------------- MAIN PROCESSING LOOP --------------------

def process_video(args):
    tmp = Path(tempfile.mkdtemp())
    print(f">> INITIALIZING V12 ENGINE | MODE: PERSONALIZED ENTROPY")

    def extract(path, prefix):
        print(f">> Extracting {path}...")
        subprocess.run([
            "ffmpeg", "-y", "-err_detect", "ignore_err", "-i", path,
            "-vf", f"scale=480:360,fps={args.fps}", str(tmp / f"{prefix}_%05d.png")
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    extract(args.v1, "v1")
    extract(args.v2, "v2")

    v1_f = sorted(list(tmp.glob("v1_*.png")))
    v2_f = sorted(list(tmp.glob("v2_*.png")))
    
    if not v1_f or not v2_f:
        print("!! FATAL: Could not extract frames. Check file paths.")
        return

    # Random Injection Logic
    n1, n2 = len(v1_f), len(v2_f)
    start_idx = random.randint(0, max(0, n1 - n2))
    print(f">> INJECTING V2 (FULL CLIP) AT FRAME {start_idx}")

    canvas = cv2.imread(str(v1_f[0]))
    prev_source = canvas.copy()
    out_dir = tmp / "render"
    out_dir.mkdir()

    for i in range(1, n1):
        curr_source = cv2.imread(str(v1_f[i]))
        
        # Calculate Optical Flow for pixel dragging
        p_g = cv2.cvtColor(prev_source, cv2.COLOR_BGR2GRAY)
        c_g = cv2.cvtColor(curr_source, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(p_g, c_g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        
        # Datamosh Smear
        if random.random() > (0.05 / args.chaos):
            h, w = canvas.shape[:2]
            flow_map = np.copy(flow)
            flow_map[:,:,0] += np.arange(w)
            flow_map[:,:,1] += np.arange(h)[:,np.newaxis]
            # 
            # The 'drag' multiplies the motion vectors to exaggerate the melt
            canvas = cv2.remap(canvas, (flow_map * args.drag).astype(np.float32), 
                             None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        else:
            # Refresh Logic (I-Frame replacement)
            if start_idx <= i < (start_idx + n2):
                canvas = cv2.imread(str(v2_f[i - start_idx]))
            else:
                canvas = curr_source.copy()

        # Apply Visual FX
        canvas = apply_chroma_bleed(canvas, args.chroma)
        canvas = apply_luma_tear(canvas, args.tear)
        
        # Blend for 'ghosting'
        final = cv2.addWeighted(canvas, 0.9, curr_source, 0.1, 0)
        cv2.imwrite(str(out_dir / f"f_{i:05d}.png"), final)
        prev_source = curr_source
        if i % 50 == 0: print(f" Progress: {int(i/n1*100)}%")

    # Audio Mux
    duration = n1 / args.fps
    audio_data, sr = synth_experimental_audio(duration, args.chaos, args.stutter)
    audio_path = tmp / "s.wav"
    with wave.open(str(audio_path), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(audio_data.tobytes())

    print(">> FINAL MUXING...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(out_dir / "f_%05d.png"),
        "-i", str(audio_path), "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
        "-crf", str(args.crf), "-preset", "ultrafast", "-shortest", args.out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    shutil.rmtree(tmp)
    print(f">> SUCCESS: {args.out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--drag", type=float, default=1.0, help="Smear intensity")
    parser.add_argument("--chaos", type=float, default=2.5, help="Global chaos")
    parser.add_argument("--chroma", type=float, default=1.0, help="Color bleeding")
    parser.add_argument("--tear", type=float, default=0.1, help="Digital tearing")
    parser.add_argument("--stutter", type=float, default=0.1, help="Audio stutter")
    parser.add_argument("--crf", type=int, default=24)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--out", default="output_entropy.mp4")
    args = parser.parse_args()
    process_video(args)
