#!/usr/bin/env python3
"""
Embedding verification script.

Run this on each worker machine to confirm embeddings match Tamor's output
byte-for-byte. If they don't match, cosine similarity across the library
will be broken.

Usage:
    python3 verify_embeddings.py
    python3 verify_embeddings.py --reference /mnt/library/harvest/config/reference_embeddings.json
"""

import argparse
import base64
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from lib.embedder import embed_one, get_model


# Built-in reference embeddings generated on the Tamor machine.
# If these don't match, the model version or preprocessing differs.
REFERENCE_STRINGS = [
    "The quick brown fox jumps over the lazy dog.",
    "Torah observance in the early church period.",
    "Shalom aleichem, welcome to today s teaching.",
]


def load_reference(path=None):
    """Load reference embeddings from file."""
    if path and os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def verify(reference_path=None):
    """
    Verify embeddings match reference values.

    Returns True if all embeddings match byte-for-byte.
    """
    print(f"Loading model...")
    model = get_model()
    print(f"Model: {model.__class__.__name__}")
    print(f"Model path: {model._model_card_vars.get('name', 'unknown')}")
    print()

    reference = load_reference(reference_path)

    all_match = True
    for test_string in REFERENCE_STRINGS:
        local_b64 = embed_one(test_string)
        local_bytes = base64.b64decode(local_b64)
        local_vec = np.frombuffer(local_bytes, dtype=np.float32)

        print(f"Text: '{test_string[:50]}...'")
        print(f"  Dim: {len(local_vec)}")
        print(f"  First 5: {local_vec[:5]}")
        print(f"  Norm: {np.linalg.norm(local_vec):.6f}")

        if reference and test_string in reference:
            ref_bytes = base64.b64decode(reference[test_string])
            ref_vec = np.frombuffer(ref_bytes, dtype=np.float32)

            bytes_match = (local_bytes == ref_bytes)
            cosine_sim = np.dot(local_vec, ref_vec) / (
                np.linalg.norm(local_vec) * np.linalg.norm(ref_vec)
            )

            if bytes_match:
                print(f"  MATCH: byte-identical to reference")
            else:
                print(f"  MISMATCH: bytes differ from reference!")
                print(f"  Cosine similarity: {cosine_sim:.8f}")
                if cosine_sim > 0.9999:
                    print(f"  (Very close — likely floating point rounding)")
                else:
                    print(f"  WARNING: Significant divergence!")
                all_match = False
        else:
            print(f"  (no reference to compare — save this output as reference)")

        print()

    if reference:
        if all_match:
            print("ALL EMBEDDINGS MATCH REFERENCE — safe to process")
        else:
            print("EMBEDDING MISMATCH — DO NOT process until resolved!")
            print("Check: model version, torch version, numpy version")
    else:
        print("No reference file found.")
        print("Run this on the Tamor machine first to generate reference,")
        print("then copy to /mnt/library/harvest/config/reference_embeddings.json")

    return all_match


def generate_reference(output_path):
    """Generate reference embeddings and save to file."""
    print("Generating reference embeddings...")
    refs = {}
    for s in REFERENCE_STRINGS:
        refs[s] = embed_one(s)
        print(f"  '{s[:40]}...' — done")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(refs, f, indent=2)

    print(f"\nSaved to {output_path}")
    print("Copy this file to all worker machines for verification.")


def main():
    parser = argparse.ArgumentParser(description="Verify embedding consistency")
    parser.add_argument(
        "--reference",
        default="/mnt/library/harvest/config/reference_embeddings.json",
        help="Path to reference embeddings JSON",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate reference embeddings (run on Tamor machine)",
    )
    args = parser.parse_args()

    if args.generate:
        generate_reference(args.reference)
    else:
        verify(args.reference)


if __name__ == "__main__":
    main()
