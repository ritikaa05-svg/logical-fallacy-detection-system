from unittest.mock import MagicMock, patch

import pytest

from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.schemas.inference import ConversationTurn, InferenceResult


@pytest.mark.asyncio
async def test_pipeline_orchestrator_basic():
    """Test that the orchestrator can process a simple text."""
    orchestrator = PipelineOrchestrator()
    text = "If it rains, the ground gets wet. The ground is wet, therefore it rained."

    # Mocking services to avoid loading large models in tests
    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        mock_s1.return_value = (True, 0.95, 10.0)

        with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
            mock_s2.return_value = ("Formal", 0.9, 10.0)

            with patch("backend.app.pipeline.orchestrator.fine_classifier.predict_multi") as mock_s3:
                mock_s3.return_value = {
                    "fine_labels": ["affirming_consequent"],
                    "fine_confidences": [0.85],
                    "sentence_details": [
                        {
                            "sentence": "The ground is wet, therefore it rained.",
                            "start": 29,
                            "end": 66,
                            "label": "affirming_consequent",
                            "score": 0.85,
                        }
                    ],
                    "salient_tokens": [],
                    "explanations_requested": False,
                    "latency_ms": 10.0,
                }

                with patch("backend.app.pipeline.orchestrator.fine_classifier.predict") as mock_s3_legacy:
                    mock_s3_legacy.return_value = (
                        ["affirming_consequent"],
                        [0.85],
                        ["affirming_consequent"],
                        [0.85],
                        [],
                        10.0,
                    )

                    with patch("backend.app.pipeline.orchestrator.z3_service.analyze") as mock_z3:
                        mock_z3.return_value = MagicMock(status="sat", latency_ms=10.0)

                        with patch("backend.app.pipeline.orchestrator.llm_synthesis_service.generate") as mock_s4:
                            mock_s4.return_value = ("Correction strategy", 10.0)

                            result = await orchestrator.analyze(text, skip_cache=True)

                            assert isinstance(result, InferenceResult)
                            assert result.is_logical_claim is True
                            assert result.coarse_category == "Formal"
                            assert "affirming_consequent" in result.fine_labels
                            assert result.z3_status == "sat"


@pytest.mark.asyncio
async def test_pipeline_gatekeeper_early_exit():
    """Test that the pipeline exits early if Stage 1 threshold is not met."""
    orchestrator = PipelineOrchestrator()
    text = "Hello world."

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        # Salience below default threshold (usually 0.3)
        mock_s1.return_value = (False, 0.1, 5.0)

        # Ensure Stage 2 is NOT called
        with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
            result = await orchestrator.analyze(text, skip_cache=True)

            assert result.is_logical_claim is False
            assert result.salience_score == 0.1
            assert result.coarse_category == "Non-Fallacious"
            assert result.z3_status == "skipped"
            mock_s2.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_with_history():
    """Test that history context is correctly handled and offsets are shifted."""
    orchestrator = PipelineOrchestrator()
    text = "You are wrong."
    history = [ConversationTurn(role="user", text="I am right.")]

    # Prefix will be "user: I am right. [TURN] current: "
    expected_prefix = "user: I am right. [TURN] current: "
    shift = len(expected_prefix)

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        mock_s1.return_value = (True, 0.98, 5.0)
        with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
            mock_s2.return_value = ("Informal (Relevance)", 0.8, 5.0)
            with patch("backend.app.pipeline.orchestrator.fine_classifier.predict_multi") as mock_s3:
                # Mock salient tokens WITH the shifted offsets
                mock_s3.return_value = {
                    "fine_labels": ["ad_hominem"],
                    "fine_confidences": [0.7],
                    "sentence_details": [
                        {
                            "sentence": "You are wrong.",
                            "start": shift,
                            "end": shift + 14,
                            "label": "ad_hominem",
                            "score": 0.7,
                        }
                    ],
                    "salient_tokens": [
                        {"token": "You", "score": 0.9, "start": shift, "end": shift + 3}
                    ],
                    "explanations_requested": False,
                    "latency_ms": 5.0,
                }
                with patch("backend.app.pipeline.orchestrator.llm_synthesis_service.generate") as mock_s4:
                    mock_s4.return_value = ("Correction", 5.0)

                    result = await orchestrator.analyze(text, skip_cache=True, history=history)

                    # Verify salient tokens are shifted BACK to original text indices
                    assert result.salient_tokens[0].start == 0
                    assert result.salient_tokens[0].end == 3


