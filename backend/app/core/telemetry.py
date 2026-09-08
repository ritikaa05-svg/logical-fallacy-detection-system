import logging
import re
import threading

from prometheus_client import REGISTRY, Counter, Histogram, generate_latest

logger = logging.getLogger(__name__)

INFERENCE_LATENCY = Histogram(
    "logiscan_inference_latency_seconds",
    "Inference latency per stage",
    ["stage"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUESTS_TOTAL = Counter(
    "logiscan_requests_total",
    "Total requests by endpoint and status",
    ["endpoint", "status"],
)

ERRORS_TOTAL = Counter(
    "logiscan_errors_total",
    "Total errors by stage and type",
    ["stage", "error_type"],
)

THROUGHPUT = Counter(
    "logiscan_throughput_total",
    "Total requests processed",
    ["stage"],
)


_SANITIZED_LABELS: set[str] = set()


def _sanitize_label(label: str, max_len: int = 100) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", label)[:max_len]
    _SANITIZED_LABELS.add(sanitized)
    # Warn if any single label value has high cardinality
    cardinality = sum(1 for l in _SANITIZED_LABELS if l == sanitized)
    if cardinality > 100:
        logger.warning(f"High label cardinality detected: '{sanitized}' appears {cardinality} times")
    return sanitized


class MetricsCollector:
    def __init__(self):
        self._lock = threading.Lock()

    def observe_latency(self, stage: str, seconds: float):
        INFERENCE_LATENCY.labels(stage=_sanitize_label(stage)).observe(seconds)

    def increment_requests(self, endpoint: str, status: str):
        REQUESTS_TOTAL.labels(endpoint=_sanitize_label(endpoint), status=_sanitize_label(status)).inc()

    def increment_errors(self, stage: str, error_type: str):
        ERRORS_TOTAL.labels(stage=_sanitize_label(stage), error_type=_sanitize_label(error_type)).inc()

    def increment_throughput(self, stage: str):
        THROUGHPUT.labels(stage=_sanitize_label(stage)).inc()

    def generate(self) -> bytes:
        return generate_latest(REGISTRY)

    def get_registry(self):
        return REGISTRY


metrics = MetricsCollector()


def observe_latency(stage: str, seconds: float):
    metrics.observe_latency(stage, seconds)


def increment_requests(endpoint: str, status: str):
    metrics.increment_requests(endpoint, status)


def increment_errors(stage: str, error_type: str):
    metrics.increment_errors(stage, error_type)


def increment_throughput(stage: str):
    metrics.increment_throughput(stage)
