#!/bin/bash
# LogiScan Pipeline Benchmarks
set -e

# Add project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

echo "==========================================="
echo "  Running LogiScan Pipeline Benchmarks     "
echo "==========================================="

./venv/bin/python backend/tests/benchmarks/run_benchmarks.py
./venv/bin/python backend/tests/benchmarks/test_offsets.py

echo "==========================================="
echo "  Benchmark Suite Complete                 "
echo "==========================================="