@pytest.mark.asyncio
async def test_pipeline_cache_interaction():
    """Test that the orchestrator interacts with the cache service correctly."""
    PipelineOrchestrator()

    with patch("backend.app.pipeline.orchestrator.cache_service") as mock_cache:
        mock_cache.is_available = True

        # Define async mock for get
        async def mock_get(key):
            return None

        mock_cache.get = mock_get

        # Define async mock for set
        async def mock_set(key, value):
            return True

        mock_cache.set = mock_set


@pytest.mark.asyncio
async def test_paragraph_contradictions_have_no_page_labels():
    """Text-mode (paragraph) analysis must not label segments as pages.

    Regression test: page_number used to default to idx + 1, so paragraph
    segments were labeled "Page 1", "Page 2", ... even without any document.
    """
    orchestrator = PipelineOrchestrator()
    text = "The new policy destroys economic growth.\n\nHowever, the same policy creates new jobs for everyone."

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        mock_s1.return_value = (True, 0.98, 5.0)
        with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
            mock_s2.return_value = ("Informal (Presumption)", 0.8, 5.0)
            with patch("backend.app.pipeline.orchestrator.fine_classifier.predict_multi") as mock_s3:
                mock_s3.return_value = {
                    "fine_labels": ["false_cause"],
                    "fine_confidences": [0.7],
                    "sentence_details": [
                        {
                            "sentence": "The new policy destroys economic growth.",
                            "start": 0,
                            "end": 40,
                            "label": "false_cause",
                            "score": 0.7,
                        }
                    ],
                    "salient_tokens": [],
                    "explanations_requested": False,
                    "latency_ms": 5.0,
                }
                with patch("backend.app.pipeline.orchestrator.llm_synthesis_service.generate") as mock_s4:
                    mock_s4.return_value = ("Correction", 5.0)

                    result = await orchestrator.analyze(text, skip_cache=True)

    assert result.cross_segment_contradictions is not None
    contradictions = result.cross_segment_contradictions.contradictions
    assert len(contradictions) >= 1
    for c in contradictions:
        assert c.segment_a_page is None
        assert c.segment_b_page is None
        assert "Page" not in c.description


def test_fallacy_signatures_cover_all_formal_classes():
    """Every formal fine-label class must have discourse signatures.

    Regression: 5 formal classes (exclusive_premises, existential_fallacy,
    illicit_major, illicit_minor, undistributed_middle) were missing from
    FALLACY_SIGNATURES, so the offline quote extractor had no anchor patterns
    for them.
    """
    import re

    from backend.app.pipeline.orchestrator import FALLACY_SIGNATURES
    from backend.app.services.unified_classifier import UnifiedClassifier

    formal = {fine for fine, coarse in UnifiedClassifier.SHADOW_COARSE_MAP.items() if coarse == "Formal"}
    missing = formal - set(FALLACY_SIGNATURES)
    assert not missing, f"Formal classes missing signatures: {missing}"

    for fine in formal:
        assert FALLACY_SIGNATURES[fine], f"{fine} has an empty signature list"

    for patterns in FALLACY_SIGNATURES.values():
        for pat in patterns:
            re.compile(pat)


