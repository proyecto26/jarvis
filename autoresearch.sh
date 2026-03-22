#!/usr/bin/env bash
# autoresearch.sh — benchmark runner for memory system optimization
# Outputs METRIC lines consumed by the autoresearch loop
set -euo pipefail

BACKEND="${1:-json-baseline}"
ITERATIONS="${2:-3}"

echo "Running memory benchmark: backend=$BACKEND iterations=$ITERATIONS"

# Run the benchmark from project root
cd "$(dirname "$0")"
python -m benchmarks.memory_bench --backend "$BACKEND" --iterations "$ITERATIONS"
