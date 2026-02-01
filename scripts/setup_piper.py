#!/usr/bin/env python3
"""
Piper TTS Setup Script

Phase 5.5: Integrated Reader.

Installs Piper TTS and downloads voice models for the reader feature.
Run from tamor-core with: python scripts/setup_piper.py

Usage:
    python scripts/setup_piper.py                    # Install default voice
    python scripts/setup_piper.py --list-voices      # Show available voices
    python scripts/setup_piper.py --voices en_US-amy-medium,en_GB-alba-medium
    python scripts/setup_piper.py --validate-only    # Test existing installation
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration
VOICES_DIR = Path("/mnt/library/piper_voices")
HUGGINGFACE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Available voices with metadata
AVAILABLE_VOICES: Dict[str, Dict] = {
    # American English
    "en_US-lessac-medium": {
        "description": "Neutral American English (default)",
        "gender": "neutral",
        "quality": "medium",
        "language": "en_US",
        "path": "en/en_US/lessac/medium",
    },
    "en_US-lessac-high": {
        "description": "Neutral American English (high quality)",
        "gender": "neutral",
        "quality": "high",
        "language": "en_US",
        "path": "en/en_US/lessac/high",
    },
    "en_US-amy-medium": {
        "description": "Female American English",
        "gender": "female",
        "quality": "medium",
        "language": "en_US",
        "path": "en/en_US/amy/medium",
    },
    "en_US-amy-low": {
        "description": "Female American English (smaller/faster)",
        "gender": "female",
        "quality": "low",
        "language": "en_US",
        "path": "en/en_US/amy/low",
    },
    "en_US-ryan-medium": {
        "description": "Male American English",
        "gender": "male",
        "quality": "medium",
        "language": "en_US",
        "path": "en/en_US/ryan/medium",
    },
    "en_US-ryan-high": {
        "description": "Male American English (high quality)",
        "gender": "male",
        "quality": "high",
        "language": "en_US",
        "path": "en/en_US/ryan/high",
    },
    "en_US-joe-medium": {
        "description": "Male American English (alternative)",
        "gender": "male",
        "quality": "medium",
        "language": "en_US",
        "path": "en/en_US/joe/medium",
    },
    # British English
    "en_GB-alba-medium": {
        "description": "Female British English",
        "gender": "female",
        "quality": "medium",
        "language": "en_GB",
        "path": "en/en_GB/alba/medium",
    },
    "en_GB-aru-medium": {
        "description": "Male British English",
        "gender": "male",
        "quality": "medium",
        "language": "en_GB",
        "path": "en/en_GB/aru/medium",
    },
    "en_GB-cori-medium": {
        "description": "Female British English (alternative)",
        "gender": "female",
        "quality": "medium",
        "language": "en_GB",
        "path": "en/en_GB/cori/medium",
    },
    # Other languages (for future expansion)
    "de_DE-thorsten-medium": {
        "description": "German male voice",
        "gender": "male",
        "quality": "medium",
        "language": "de_DE",
        "path": "de/de_DE/thorsten/medium",
    },
    "es_ES-davefx-medium": {
        "description": "Spanish male voice",
        "gender": "male",
        "quality": "medium",
        "language": "es_ES",
        "path": "es/es_ES/davefx/medium",
    },
    "fr_FR-siwis-medium": {
        "description": "French female voice",
        "gender": "female",
        "quality": "medium",
        "language": "fr_FR",
        "path": "fr/fr_FR/siwis/medium",
    },
}

DEFAULT_VOICE = "en_US-lessac-medium"


def print_header(text: str) -> None:
    """Print a section header."""
    print()
    print("=" * 60)
    print(text)
    print("=" * 60)


def print_step(step: int, total: int, text: str) -> None:
    """Print a step indicator."""
    print(f"\n[{step}/{total}] {text}")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"  ✓ {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"  ✗ {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"  • {text}")


def run_command(cmd: str, check: bool = True, capture: bool = True) -> Optional[subprocess.CompletedProcess]:
    """Run a shell command."""
    print(f"  $ {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if check and result.returncode != 0:
            if capture:
                print_error(result.stderr or "Command failed")
            return None
        return result
    except subprocess.TimeoutExpired:
        print_error("Command timed out")
        return None
    except Exception as e:
        print_error(str(e))
        return None


def check_piper_installed() -> bool:
    """Check if piper-tts is installed."""
    result = run_command("pip show piper-tts", check=False)
    return result is not None and result.returncode == 0


def install_piper() -> bool:
    """Install piper-tts via pip."""
    print_step(1, 4, "Installing piper-tts...")

    if check_piper_installed():
        print_success("piper-tts already installed")
        return True

    result = run_command("pip install piper-tts")
    if result:
        print_success("piper-tts installed successfully")
        return True
    else:
        print_error("Failed to install piper-tts")
        return False


def ensure_voices_directory() -> bool:
    """Create voices directory if it doesn't exist."""
    try:
        VOICES_DIR.mkdir(parents=True, exist_ok=True)
        print_success(f"Voices directory: {VOICES_DIR}")
        return True
    except Exception as e:
        print_error(f"Failed to create voices directory: {e}")
        return False