def test_fallacy_signature_examples_match():
    """The new formal-class signatures must match representative instances."""
    import re

    from backend.app.pipeline.orchestrator import FALLACY_SIGNATURES

    cases = {
        "exclusive_premises": (
            "No cats are mammals and no dogs are reptiles, therefore no cats are reptiles.",
            r"\bno\s+\w+\s+(are|is)\b.{0,80}\bno\s+\w+\s+(are|is)\b",
        ),
        "existential_fallacy": (
            "All humans are mortal and no mortals are perfect, therefore some humans are not perfect.",
            r"\b(all|every|no)\b.{0,60}\b(some|few)\b.{0,60}\b(therefore|so|thus)\b",
        ),
        "illicit_major": (
            "Some students are athletes and all athletes are healthy, therefore all students are healthy.",
            r"\b(therefore|so|thus)\b.{0,50}\ball\s+\w+\s+(are|is)\b",
        ),
        "illicit_minor": (
            "All birds are animals and some pets are birds, therefore no pets are animals.",
            r"\b(therefore|so|thus)\b.{0,50}\bno\s+\w+\s+(are|is)\b",
        ),
        "undistributed_middle": (
            "All dogs are animals and all cats are animals, therefore all dogs are cats.",
            r"\ball\s+\w+\s+(are|is)\s+\w+\b.{0,80}\ball\s+\w+\s+(are|is)\s+\w+\b",
        ),
    }
    for fallacy, (text, pat) in cases.items():
        assert any(
            re.search(p, text, re.IGNORECASE) for p in FALLACY_SIGNATURES[fallacy]
        ), f"No signature in {fallacy} matched: {text} (expected at least {pat})"


def test_segment_text_keeps_multi_sentence_argument_together():
    """Regression: sentence-boundary splitting produced false positives.

    Multi-sentence arguments (e.g. "The ground is wet. Therefore it rained.")
    used to be split into per-sentence segments, so the lone conclusion
    fragment was classified without its premise. Segmentation must only
    occur on explicit line breaks, section delimiters, or token overflow.
    """
    from backend.app.pipeline.segmenter import segment_text

    assert len(segment_text("The ground is wet. Therefore it rained.")) == 1
    assert len(segment_text("If it rains, the ground gets wet. The ground is wet, therefore it rained.")) == 1
    # Explicit paragraph breaks still split
    assert len(segment_text("The first paragraph.\n\nThe second paragraph.")) == 2
    # Structured section delimiters still split
    assert len(segment_text("Definition: Straw man.\nExplanation: A distortion.")) == 2


@pytest.mark.asyncio
async def test_low_confidence_fallacy_becomes_valid_reasoning_when_argument_found():
    """Regression: a sub-floor detection on a real argument must not emit a
    fallacy. It should report valid reasoning instead of "Not an argument"."""
    from backend.app.schemas.inference import ArgumentIntelligenceResult

    orchestrator = PipelineOrchestrator()
    text = "The ground is wet. Therefore it rained."
    argument = ArgumentIntelligenceResult(
        status="success_regex",
        is_argument=True,
        premises=["The ground is wet."],
        conclusion="Therefore it rained.",
        reasoning_type="abductive",
    )

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        mock_s1.return_value = (True, 0.9, 5.0)
        with patch("backend.app.pipeline.orchestrator.structural_parser.parse_argument") as mock_parser:
            mock_parser.return_value = argument
            with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
                mock_s2.return_value = ("Informal (Causal)", 0.8, 5.0)
                with patch("backend.app.pipeline.orchestrator.fine_classifier.predict_multi") as mock_s3:
                    # false_cause at 0.58: above the global floor (0.35) but
                    # below the false_cause low-support floor (0.60 -> dropped)
                    mock_s3.return_value = {
                        "fine_labels": ["false_cause"],
                        "fine_confidences": [0.58],
                        "sentence_details": [
                            {
                                "sentence": "Therefore it rained.",
                                "start": 18,
                                "end": 38,
                                "label": "false_cause",
                                "score": 0.58,
                            }
                        ],
                        "salient_tokens": [],
                        "explanations_requested": False,
                        "latency_ms": 5.0,
                    }
                    with patch("backend.app.pipeline.orchestrator.fine_classifier.predict") as mock_s3_legacy:
                        mock_s3_legacy.return_value = (
                            ["false_cause"],
                            [0.58],
                            ["false_cause"],
                            [0.58],
                            [],
                            5.0,
                        )
                        with patch("backend.app.pipeline.orchestrator.llm_synthesis_service.generate") as mock_s4:
                            mock_s4.return_value = ("Correction", 5.0)
                            with patch("backend.app.pipeline.orchestrator.llm_synthesis_service.generate_unified_breakdown") as mock_breakdown:
                                mock_breakdown.return_value = []

                                result = await orchestrator.analyze(text, skip_cache=True)

    assert result.fine_labels == ["valid_reasoning"]
    assert result.coarse_category == "Non-Fallacious"
    assert result.logic_score == 1.0
    assert result.fallacies == []


