from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.z3_service import Z3Result, Z3Service


@pytest.fixture
def z3_service():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Z3 version 4.13.0")
        service = Z3Service()
        service._solver_path = "z3"
        return service


class TestExtractLogicalStructure:
    def test_basic_premise_conclusion_extraction(self, z3_service):
        text = "All men are mortal. Socrates is a man. Therefore, Socrates is mortal."
        premises, conclusion, confidence = z3_service._extract_logical_structure_regex(text)
        assert len(premises) == 2
        assert "Socrates is mortal" in conclusion
        assert confidence == 0.85

    def test_no_conclusion_marker_uses_last_sentence(self, z3_service):
        text = "It is raining. The ground is wet."
        premises, conclusion, confidence = z3_service._extract_logical_structure_regex(text)
        assert len(premises) == 1
        assert "The ground is wet" in conclusion or "the ground is wet" in conclusion
        assert confidence == 0.65

    def test_single_sentence_returns_empty(self, z3_service):
        text = "Hello world."
        premises, conclusion, confidence = z3_service._extract_logical_structure_regex(text)
        assert premises == []
        assert conclusion == ""
        assert confidence == 0.0

    def test_hence_marker(self, z3_service):
        text = "The data supports the hypothesis. Hence, the theory is correct."
        premises, conclusion, confidence = z3_service._extract_logical_structure_regex(text)
        assert len(premises) >= 1
        assert "theory is correct" in conclusion


class TestBuildSmtRegex:
    def test_basic_propositional_mapping(self, z3_service):
        premises = ["All men are mortal", "Socrates is a man"]
        conclusion = "Socrates is mortal"
        script, confidence = z3_service._build_smt_regex(premises, conclusion)
        assert "(set-logic QF_UF)" in script
        assert "(check-sat)" in script
        assert "(declare-const" in script

    def test_implication_if_then(self, z3_service):
        premises = ["If it rains, then the ground is wet"]
        conclusion = "The ground is wet"
        script, _ = z3_service._build_smt_regex(premises, conclusion)
        assert "(=>" in script

    def test_negation_handling(self, z3_service):
        premises = ["It is not raining"]
        conclusion = "The ground is dry"
        script, _ = z3_service._build_smt_regex(premises, conclusion)
        assert "(not" in script

    def test_variable_deduplication(self, z3_service):
        premises = ["Socrates is mortal"]
        conclusion = "Socrates is mortal"
        script, _ = z3_service._build_smt_regex(premises, conclusion)
        var_count = script.count("(declare-const")
        assert var_count == 1


class TestRunZ3:
    def test_no_solver_available(self, z3_service):
        z3_service._solver_path = None
        status, model, error = z3_service._run_z3("(check-sat)")
        assert status == "unknown"
        assert error == "Z3 not installed"

    def test_timeout_returns_timeout(self, z3_service):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = __import__("subprocess").TimeoutExpired("z3", 5)
            status, model, error = z3_service._run_z3("(check-sat)")
            assert status == "timeout"
            assert error == "Timeout"

    def test_unsat_result(self, z3_service):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="unsat\n", stderr="")
            status, model, error = z3_service._run_z3("(check-sat)")
            assert status == "unsat"

    def test_error_returncode(self, z3_service):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="parse error")
            status, model, error = z3_service._run_z3("(check-sat)")
            assert status == "error"
            assert error == "parse error"


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_llm_success_path(self, z3_service):
        with patch("backend.app.services.z3_service.llm_to_smt") as mock_llm:
            mock_llm.return_value = ("(check-sat)", 0.9)
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="unsat\n", stderr="")
                result = await z3_service.analyze("If it rains, the ground gets wet.")
                assert result.status == "unsat"
                assert result.parsing_confidence == 0.9

    @pytest.mark.asyncio
    async def test_regex_fallback_on_low_confidence(self, z3_service):
        with patch("backend.app.services.z3_service.llm_to_smt") as mock_llm:
            mock_llm.return_value = (None, 0.3)
            with patch.object(z3_service, "_extract_logical_structure_regex") as mock_extract:
                mock_extract.return_value = (["premise"], "conclusion", 0.85)
                with patch.object(z3_service, "_build_smt_regex") as mock_build:
                    mock_build.return_value = ("(check-sat)", 0.6)
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=0, stdout="sat\n", stderr="")
                        result = await z3_service.analyze("If it rains, the ground gets wet.")
                        assert result.status == "sat"
                        assert result.parsing_confidence <= 0.6
                        mock_extract.assert_called_once()
                        mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_parsers_fail(self, z3_service):
        with patch("backend.app.services.z3_service.llm_to_smt") as mock_llm:
            mock_llm.return_value = (None, 0.3)
            with patch.object(z3_service, "_extract_logical_structure_regex") as mock_extract:
                mock_extract.return_value = ([], "", 0.0)
                result = await z3_service.analyze("Hello.")
                assert result.status == "unknown"
                assert "Both LLM and Regex parsing failed" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_z3_error_triggers_regex_fallback(self, z3_service):
        with patch("backend.app.services.z3_service.llm_to_smt") as mock_llm:
            mock_llm.return_value = ("(invalid-script)", 0.9)
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: parse error")
                with patch.object(z3_service, "_extract_logical_structure_regex") as mock_extract:
                    mock_extract.return_value = (["premise"], "conclusion", 0.85)
                    with patch.object(z3_service, "_build_smt_regex") as mock_build:
                        mock_build.return_value = ("(check-sat)", 0.6)
                        result = await z3_service.analyze("If it rains, the ground gets wet.")
                        assert result.status in ("sat", "unsat", "unknown", "error")
                        mock_extract.assert_called_once()


class TestZ3Result:
    def test_dataclass_defaults(self):
        result = Z3Result(status="unknown", parsing_confidence=0.0)
        assert result.latency_ms == 0.0
        assert result.smt_script is None
        assert result.model is None
        assert result.error_message is None

    def test_dataclass_full(self):
        result = Z3Result(
            status="unsat",
            parsing_confidence=0.95,
            smt_script="(check-sat)",
            model="",
            error_message=None,
            latency_ms=12.5,
        )
        assert result.status == "unsat"
        assert result.latency_ms == 12.5
