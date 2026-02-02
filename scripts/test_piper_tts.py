#!/usr/bin/env python3
"""
Piper TTS validation script.

Tests Piper text-to-speech on local hardware before integrating into Tamor.
Run from tamor-core with: python scripts/test_piper_tts.py
"""

import subprocess
import sys
import time
from pathlib import Path

# Test configuration
VOICE_MODEL = "en_US-lessac-medium"
VOICE_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

MODELS_DIR = Path("/mnt/library/piper_voices")
OUTPUT_DIR = Path("/tmp/piper_test")

SAMPLE_TEXT = """
Welcome to Tamor's integrated reader. This is a test of the Piper text-to-speech system.

The reader will allow you to listen to documents from your library while doing other tasks.
Whether you're commuting, exercising, or just resting your eyes, your research continues.

This sample includes multiple sentences to test natural pacing and pronunciation.
Let's also test some numbers: Chapter 3, verse 16. And a date: January 15th, 2026.
"""

def run(cmd, check=True):
    """Run a shell command."""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return None
    return result

def main():
    print("=" * 60)
    print("Piper TTS Validation Test")
    print("=" * 60)

    # Step 1: Check if piper-tts is installed
    print("\n[1/5] Checking piper-tts installation...")
    result = run("pip show piper-tts", check=False)
    if result and result.returncode == 0:
        print("  ✓ piper-tts already installed")
    else:
        print("  Installing piper-tts...")
        result = run("pip install piper-tts")
        if not result:
            print("  ✗ Failed to install piper-tts")
            return 1
        print("  ✓ piper-tts installed")

    # Step 2: Create directories
    print("\n[2/5] Setting up directories...")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Models dir: {MODELS_DIR}")
    print(f"  ✓ Output dir: {OUTPUT_DIR}")

    # Step 3: Download voice model if needed
    print("\n[3/5] Checking voice model...")
    model_path = MODELS_DIR / f"{VOICE_MODEL}.onnx"
    config_path = MODELS_DIR / f"{VOICE_MODEL}.onnx.json"

    if model_path.exists() and config_path.exists():
        print(f"  ✓ Voice model already downloaded: {model_path.name}")
    else:
        print(f"  Downloading {VOICE_MODEL} (~60MB)...")

        if not model_path.exists():
            result = run(f'curl -L -o "{model_path}" "{VOICE_URL}"')
            if not result:
                print("  ✗ Failed to download model")
                return 1

        if not config_path.exists():
            result = run(f'curl -L -o "{config_path}" "{CONFIG_URL}"')
            if not result:
                print("  ✗ Failed to download config")
                return 1

        print(f"  ✓ Voice model downloaded: {model_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Step 4: Generate test audio
    print("\n[4/5] Generating test audio...")
    output_file = OUTPUT_DIR / "piper_test.wav"

    # Write sample text to temp file
    text_file = OUTPUT_DIR / "sample.txt"
    text_file.write_text(SAMPLE_TEXT.strip())

    # Time the generation
    start_time = time.time()

    cmd = f'cat "{text_file}" | piper --model "{model_path}" --output_file "{output_file}"'
    result = run(cmd)

    generation_time = time.time() - start_time

    if not result or not output_file.exists():
        print("  ✗ Failed to generate audio")
        return 1

    # Get audio duration (rough estimate: WAV at 22050 Hz, 16-bit mono)
    file_size = output_file.stat().st_size
    # WAV header is 44 bytes, then 2 bytes per sample at 22050 Hz
    audio_duration = (file_size - 44) / (22050 * 2)

    print(f"  ✓ Audio generated: {output_file}")
    print(f"  ✓ File size: {file_size / 1024:.1f} KB")
    print(f"  ✓ Audio duration: ~{audio_duration:.1f} seconds")
    print(f"  ✓ Generation time: {generation_time:.2f} seconds")
    print(f"  ✓ Real-time factor: {audio_duration / generation_time:.1f}x")

    # Step 5: Summary
    print("\n[5/5] Summary")
    print("=" * 60)

    rtf = audio_duration / generation_time
    if rtf >= 10:
        rating = "Excellent"
    elif rtf >= 5:
        rating = "Good"
    elif rtf >= 1:
        rating = "Acceptable"
    else:
        rating = "Too slow for real-time"

    print(f"  Voice model: {VOICE_MODEL}")
    print(f"  Text length: {len(SAMPLE_TEXT)} characters")
    print(f"  Audio duration: {audio_duration:.1f}s")
    print(f"  Generation time: {generation_time:.2f}s")
    print(f"  Real-time factor: {rtf:.1f}x ({rating})")
    print(f"\n  Output file: {output_file}")
    print(f"  Play with: aplay {output_file}")
    print("=" * 60)

    if rtf < 1:
        print("\n⚠️  Warning: Generation is slower than real-time.")
        print("   Consider using a smaller model or checking CPU load.")
        return 1

    print("\n✓ Piper TTS is ready for Tamor integration!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
