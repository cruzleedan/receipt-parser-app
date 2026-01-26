#!/usr/bin/env python3
"""
Test client for Receipt Parser API.

Usage:
    python test_api.py receipts/sample.jpg          # Test single receipt
    python test_api.py receipts/                     # Test all receipts in directory
    python test_api.py receipts/ --benchmark         # Run performance benchmark
"""

import sys
import json
import requests
from pathlib import Path
import time
from typing import List
import argparse


API_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{API_URL}/health")

    if response.status_code == 200:
        data = response.json()
        print(f"  Status: {data['status']}")
        print(f"  OCR: {data['services']['ocr']['status']}")
        print(f"  LLM: {data['services']['llm']['status']}")
        print("  ✓ Health check passed\n")
        return True
    else:
        print(f"  ✗ Health check failed: {response.status_code}\n")
        return False


def test_service_info():
    """Test service info endpoint."""
    print("Testing service info endpoint...")
    response = requests.get(f"{API_URL}/")

    if response.status_code == 200:
        data = response.json()
        print(f"  Service: {data['name']}")
        print(f"  Version: {data['version']}")
        print(f"  Architecture: {data['architecture']}")
        print("  ✓ Service info retrieved\n")
        return True
    else:
        print(f"  ✗ Service info failed: {response.status_code}\n")
        return False


def parse_receipt(image_path: Path) -> dict:
    """
    Parse a single receipt.

    Args:
        image_path: Path to receipt image

    Returns:
        Response data dictionary
    """
    print(f"Parsing receipt: {image_path.name}")

    start_time = time.time()

    with open(image_path, "rb") as f:
        files = {"file": (image_path.name, f, "image/jpeg")}
        response = requests.post(f"{API_URL}/parse", files=files)

    elapsed_ms = (time.time() - start_time) * 1000

    if response.status_code == 200:
        data = response.json()
        metadata = data.get("processing_metadata", {})

        print(f"  ✓ Parsing succeeded")
        print(f"  Merchant: {data.get('merchant_name', 'N/A')}")
        print(f"  Date: {data.get('date', 'N/A')}")
        print(f"  Total: ${data.get('total', 0.0):.2f}")
        print(f"  Items: {len(data.get('items', []))}")
        print(f"  OCR Time: {metadata.get('ocr_time_ms', 0):.0f}ms")
        print(f"  LLM Time: {metadata.get('llm_time_ms', 0):.0f}ms")
        print(f"  Total Time: {elapsed_ms:.0f}ms (including network)")
        print(f"  OCR Confidence: {metadata.get('ocr_confidence', 0):.2f}")
        print()

        return {"success": True, "data": data, "time_ms": elapsed_ms}

    else:
        print(f"  ✗ Parsing failed: {response.status_code}")
        try:
            error_data = response.json()
            print(f"  Error: {error_data.get('error', 'Unknown error')}")
            print(f"  Details: {error_data.get('details', 'N/A')}")
        except:
            print(f"  Response: {response.text}")
        print()

        return {"success": False, "error": response.text, "time_ms": elapsed_ms}


def parse_batch(image_paths: List[Path]) -> dict:
    """
    Parse multiple receipts in batch.

    Args:
        image_paths: List of paths to receipt images

    Returns:
        Batch response data
    """
    print(f"Parsing batch of {len(image_paths)} receipts...")

    start_time = time.time()

    files = [
        ("files", (path.name, open(path, "rb"), "image/jpeg"))
        for path in image_paths
    ]

    response = requests.post(f"{API_URL}/parse-batch", files=files)

    # Close file handles
    for _, (_, f, _) in files:
        f.close()

    elapsed_ms = (time.time() - start_time) * 1000

    if response.status_code == 200:
        data = response.json()

        print(f"  ✓ Batch parsing completed")
        print(f"  Total: {data.get('total', 0)}")
        print(f"  Successful: {data.get('successful', 0)}")
        print(f"  Failed: {data.get('failed', 0)}")
        print(f"  Total Time: {elapsed_ms:.0f}ms (including network)")
        print(f"  Avg Time: {elapsed_ms / len(image_paths):.0f}ms per receipt")
        print()

        return {"success": True, "data": data, "time_ms": elapsed_ms}

    else:
        print(f"  ✗ Batch parsing failed: {response.status_code}")
        print(f"  Response: {response.text}")
        print()

        return {"success": False, "error": response.text, "time_ms": elapsed_ms}


def benchmark(image_paths: List[Path], iterations: int = 3):
    """
    Run performance benchmark.

    Args:
        image_paths: List of receipt images
        iterations: Number of iterations per image
    """
    print(f"Running benchmark ({iterations} iterations per image)...\n")

    results = []

    for image_path in image_paths:
        image_results = []

        for i in range(iterations):
            print(f"  [{i+1}/{iterations}] {image_path.name}")
            result = parse_receipt(image_path)
            if result["success"]:
                image_results.append(result["time_ms"])

        if image_results:
            avg = sum(image_results) / len(image_results)
            min_time = min(image_results)
            max_time = max(image_results)

            results.append(
                {
                    "file": image_path.name,
                    "avg_ms": avg,
                    "min_ms": min_time,
                    "max_ms": max_time,
                }
            )

    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)

    for result in results:
        print(f"{result['file']}:")
        print(f"  Average: {result['avg_ms']:.0f}ms")
        print(f"  Min: {result['min_ms']:.0f}ms")
        print(f"  Max: {result['max_ms']:.0f}ms")
        print()

    if results:
        overall_avg = sum(r["avg_ms"] for r in results) / len(results)
        print(f"Overall Average: {overall_avg:.0f}ms per receipt")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Test Receipt Parser API")
    parser.add_argument(
        "path", nargs="?", help="Path to receipt image or directory"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run performance benchmark",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of benchmark iterations (default: 3)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use batch processing endpoint",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("Receipt Parser API - Test Client")
    print("=" * 60 + "\n")

    # Test health first
    if not test_health():
        print("Error: API is not healthy. Please start the service first.")
        print("Run: ./quickstart.sh")
        sys.exit(1)

    # Test service info
    test_service_info()

    # If no path provided, show usage
    if not args.path:
        print("Usage:")
        print("  python test_api.py receipts/sample.jpg")
        print("  python test_api.py receipts/")
        print("  python test_api.py receipts/ --benchmark")
        print("  python test_api.py receipts/ --batch")
        sys.exit(0)

    # Get image paths
    path = Path(args.path)

    if path.is_file():
        image_paths = [path]
    elif path.is_dir():
        image_paths = sorted(
            [
                p
                for p in path.iterdir()
                if p.suffix.lower() in [".jpg", ".jpeg", ".png"]
            ]
        )
    else:
        print(f"Error: Path not found: {path}")
        sys.exit(1)

    if not image_paths:
        print(f"Error: No image files found in {path}")
        sys.exit(1)

    # Run benchmark if requested
    if args.benchmark:
        benchmark(image_paths, iterations=args.iterations)

    # Run batch processing if requested
    elif args.batch and len(image_paths) > 1:
        parse_batch(image_paths)

    # Parse individual receipts
    else:
        for image_path in image_paths:
            parse_receipt(image_path)

    print("Done!\n")


if __name__ == "__main__":
    main()