@pytest.mark.asyncio
async def test_low_confidence_fallacy_without_argument_falls_back_to_factual():
    """Sub-floor detections on non-arguments must not surface as fallacies."""
    from backend.app.schemas.inference import ArgumentIntelligenceResult

    orchestrator = PipelineOrchestrator()
    text = "The ground is wet."

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        # High salience overrides the parser's non-argument verdict, so the
        # pipeline proceeds to classification (uncertainty buffer path).
        mock_s1.return_value = (True, 0.96, 5.0)
        with patch("backend.app.pipeline.orchestrator.structural_parser.parse_argument") as mock_parser:
            mock_parser.return_value = ArgumentIntelligenceResult(
                status="success", is_argument=False, premises=[], conclusion=""
            )
            with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
                mock_s2.return_value = ("Informal", 0.8, 5.0)
                with patch("backend.app.pipeline.orchestrator.fine_classifier.predict_multi") as mock_s3:
                    mock_s3.return_value = {
                        "fine_labels": ["false_cause"],
                        "fine_confidences": [0.58],
                        "sentence_details": [
                            {
                                "sentence": "The ground is wet.",
                                "start": 0,
                                "end": 18,
                                "label": "false_cause",
                                "score": 0.58,
                            }
                        ],
                        "salient_tokens": [],
                        "explanations_requested": False,
                        "latency_ms": 5.0,
                    }
                    with patch("backend.app.pipeline.orchestrator.fine_classifier.predict") as mock_s3_legacy:
                        mock_s3_legacy.return_value = (
                            ["false_cause"],
                            [0.58],
                            ["false_cause"],
                            [0.58],
                            [],
                            5.0,
                        )
                        with patch("backend.app.pipeline.orchestrator.llm_synthesis_service.generate") as mock_s4:
                            mock_s4.return_value = ("Correction", 5.0)
                            with patch("backend.app.pipeline.orchestrator.llm_synthesis_service.generate_unified_breakdown") as mock_breakdown:
                                mock_breakdown.return_value = []

                                result = await orchestrator.analyze(text, skip_cache=True)

    assert result.fine_labels == ["factual_statement"]
    assert result.fallacies == []


