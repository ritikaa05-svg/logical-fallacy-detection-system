import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    precision_recall_fscore_support,
)

sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

REPORT_PATH = Path("backend/tests/benchmarks/latest_report.json")


class PipelineBenchmarkSuite:
    def __init__(self, data_path: str):
        with open(data_path) as f:
            self.data = json.load(f)
        self.orchestrator = PipelineOrchestrator()

    async def run_suite_a(self) -> dict[str, Any]:
        """Suite A: Argument Detection Metrics."""
        print("\n--- Suite A: Argument Detection ---")
        y_true = []
        y_pred = []

        for item in self.data:
            res = await self.orchestrator.analyze(item["text"], skip_cache=True)
            y_true.append(item["expected_is_argument"])
            is_arg_pred = res.fine_labels[0] != "factual_statement" if res.fine_labels else False
            y_pred.append(is_arg_pred)

        p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
        cm = confusion_matrix(y_true, y_pred)

        return {
            "precision": p,
            "recall": r,
            "f1": f1,
            "confusion_matrix": cm.tolist(),
        }

    async def run_suite_b(self) -> dict[str, Any]:
        """Suite B: Evidence Extraction Metrics."""
        print("\n--- Suite B: Evidence Extraction ---")
        iou_scores = []
        exact_matches = []
        offset_errors = 0
        whole_text_fallbacks = 0

        target_samples = [d for d in self.data if d["type"] == "argument" and "expected_quote" in d]

        for item in target_samples:
            await self.orchestrator.analyze(item["text"], skip_cache=True)

            from backend.app.pipeline.orchestrator import _extract_quote_offline

            direct_quote, d_start, d_end = _extract_quote_offline(item["text"], item["expected_fallacy"], [])

            exact_matches.append(direct_quote.strip().lower() == item["expected_quote"].strip().lower())

            def get_iou(s1, s2):
                set1 = set(s1.lower().split())
                set2 = set(s2.lower().split())
                if not set1 or not set2:
                    return 0.0
                return len(set1 & set2) / len(set1 | set2)

            iou_scores.append(get_iou(direct_quote, item["expected_quote"]))

            if direct_quote:
                if direct_quote not in item["text"]:
                    offset_errors += 1
                if item["text"][d_start:d_end] != direct_quote:
                    offset_errors += 1

            if direct_quote == item["text"]:
                whole_text_fallbacks += 1

        return {
            "avg_iou": float(np.mean(iou_scores)) if iou_scores else 0.0,
            "exact_match_rate": float(np.mean(exact_matches)) if exact_matches else 0.0,
            "offset_error_rate": (offset_errors / len(target_samples) if target_samples else 0.0),
            "whole_text_fallback_rate": (whole_text_fallbacks / len(target_samples) if target_samples else 0.0),
        }

    async def run_suite_c(self) -> dict[str, Any]:
        """Suite C: Highlighting Metrics."""
        print("\n--- Suite C: Highlighting ---")
        correct_spans = 0
        total_annotations = 0

        for item in self.data:
            res = await self.orchestrator.analyze(item["text"], skip_cache=True, include_explanations=True)
            for ann in res.annotations:
                total_annotations += 1
                for span in ann.spans:
                    actual = item["text"][span.start : span.end]
                    if span.text.lower() in actual.lower():
                        correct_spans += 1

        return {"span_alignment_accuracy": correct_spans / max(1, total_annotations)}

    async def run_suite_d(self) -> dict[str, Any]:
        """Suite D: Per-class fallacy classification metrics.

        Groups benchmark samples by expected_fallacy (mapping non-argument
        samples to 'non_argument') and computes precision/recall/F1 for each
        class, plus a confusion matrix.
        """
        print("\n--- Suite D: Per-Class Classification ---")
        y_true = []
        y_pred = []

        for item in self.data:
            res = await self.orchestrator.analyze(item["text"], skip_cache=True)

            true_label = "non_argument" if not item["expected_is_argument"] else item["expected_fallacy"]

            if res.fine_labels:
                pred = res.fine_labels[0]
                pred_label = (
                    "non_argument" if not item["expected_is_argument"] and pred == "factual_statement" else pred
                )
            else:
                pred_label = "non_argument"

            y_true.append(true_label)
            y_pred.append(pred_label)

        all_labels = sorted(set(y_true) | set(y_pred))
        p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, labels=all_labels, zero_division=0)
        cm = confusion_matrix(y_true, y_pred, labels=all_labels)

        per_class = {}
        for i, label in enumerate(all_labels):
            per_class[label] = {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f1[i]),
            }

        macro_f1 = float(np.mean([v["f1"] for v in per_class.values()]))
        exact_acc = sum(1 for t, p_ in zip(y_true, y_pred) if t == p_) / len(y_true)

        return {
            "per_class": per_class,
            "confusion_matrix": {
                "labels": all_labels,
                "matrix": cm.tolist(),
            },
            "macro_f1": macro_f1,
            "exact_match_accuracy": exact_acc,
        }

    async def run_all(self, compare: bool = False):
        previous = None
        if compare and REPORT_PATH.exists():
            with open(REPORT_PATH) as f:
                previous = json.load(f)

        start_time = time.perf_counter()

        results = {
            "suite_a": await self.run_suite_a(),
            "suite_b": await self.run_suite_b(),
            "suite_c": await self.run_suite_c(),
            "suite_d": await self.run_suite_d(),
            "metadata": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_latency_ms": (time.perf_counter() - start_time) * 1000,
            },
        }

        print("\n" + "=" * 60)
        print("PERMANENT BENCHMARK REPORT")
        print("=" * 60)
        print(f"Suite A — Argument Detection F1:    {results['suite_a']['f1']:.2%}")
        print(f"Suite B — Evidence Avg IoU:         {results['suite_b']['avg_iou']:.2%}")
        print(f"Suite C — Highlight Alignment:      {results['suite_c']['span_alignment_accuracy']:.2%}")
        print(f"Suite D — Classification Macro F1:  {results['suite_d']['macro_f1']:.2%}")
        print(f"Suite D — Exact Match Accuracy:     {results['suite_d']['exact_match_accuracy']:.2%}")
        print(f"Total Execution Time:               {results['metadata']['total_latency_ms']:.2f}ms")
        print("=" * 60)

        with open(REPORT_PATH, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Report saved to {REPORT_PATH}")

        if previous:
            self._print_comparison(previous, results)

    def _print_comparison(self, previous: dict, current: dict):
        print("\n" + "=" * 60)
        print("BEFORE vs AFTER COMPARISON")
        print("=" * 60)

        metrics = [
            ("suite_a", "f1", "Argument Detection F1"),
            ("suite_b", "avg_iou", "Evidence Avg IoU"),
            ("suite_b", "exact_match_rate", "Exact Match Rate"),
            ("suite_c", "span_alignment_accuracy", "Highlight Alignment"),
            ("suite_d", "macro_f1", "Classification Macro F1"),
            ("suite_d", "exact_match_accuracy", "Exact Match Accuracy"),
        ]

        for suite, key, label in metrics:
            prev_val = previous.get(suite, {}).get(key, "N/A")
            curr_val = current.get(suite, {}).get(key, "N/A")
            if isinstance(prev_val, (int, float)) and isinstance(curr_val, (int, float)):
                delta = curr_val - prev_val
                sign = "+" if delta >= 0 else ""
                print(f"  {label:35}: {prev_val:.2%} -> {curr_val:.2%} ({sign}{delta:.2%})")
            else:
                print(f"  {label:35}: {prev_val} -> {curr_val}")

        prev_pc = previous.get("suite_d", {}).get("per_class", {})
        curr_pc = current.get("suite_d", {}).get("per_class", {})
        if prev_pc and curr_pc:
            print("\n  Per-Class F1 Changes:")
            all_cls = sorted(set(prev_pc) | set(curr_pc))
            for cl in all_cls:
                pf = prev_pc.get(cl, {}).get("f1", 0)
                cf = curr_pc.get(cl, {}).get("f1", 0)
                delta = cf - pf
                if abs(delta) > 0.001:
                    sign = "+" if delta >= 0 else ""
                    print(f"    {cl:30}: {pf:.2%} -> {cf:.2%} ({sign}{delta:.2%})")

        print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline benchmark suite")
    parser.add_argument(
        "--data",
        default="backend/tests/benchmarks/benchmark_dataset.json",
        help="Path to benchmark dataset",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Diff against previous latest_report.json",
    )
    args = parser.parse_args()

    suite = PipelineBenchmarkSuite(args.data)
    asyncio.run(suite.run_all(compare=args.compare))
