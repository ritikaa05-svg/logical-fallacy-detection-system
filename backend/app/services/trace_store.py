"""
Phase 9.4: Symbolic Trace Store

Persists per-analysis symbolic trace trees as JSON files (with an in-memory
cache) so the Researcher's Dashboard can render Z3 proof trees alongside ML
confidence scores and saliency maps.

Trace tree shape mirrors the frontend TraceNode contract:
    {node_type, label, confidence?, saliency_tokens?, children?}
"""

import json
import logging
import threading
import time
from pathlib import Path

from backend.app.config import settings

logger = logging.getLogger(__name__)

Z3_STATUS_MAP = {
    "SAT": "satisfiable",
    "UNSAT": "unsatisfiable",
    "sat": "satisfiable",
    "unsat": "unsatisfiable",
    "UNKNOWN": "unknown",
    "unknown": "unknown",
    "skipped": "skipped",
}


def _truncate(text: str | None, limit: int = 400) -> str | None:
    if not text:
        return text
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _top_salient_tokens(result, limit: int = 8) -> list[str]:
    tokens = []
    for t in result.salient_tokens or []:
        if isinstance(t, dict):
            token = t.get("token") or t.get("text")
        else:
            token = getattr(t, "token", None) or getattr(t, "text", None)
        if token and token not in tokens:
            tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def build_trace_tree(result, z3_ctx=None) -> dict:
    """Build a TraceNode tree from an InferenceResult (plus optional Z3Context).

    The tree is always buildable from the result alone (works for cached
    hits). When a Z3Context is supplied, the SMT script, Z3 model output and
    parser confidence enrich the Z3 branch.
    """
    root_children: list[dict] = []

    # --- Stage 1: Gatekeeper ---
    gatekeeper_children = []
    if getattr(result, "salience_score", None) is not None:
        gatekeeper_children.append(
            {
                "node_type": "salience",
                "label": f"Salience score: {result.salience_score:.3f}",
                "confidence": float(result.salience_score),
            }
        )
    salient_tokens = _top_salient_tokens(result)
    root_children.append(
        {
            "node_type": "gatekeeper",
            "label": f"Stage 1 — Gatekeeper: {'logical claim' if result.is_logical_claim else 'not a logical claim'}",
            "confidence": float(getattr(result, "salience_score", 0.0) or 0.0),
            "saliency_tokens": salient_tokens,
            "children": gatekeeper_children,
        }
    )

    # --- Structural Parser ---
    arg_struct = getattr(result, "argument_structure", None)
    if arg_struct is not None and getattr(arg_struct, "is_argument", False):
        structure_children = []
        for i, premise in enumerate(getattr(arg_struct, "premises", []) or []):
            structure_children.append(
                {
                    "node_type": "premise",
                    "label": f"Premise {i + 1}: {_truncate(premise, 160) or '(empty)'}",
                }
            )
        conclusion = getattr(arg_struct, "conclusion", "") or ""
        structure_children.append(
            {
                "node_type": "conclusion",
                "label": f"Conclusion: {_truncate(conclusion, 160) or '(none extracted)'}",
                "confidence": float(getattr(arg_struct, "confidence", 0.0) or 0.0),
            }
        )
        reasoning = getattr(arg_struct, "reasoning_type", "unknown") or "unknown"
        root_children.append(
            {
                "node_type": "structure",
                "label": f"Structural parser — argument ({reasoning} reasoning)",
                "confidence": float(getattr(arg_struct, "confidence", 0.0) or 0.0),
                "children": structure_children,
            }
        )

    # --- Stages 2/3: Classification ---
    fine_labels = result.fine_labels or []
    fine_scores = result.confidence_scores or []
    classification_children = []
    for label, score in zip(fine_labels[:3], fine_scores[:3]):
        classification_children.append(
            {
                "node_type": "fine",
                "label": label.replace("_", " ").title(),
                "confidence": float(score),
            }
        )
    coarse = result.coarse_category or "Unknown"
    root_children.append(
        {
            "node_type": "classification",
            "label": f"Stages 2/3 — {coarse}" + (f" ({len(fine_labels)} fine labels)" if fine_labels else ""),
            "children": classification_children,
        }
    )

    # --- Stage 4: Neuro-Symbolic (Z3) ---
    z3_status = (getattr(result, "z3_status", None) or "skipped").upper()
    node_type = Z3_STATUS_MAP.get(z3_status, z3_status.lower() or "skipped")

    z3_children = []
    if z3_ctx is not None:
        smt_script = getattr(z3_ctx, "smt_script", None)
        model = getattr(z3_ctx, "model", None)
        error_message = getattr(z3_ctx, "error_message", None)
        parsing_confidence = getattr(z3_ctx, "parsing_confidence", None)
        if smt_script:
            z3_children.append(
                {
                    "node_type": "smt",
                    "label": f"SMT script: {_truncate(smt_script, 400) or '(empty)'}",
                }
            )
        if model:
            z3_children.append(
                {
                    "node_type": "model",
                    "label": f"Z3 model: {_truncate(model, 400) or '(empty)'}",
                }
            )
        if error_message:
            z3_children.append(
                {
                    "node_type": "error",
                    "label": f"Error: {_truncate(error_message, 300)}",
                }
            )
        if parsing_confidence is not None:
            z3_children.append(
                {
                    "node_type": "parsing",
                    "label": f"Translation parsing confidence",
                    "confidence": float(parsing_confidence),
                }
            )

    if z3_status == "SKIPPED":
        z3_label = "Stage 4 — Z3 formal check: skipped (informal fallacy)"
    elif z3_status == "UNKNOWN":
        z3_label = "Stage 4 — Z3 formal check: inconclusive"
    elif z3_status == "UNSAT":
        z3_label = "Stage 4 — Z3 formal check: premises are contradictory (UNSAT)"
    else:
        z3_label = "Stage 4 — Z3 formal check: premises satisfiable (SAT)"

    if z3_children or z3_status not in ("SKIPPED",):
        root_children.append(
            {
                "node_type": node_type,
                "label": z3_label,
                "children": z3_children,
            }
        )

    # --- Correction strategy (Stage 4 synthesis) ---
    correction = getattr(result, "correction_strategy", None)
    if correction:
        root_children.append(
            {
                "node_type": "correction",
                "label": f"Correction: {_truncate(correction, 400)}",
            }
        )

    return {
        "node_type": "root",
        "label": "Symbolic Trace",
        "children": root_children,
    }