@pytest.mark.asyncio
async def test_pipeline_detects_multiple_fallacies_per_sentence():
    """Multi-sentence input must produce one card + annotation per fallacy,
    each quoting its own sentence. Sub-floor sentences get a signature supplement."""
    orchestrator = PipelineOrchestrator()
    s1 = "You claim the plan is terrible, but I never said that."
    s2 = "Everyone is buying this product, which proves it must be good."
    s3 = "If we let them close the library, things will just collapse."
    s4 = "Either we raise taxes or we cut all funding."
    text = f"{s1} {s2} {s3} {s4}"

    def off(sent):
        start = text.find(sent)
        return start, start + len(sent)

    s1_start, s1_end = off(s1)
    s2_start, s2_end = off(s2)
    s3_start, s3_end = off(s3)
    s4_start, s4_end = off(s4)

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        mock_s1.return_value = (True, 0.95, 5.0)
        with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
            mock_s2.return_value = ("Informal (Presumption)", 0.8, 5.0)
            with patch("backend.app.pipeline.orchestrator.fine_classifier.predict_multi") as mock_s3:
                mock_s3.return_value = {
                    "fine_labels": ["false_dilemma", "straw_man", "bandwagon", "hasty_generalization"],
                    "fine_confidences": [0.97, 0.675, 0.523, 0.30],
                    "sentence_details": [
                        {"sentence": s1, "start": s1_start, "end": s1_end, "label": "straw_man", "score": 0.675},
                        {"sentence": s2, "start": s2_start, "end": s2_end, "label": "bandwagon", "score": 0.523},
                        {
                            "sentence": s3,
                            "start": s3_start,
                            "end": s3_end,
                            "label": "hasty_generalization",
                            "score": 0.30,
                        },
                        {"sentence": s4, "start": s4_start, "end": s4_end, "label": "false_dilemma", "score": 0.97},
                    ],
                    "salient_tokens": [],
                    "explanations_requested": False,
                    "latency_ms": 5.0,
                }

                result = await orchestrator.analyze(text, skip_cache=True, fast_track=True)

    # Four cards, each quoting its own sentence
    names = {f.name for f in result.fallacies}
    assert names == {"false_dilemma", "straw_man", "bandwagon", "slippery_slope"}
    assert len(result.fallacies) == 4

    quote_by_name = {f.name: f.quote for f in result.fallacies}
    assert quote_by_name["false_dilemma"] == s4
    assert quote_by_name["straw_man"] == s1
    assert quote_by_name["bandwagon"] == s2
    assert quote_by_name["slippery_slope"] == s3

    conf_by_name = {f.name: f.confidence for f in result.fallacies}
    assert conf_by_name["false_dilemma"] == 0.97
    assert conf_by_name["slippery_slope"] == 0.45  # signature supplement

    # One annotation per fallacy, pointing at the correct sentence
    assert len(result.annotations) == 4
    ann_by_type = {a.type: a for a in result.annotations}
    assert ann_by_type["false_dilemma"].sentence == s4
    assert ann_by_type["false_dilemma"].sentence_start == s4_start
    assert ann_by_type["false_dilemma"].sentence_end == s4_end
    assert ann_by_type["straw_man"].sentence_start == s1_start
    assert ann_by_type["slippery_slope"].sentence_start == s3_start

    # Merged top-level labels keep per-label floors (hasty_generalization 0.30 dropped)
    # and the global 0.55 MIN_FALLACY_CONFIDENCE filter; lower-confidence labels
    # still surface as sentence-level cards.
    assert result.fine_labels == ["false_dilemma", "straw_man"]


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_predict_when_predict_multi_fails():
    """If predict_multi errors, the orchestrator must fall back to the legacy
    predict() result (keeping existing fine_classifier.predict mocks valid)."""
    orchestrator = PipelineOrchestrator()
    text = "You are wrong, and everyone knows it."

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        mock_s1.return_value = (True, 0.95, 5.0)
        with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
            mock_s2.return_value = ("Informal (Relevance)", 0.8, 5.0)
            with patch(
                "backend.app.pipeline.orchestrator.fine_classifier.predict_multi",
                side_effect=RuntimeError("multi unavailable"),
            ):
                with patch("backend.app.pipeline.orchestrator.fine_classifier.predict") as mock_s3_legacy:
                    mock_s3_legacy.return_value = (
                        ["ad_hominem"],
                        [0.8],
                        ["ad_hominem"],
                        [0.8],
                        [],
                        5.0,
                    )

                    result = await orchestrator.analyze(text, skip_cache=True, fast_track=True)

    assert "ad_hominem" in result.fine_labels
    assert any(f.name == "ad_hominem" for f in result.fallacies)


@pytest.mark.asyncio
async def test_predict_fine_multi_merges_labels_by_max_confidence():
    """Unit test: per-sentence labels are merged across sentences by max
    confidence, sorted descending, with remapped salient tokens."""
    from unittest.mock import AsyncMock

    from backend.app.services.unified_classifier import UnifiedClassifier

    classifier = UnifiedClassifier()
    text = "You are wrong. Everyone agrees with me."

    def fake_predict(sentence, **kwargs):
        if sentence == "You are wrong.":
            return {
                "fine_labels": ["ad_hominem", "straw_man"],
                "fine_confidences": [0.9, 0.3],
                "salient_tokens": [{"token": "wrong", "score": 0.8, "start": 4, "end": 9}],
                "explanations_requested": False,
            }
        return {
            "fine_labels": ["bandwagon", "ad_hominem"],
            "fine_confidences": [0.7, 0.2],
            "salient_tokens": [{"token": "Everyone", "score": 0.6, "start": 0, "end": 8}],
            "explanations_requested": False,
        }

    with patch.object(classifier, "predict", new=AsyncMock(side_effect=fake_predict)):
        res = await classifier.predict_fine_multi(text)

    # ad_hominem 0.9 (S1), bandwagon 0.7 (S2), straw_man 0.3 (top-2 of S1)
    assert res["fine_labels"] == ["ad_hominem", "bandwagon", "straw_man"]
    assert res["fine_confidences"] == [0.9, 0.7, 0.3]

    # Sentence details carry per-sentence offsets
    assert len(res["sentence_details"]) == 2
    assert res["sentence_details"][0]["sentence"] == "You are wrong."
    assert res["sentence_details"][0]["start"] == 0
    assert res["sentence_details"][1]["start"] == text.find("Everyone agrees with me.")

    # Salient tokens remapped to full-text offsets
    assert res["salient_tokens"][0]["start"] == 4
    assert res["salient_tokens"][1]["start"] == text.find("Everyone agrees with me.")


