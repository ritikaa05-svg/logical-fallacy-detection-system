import argparse
import json
import sys


def load_report(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_metrics(report: dict) -> dict:
    return {
        "suite_a": {"f1": report.get("suite_a", {}).get("f1", 0)},
        "suite_b": {"avg_iou": report.get("suite_b", {}).get("avg_iou", 0)},
        "suite_c": {"span_alignment_accuracy": report.get("suite_c", {}).get("span_alignment_accuracy", 0)},
        "suite_d": {
            "macro_f1": report.get("suite_d", {}).get("macro_f1", 0),
            "exact_match_accuracy": report.get("suite_d", {}).get("exact_match_accuracy", 0),
        },
        "classification": {
            "macro_f1": report.get("classification", {}).get("macro_f1", 0),
            "micro_f1": report.get("classification", {}).get("micro_f1", 0),
        },
    }


def compare(current: dict, baseline: dict, threshold: float) -> tuple[bool, list[str]]:
    failures = []
    for suite, metrics in current.items():
        for metric, cur_val in metrics.items():
            if not isinstance(cur_val, (int, float)):
                continue
            base_val = baseline.get(suite, {}).get(metric)
            if base_val is None or not isinstance(base_val, (int, float)):
                continue
            delta = cur_val - base_val
            if delta < -threshold:
                failures.append(
                    f"{suite}.{metric}: baseline={base_val:.4f}, "
                    f"current={cur_val:.4f}, delta={delta:.4f} (exceeds -{threshold})"
                )
    return len(failures) == 0, failures


def print_table(current: dict, baseline: dict):
    print(f"{'Suite':<20} {'Metric':<30} {'Baseline':<10} {'Current':<10} {'Delta':<10}")
    print("-" * 80)
    for suite, metrics in current.items():
        for metric, cur_val in metrics.items():
            base_val = baseline.get(suite, {}).get(metric, "N/A")
            if isinstance(base_val, (int, float)):
                delta = cur_val - base_val
                print(f"{suite:<20} {metric:<30} {base_val:<10.4f} {cur_val:<10.4f} {delta:<+10.4f}")
            else:
                print(f"{suite:<20} {metric:<30} {str(base_val):<10} {cur_val:<10.4f} {'N/A':<10}")


def main():
    parser = argparse.ArgumentParser(description="Compare benchmark results against a baseline.")
    parser.add_argument("--current", required=True, help="Path to current benchmark report JSON")
    parser.add_argument("--baseline", required=True, help="Path to baseline benchmark JSON")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.02,
        help="Maximum allowed F1 drop (default: 0.02)",
    )
    args = parser.parse_args()

    current_report = load_report(args.current)
    baseline_report = load_report(args.baseline)

    current_metrics = extract_metrics(current_report)
    baseline_metrics = extract_metrics(baseline_report)

    ok, failures = compare(current_metrics, baseline_metrics, args.threshold)

    print("=" * 80)
    print("BENCHMARK COMPARISON")
    print("=" * 80)
    print_table(current_metrics, baseline_metrics)
    print("=" * 80)

    if ok:
        print("All metrics within threshold.")
        sys.exit(0)
    else:
        print(f"FAILED: {len(failures)} metric(s) dropped below threshold:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