def get_voice_urls(voice_name: str) -> Tuple[str, str]:
    """Get download URLs for a voice model."""
    if voice_name not in AVAILABLE_VOICES:
        raise ValueError(f"Unknown voice: {voice_name}")

    voice_info = AVAILABLE_VOICES[voice_name]
    path = voice_info["path"]

    model_url = f"{HUGGINGFACE_BASE}/{path}/{voice_name}.onnx"
    config_url = f"{HUGGINGFACE_BASE}/{path}/{voice_name}.onnx.json"

    return model_url, config_url


def is_voice_installed(voice_name: str) -> bool:
    """Check if a voice model is already downloaded."""
    model_path = VOICES_DIR / f"{voice_name}.onnx"
    config_path = VOICES_DIR / f"{voice_name}.onnx.json"
    return model_path.exists() and config_path.exists()


def download_voice(voice_name: str) -> bool:
    """Download a voice model from HuggingFace."""
    if voice_name not in AVAILABLE_VOICES:
        print_error(f"Unknown voice: {voice_name}")
        return False

    if is_voice_installed(voice_name):
        print_success(f"{voice_name} already installed")
        return True

    voice_info = AVAILABLE_VOICES[voice_name]
    print_info(f"Downloading {voice_name} ({voice_info['description']})...")

    try:
        model_url, config_url = get_voice_urls(voice_name)
        model_path = VOICES_DIR / f"{voice_name}.onnx"
        config_path = VOICES_DIR / f"{voice_name}.onnx.json"

        # Download model file (~60MB)
        result = run_command(f'curl -L --progress-bar -o "{model_path}" "{model_url}"')
        if not result or not model_path.exists():
            print_error("Failed to download model file")
            return False

        # Download config file
        result = run_command(f'curl -L -s -o "{config_path}" "{config_url}"')
        if not result or not config_path.exists():
            print_error("Failed to download config file")
            # Clean up partial download
            if model_path.exists():
                model_path.unlink()
            return False

        size_mb = model_path.stat().st_size / (1024 * 1024)
        print_success(f"{voice_name} downloaded ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        print_error(f"Download failed: {e}")
        return False


def download_voices(voice_names: List[str]) -> Tuple[int, int]:
    """Download multiple voice models. Returns (success_count, fail_count)."""
    success = 0
    failed = 0

    for voice in voice_names:
        if download_voice(voice):
            success += 1
        else:
            failed += 1

    return success, failed


def validate_installation(voice_name: str = None) -> bool:
    """Validate Piper installation by running test synthesis."""
    voice_name = voice_name or DEFAULT_VOICE

    print_step(4, 4, "Validating installation...")

    # Check piper command
    result = run_command("piper --help", check=False)
    if not result or result.returncode != 0:
        print_error("piper command not found or not working")
        return False
    print_success("piper command available")

    # Check voice model
    if not is_voice_installed(voice_name):
        print_error(f"Voice model not found: {voice_name}")
        return False
    print_success(f"Voice model found: {voice_name}")

    # Test synthesis
    model_path = VOICES_DIR / f"{voice_name}.onnx"
    test_text = "Hello, this is a test of the Piper text to speech system."

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        cmd = f'echo "{test_text}" | piper --model "{model_path}" --output_file "{tmp_path}"'
        result = run_command(cmd)

        if not result:
            print_error("Synthesis test failed")
            return False

        output_path = Path(tmp_path)
        if not output_path.exists() or output_path.stat().st_size < 1000:
            print_error("Synthesis produced invalid output")
            return False

        size_kb = output_path.stat().st_size / 1024
        print_success(f"Test synthesis successful ({size_kb:.1f} KB audio)")

        # Estimate duration
        # WAV: 22050 Hz, 16-bit mono = 44100 bytes/second
        duration = (output_path.stat().st_size - 44) / 44100
        print_info(f"Audio duration: ~{duration:.1f} seconds")

        return True

    finally:
        # Clean up
        Path(tmp_path).unlink(missing_ok=True)


def list_voices() -> None:
    """Print available voices with descriptions."""
    print_header("Available Piper Voices")

    # Group by language
    by_language: Dict[str, List[str]] = {}
    for name, info in AVAILABLE_VOICES.items():
        lang = info["language"]
        if lang not in by_language:
            by_language[lang] = []
        by_language[lang].append(name)

    for lang in sorted(by_language.keys()):
        print(f"\n{lang}:")
        for name in sorted(by_language[lang]):
            info = AVAILABLE_VOICES[name]
            installed = "✓" if is_voice_installed(name) else " "
            default = " (default)" if name == DEFAULT_VOICE else ""
            print(f"  [{installed}] {name}{default}")
            print(f"      {info['description']} [{info['gender']}, {info['quality']} quality]")

    print()
    installed_count = sum(1 for v in AVAILABLE_VOICES if is_voice_installed(v))
    print(f"Installed: {installed_count}/{len(AVAILABLE_VOICES)}")
    print(f"Voices directory: {VOICES_DIR}")


def list_installed() -> None:
    """List currently installed voices."""
    print_header("Installed Voices")

    if not VOICES_DIR.exists():
        print("No voices directory found.")
        return

    installed = []
    for name in AVAILABLE_VOICES:
        if is_voice_installed(name):
            installed.append(name)

    if not installed:
        print("No voices installed.")
        return

    for name in installed:
        info = AVAILABLE_VOICES[name]
        model_path = VOICES_DIR / f"{name}.onnx"
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"  {name} ({size_mb:.1f} MB)")
        print(f"    {info['description']}")

    print(f"\nTotal: {len(installed)} voice(s)")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up Piper TTS for Tamor's integrated reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              Install default voice
  %(prog)s --voices en_US-amy-medium    Install specific voice
  %(prog)s --voices all                 Install all available voices
  %(prog)s --list-voices                Show available voices
  %(prog)s --validate-only              Test existing installation
        """,
    )

    parser.add_argument(
        "--voices",
        type=str,
        default=DEFAULT_VOICE,
        help=f"Comma-separated list of voices to install (default: {DEFAULT_VOICE})",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Show available voices with descriptions",
    )
    parser.add_argument(
        "--list-installed",
        action="store_true",
        help="Show installed voices",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing installation",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation after installation",
    )

    args = parser.parse_args()

    # List voices
    if args.list_voices:
        list_voices()
        return 0

    # List installed
    if args.list_installed:
        list_installed()
        return 0

    # Validate only
    if args.validate_only:
        print_header("Piper TTS Validation")
        if validate_installation():
            print("\n✓ Piper TTS is ready!")
            return 0
        else:
            print("\n✗ Validation failed")
            return 1

    # Full installation
    print_header("Piper TTS Setup")

    # Parse voice list
    if args.voices.lower() == "all":
        voices_to_install = list(AVAILABLE_VOICES.keys())
    else:
        voices_to_install = [v.strip() for v in args.voices.split(",")]

    # Validate voice names
    unknown = [v for v in voices_to_install if v not in AVAILABLE_VOICES]
    if unknown:
        print_error(f"Unknown voice(s): {', '.join(unknown)}")
        print_info("Use --list-voices to see available options")
        return 1

    print(f"Voices to install: {', '.join(voices_to_install)}")

    # Step 1: Install piper-tts
    if not install_piper():
        return 1

    # Step 2: Create voices directory
    print_step(2, 4, "Setting up voices directory...")
    if not ensure_voices_directory():
        return 1

    # Step 3: Download voices
    print_step(3, 4, f"Downloading {len(voices_to_install)} voice(s)...")
    success, failed = download_voices(voices_to_install)

    if failed > 0:
        print_error(f"{failed} voice(s) failed to download")
    if success > 0:
        print_success(f"{success} voice(s) downloaded successfully")

    # Step 4: Validate
    if not args.skip_validation:
        # Use first successfully installed voice for validation
        test_voice = None
        for v in voices_to_install:
            if is_voice_installed(v):
                test_voice = v
                break

        if test_voice and not validate_installation(test_voice):
            print("\n⚠️  Installation completed but validation failed")
            return 1

    # Summary
    print_header("Setup Complete")
    print(f"Voices installed: {success}")
    print(f"Voices directory: {VOICES_DIR}")
    print("\nTo use in Tamor:")
    print("  - Start the API server")
    print("  - Open a document in the reader")
    print("  - Click play to hear TTS")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