class TraceStore:
    """File-backed store for symbolic trace trees with an in-memory cache."""

    def __init__(self, storage_dir: str | None = None, max_files: int | None = None):
        self.storage_dir = Path(storage_dir or settings.TRACE_STORAGE_DIR)
        self.max_files = max_files or settings.TRACE_MAX_FILES
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, dict] = {}
        self._prune()

    def _path_for(self, analysis_id: str) -> Path:
        safe_id = "".join(c for c in analysis_id if c.isalnum() or c in "-_")
        return self.storage_dir / f"{safe_id}.json"

    def _prune(self) -> None:
        """Delete oldest trace files beyond the retention limit."""
        try:
            files = sorted(self.storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            evicted = files[self.max_files :]
            for old in evicted:
                old.unlink(missing_ok=True)
            if evicted:
                with self._lock:
                    for old in evicted:
                        self._cache.pop(old.stem, None)
        except Exception as e:
            logger.warning(f"Trace prune failed: {e}")

    def capture(self, analysis_id: str, result, z3_ctx=None) -> None:
        """Build and persist a trace tree for the given analysis."""
        if not analysis_id:
            return
        try:
            payload = {
                "analysis_id": analysis_id,
                "timestamp": getattr(result, "timestamp", None) or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "input_text": getattr(result, "input_text", "")[:200],
                "logic_score": float(getattr(result, "logic_score", 0.0) or 0.0),
                "trace_tree": build_trace_tree(result, z3_ctx),
            }
            with self._lock:
                self._cache[analysis_id] = payload
            self._path_for(analysis_id).write_text(json.dumps(payload, indent=2, ensure_ascii=False))
            self._prune()
        except Exception as e:
            logger.error(f"Failed to capture trace for '{analysis_id}': {e}")

    def get(self, analysis_id: str) -> dict | None:
        """Return the stored trace payload, or None if not found."""
        with self._lock:
            if analysis_id in self._cache:
                return self._cache[analysis_id]
        path = self._path_for(analysis_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
            with self._lock:
                self._cache[analysis_id] = payload
            return payload
        except Exception as e:
            logger.error(f"Failed to load trace '{analysis_id}': {e}")
            return None


trace_store = TraceStore()
