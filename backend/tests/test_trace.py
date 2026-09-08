import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.pipeline.orchestrator import Z3Context
from backend.app.schemas.inference import InferenceResult
from backend.app.services.trace_store import TraceStore, build_trace_tree, trace_store


@pytest.fixture
def store(tmp_path):
    return TraceStore(storage_dir=str(tmp_path / "traces"), max_files=5)


def _sample_result(**overrides) -> InferenceResult:
    base = dict(
        input_text="If it rains, the ground gets wet. The ground is wet, therefore it rained.",
        is_logical_claim=True,
        salience_score=0.95,
        coarse_category="Formal",
        fine_labels=["affirming_consequent"],
        confidence_scores=[0.85],
        z3_status="sat",
        correction_strategy="This argument commits affirming the consequent.",
        logic_score=0.15,
        total_latency_ms=450.0,
    )
    base.update(overrides)
    return InferenceResult(**base)


class TestBuildTraceTree:
    def test_minimal_tree_from_result(self):
        result = _sample_result()
        tree = build_trace_tree(result)
        assert tree["node_type"] == "root"
        assert tree["label"] == "Symbolic Trace"
        node_types = [c["node_type"] for c in tree["children"]]
        assert "gatekeeper" in node_types
        assert "classification" in node_types
        assert "satisfiable" in node_types
        # No SMT/model children without Z3Context
        z3 = next(c for c in tree["children"] if c["node_type"] == "satisfiable")
        assert z3["children"] == []

    def test_rich_tree_with_z3_context(self):
        result = _sample_result()
        ctx = Z3Context(
            status="sat",
            triggered=True,
            smt_script="(declare-const p Bool)\n(check-sat)",
            model="(define-fun p () Bool true)",
            parsing_confidence=0.92,
        )
        tree = build_trace_tree(result, ctx)
        z3 = next(c for c in tree["children"] if c["node_type"] == "satisfiable")
        child_types = [c["node_type"] for c in z3["children"]]
        assert "smt" in child_types
        assert "model" in child_types
        assert "parsing" in child_types
        parsing = next(c for c in z3["children"] if c["node_type"] == "parsing")
        assert parsing["confidence"] == 0.92

    def test_unsatisfiable_mapping(self):
        result = _sample_result(z3_status="unsat")
        tree = build_trace_tree(result)
        assert any(c["node_type"] == "unsatisfiable" for c in tree["children"])

    def test_skipped_z3_omitted_for_informal(self):
        result = _sample_result(coarse_category="Informal", z3_status="skipped")
        tree = build_trace_tree(result)
        node_types = [c["node_type"] for c in tree["children"]]
        assert "skipped" not in node_types
        assert "satisfiable" not in node_types

    def test_structure_children_from_argument(self):
        result = _sample_result(
            argument_structure={
                "status": "success",
                "is_argument": True,
                "premises": ["If it rains, the ground gets wet", "The ground is wet"],
                "conclusion": "It rained",
                "reasoning_type": "deductive",
                "confidence": 0.9,
            }
        )
        tree = build_trace_tree(result)
        structure = next(c for c in tree["children"] if c["node_type"] == "structure")
        labels = [c["label"] for c in structure["children"]]
        assert any("Premise 1" in l for l in labels)
        assert any(l.startswith("Conclusion") for l in labels)


class TestTraceStore:
    def test_roundtrip(self, store):
        store.capture("abc123", _sample_result())
        payload = store.get("abc123")
        assert payload is not None
        assert payload["analysis_id"] == "abc123"
        assert payload["trace_tree"]["node_type"] == "root"
        assert payload["logic_score"] == 0.15

    def test_rich_capture_keeps_z3_details(self, store):
        ctx = Z3Context(status="sat", triggered=True, smt_script="(check-sat)")
        store.capture("rich1", _sample_result(), ctx)
        payload = store.get("rich1")
        z3 = next(c for c in payload["trace_tree"]["children"] if c["node_type"] == "satisfiable")
        assert any(c["node_type"] == "smt" for c in z3["children"])

    def test_get_missing_returns_none(self, store):
        assert store.get("does-not-exist") is None

    def test_prune(self, store):
        for i in range(7):
            store.capture(f"id{i}", _sample_result())
        remaining = list(store.storage_dir.glob("*.json"))
        assert len(remaining) <= 5
        assert store.get("id0") is None
        assert store.get("id6") is not None

    def test_ignores_empty_id(self, store):
        store.capture("", _sample_result())
        assert list(store.storage_dir.glob("*.json")) == []


class TestTraceApi:
    @pytest.fixture(autouse=True)
    def _isolate_store(self, tmp_path, monkeypatch):
        monkeypatch.setattr(trace_store, "storage_dir", tmp_path / "traces")
        trace_store.storage_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(trace_store, "_cache", {})

    @pytest.mark.asyncio
    async def test_get_trace_roundtrip(self):
        trace_store.capture("api-1", _sample_result())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traces/api-1")
        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == "api-1"
        assert data["trace_tree"]["node_type"] == "root"
        assert any(c["node_type"] == "gatekeeper" for c in data["trace_tree"]["children"])

    @pytest.mark.asyncio
    async def test_get_trace_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traces/nope")
        assert response.status_code == 404