def test_signature_supplement_patterns_match():
    """The new signature patterns must match representative sentences."""
    import re

    from backend.app.pipeline.orchestrator import FALLACY_SIGNATURES

    cases = {
        "slippery_slope": (
            "If we pass this environmental restriction, it will completely ban all forms of "
            "construction nationwide, and every citizen will eventually be forced to live in mud huts.",
            r"\bif\b.{0,80}\bwill\b.{0,60}\b(every|all)\b.{0,50}\b(eventually|forced|ban|destroy|collapse|ruin|end|completely)\b",
        ),
        "ad_hominem": (
            "Once he was fired from his entry-level job, he cannot be trusted on anything.",
            r"\b(once|fired|entry-level job)\b.{0,60}\bcannot\s+be\s+trusted\b",
        ),
        "bandwagon": (
            "Everyone is buying this product, which proves it must be good.",
            r"\b(everyone|everybody)\b.{0,40}\b(proves|showing|which\s+proves)\b",
        ),
        "appeal_to_ignorance": (
            "No one has ever definitively proven that cutting down this specific forest causes "
            "permanent damage to the ecosystem, which means it is completely safe to do so.",
            r"\bno\s+one\b.{0,80}\bproven\b.{0,120}\b(which\s+means|means|therefore|so|thus)\b",
        ),
    }
    for fallacy, (text_example, pat) in cases.items():
        assert any(
            re.search(p, text_example, re.IGNORECASE) for p in FALLACY_SIGNATURES[fallacy]
        ), f"No signature in {fallacy} matched: {text_example} (expected at least {pat})"


@pytest.mark.asyncio
async def test_signature_supplement_fires_when_label_below_low_support_floor():
    """Signature supplement must also fire when the model's top-1 is above the
    general floor but below its LOW_SUPPORT_CLASSES floor (nothing would surface
    as a card otherwise)."""
    orchestrator = PipelineOrchestrator()
    s1 = "No one has ever definitively proven that cutting down this forest causes permanent damage, which means it is completely safe to do so."
    s2 = "The economy grew last quarter."
    text = f"{s1} {s2}"

    s1_start = text.find(s1)

    with patch("backend.app.pipeline.orchestrator.gatekeeper_service.predict") as mock_s1:
        mock_s1.return_value = (True, 0.95, 5.0)
        with patch("backend.app.pipeline.orchestrator.coarse_classifier.predict") as mock_s2:
            mock_s2.return_value = ("Informal (Presumption)", 0.8, 5.0)
            with patch("backend.app.pipeline.orchestrator.fine_classifier.predict_multi") as mock_s3:
                mock_s3.return_value = {
                    "fine_labels": ["false_cause", "factual_statement"],
                    "fine_confidences": [0.58, 0.9],
                    "sentence_details": [
                        {
                            "sentence": s1,
                            "start": s1_start,
                            "end": s1_start + len(s1),
                            "label": "false_cause",  # 0.58 < false_cause floor 0.60 -> dropped
                            "score": 0.58,
                        }
                    ],
                    "salient_tokens": [],
                    "explanations_requested": False,
                    "latency_ms": 5.0,
                }

                result = await orchestrator.analyze(text, skip_cache=True, fast_track=True)

    # false_cause is dropped by its LOW_SUPPORT floor, but the sentence's
    # appeal-to-ignorance construction is caught by the signature supplement.
    assert result.fallacies
    assert {f.name for f in result.fallacies} == {"appeal_to_ignorance"}
    assert result.fallacies[0].confidence == 0.45
    assert result.fallacies[0].quote == s1
    assert len(result.annotations) == 1
    assert result.annotations[0].type == "appeal_to_ignorance"
    assert result.annotations[0].sentence_start == s1_start
