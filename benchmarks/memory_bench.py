"""Memory system benchmark harness.

Measures: write latency, read latency, recall precision@k,
contradiction detection F1, and memory usage.

Outputs METRIC lines for autoresearch consumption.

Usage:
    python -m benchmarks.memory_bench --backend json-baseline
    python -m benchmarks.memory_bench --backend pageindex-local
    python -m benchmarks.memory_bench --backend grafeo
"""

import argparse
import json
import sys
import time
from pathlib import Path

from benchmarks.synthetic_data import generate_all

# Registry of available backends
BACKEND_REGISTRY: dict[str, type] = {}


def register_backends():
    """Register all available backends."""
    from benchmarks.backends.json_baseline import JsonBaselineBackend
    BACKEND_REGISTRY["json-baseline"] = JsonBaselineBackend

    from benchmarks.backends.pageindex_local import PageIndexLocalBackend
    BACKEND_REGISTRY["pageindex-local"] = PageIndexLocalBackend

    # Hybrid: PageIndex + local embeddings
    try:
        from benchmarks.backends.hybrid_embeddings import HybridEmbeddingsBackend
        BACKEND_REGISTRY["hybrid-embeddings"] = HybridEmbeddingsBackend
    except ImportError:
        pass

    # Grafeo — requires Docker or pip install
    try:
        from benchmarks.backends.grafeo_backend import GrafeoBackend
        BACKEND_REGISTRY["grafeo"] = GrafeoBackend
    except ImportError:
        pass

    # HelixDB — requires CLI install
    try:
        from benchmarks.backends.helix_backend import HelixBackend
        BACKEND_REGISTRY["helix"] = HelixBackend
    except ImportError:
        pass


def precision_at_k(retrieved_dates: list[str], expected_dates: list[str], k: int = 5) -> float:
    """Compute precision@k: fraction of top-k retrieved that are relevant."""
    if not expected_dates:
        return 1.0 if not retrieved_dates else 0.0
    top_k = retrieved_dates[:k]
    if not top_k:
        return 0.0
    relevant = sum(1 for d in top_k if d in expected_dates)
    return relevant / len(top_k)


def f1_score(tp: int, fp: int, fn: int) -> float:
    """Compute F1 from raw counts."""
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def run_benchmark(backend_name: str, iterations: int = 3) -> dict:
    """Run the full benchmark suite on a backend.

    Runs `iterations` times and reports the median to reduce noise.
    """
    register_backends()

    if backend_name not in BACKEND_REGISTRY:
        print(f"ERROR: Unknown backend '{backend_name}'. Available: {list(BACKEND_REGISTRY.keys())}")
        sys.exit(1)

    backend_cls = BACKEND_REGISTRY[backend_name]
    data = generate_all()

    all_results = []

    for iteration in range(iterations):
        backend = backend_cls()
        backend.setup()

        results = {}

        # --- 1. Write latency: store all entries + beliefs ---
        start = time.perf_counter()
        for entry in data["entries"]:
            backend.store_entry(entry)
        for belief in data["beliefs"]:
            backend.store_belief(belief)
        write_elapsed = time.perf_counter() - start
        write_count = len(data["entries"]) + len(data["beliefs"])
        results["write_latency_ms"] = (write_elapsed / write_count) * 1000

        # --- 2. Read latency + Recall precision@5 ---
        precisions = []
        read_times = []

        for qp in data["query_pairs"]:
            start = time.perf_counter()
            recalled = backend.recall(qp["query"], top_k=5)
            read_elapsed = time.perf_counter() - start
            read_times.append(read_elapsed)

            retrieved_dates = [r["date"] for r in recalled]
            p_at_5 = precision_at_k(retrieved_dates, qp["expected_dates"], k=5)
            precisions.append(p_at_5)

        results["read_latency_ms"] = (
            sum(read_times) / max(len(read_times), 1)
        ) * 1000
        results["recall_precision_at_5"] = (
            sum(precisions) / max(len(precisions), 1)
        )

        # --- 3. Contradiction detection F1 ---
        tp, fp, fn = 0, 0, 0
        for cp in data["contradiction_pairs"]:
            result = backend.check_contradiction(cp["belief_a"], cp["belief_b"])
            predicted_conflict = result.get("has_conflict", False)
            actual_conflict = cp["expected_conflict"]

            if predicted_conflict and actual_conflict:
                tp += 1
            elif predicted_conflict and not actual_conflict:
                fp += 1
            elif not predicted_conflict and actual_conflict:
                fn += 1

        results["contradiction_f1"] = f1_score(tp, fp, fn)

        # --- 4. Memory usage ---
        results["memory_usage_mb"] = backend.get_memory_usage_mb()

        # --- 5. Composite score ---
        # Normalize latencies: cap at 100ms, lower is better → 1 - (val/100)
        norm_write = min(results["write_latency_ms"] / 100.0, 1.0)
        norm_read = min(results["read_latency_ms"] / 100.0, 1.0)

        results["composite_score"] = round(
            100 * (
                0.40 * results["recall_precision_at_5"]
                + 0.20 * (1.0 - norm_write)
                + 0.20 * (1.0 - norm_read)
                + 0.20 * results["contradiction_f1"]
            ),
            2,
        )

        backend.teardown()
        all_results.append(results)

    # Take median of each metric across iterations
    median_results = {}
    for key in all_results[0]:
        values = sorted(r[key] for r in all_results)
        mid = len(values) // 2
        median_results[key] = values[mid]

    return median_results


def main():
    parser = argparse.ArgumentParser(description="Memory system benchmark")
    parser.add_argument(
        "--backend",
        default="json-baseline",
        help="Backend to benchmark (default: json-baseline)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations for median (default: 3)",
    )
    args = parser.parse_args()

    print(f"=== Memory Benchmark: {args.backend} ({args.iterations} iterations) ===\n")

    results = run_benchmark(args.backend, args.iterations)

    # Output METRIC lines for autoresearch
    for key, value in results.items():
        formatted = f"{value:.4f}" if isinstance(value, float) else str(value)
        print(f"METRIC {key}={formatted}")

    # Human-readable summary
    print(f"\n--- Summary ---")
    print(f"Backend: {args.backend}")
    print(f"Composite Score: {results['composite_score']:.2f}/100")
    print(f"Recall P@5: {results['recall_precision_at_5']:.4f}")
    print(f"Write Latency: {results['write_latency_ms']:.2f}ms/op")
    print(f"Read Latency: {results['read_latency_ms']:.2f}ms/op")
    print(f"Contradiction F1: {results['contradiction_f1']:.4f}")
    print(f"Memory: {results['memory_usage_mb']:.2f}MB")


if __name__ == "__main__":
    main()
