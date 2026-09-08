"""
Pydantic schemas for LogiScan inference API.
Strict typing with comprehensive validation for all pipeline stages.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConversationTurn(BaseModel):
    """A single turn in a logical debate or conversation."""

    role: str = Field(..., description="Role of the speaker (user or assistant).")
    text: str = Field(..., description="The content of the utterance.")


class InferenceRequest(BaseModel):
    """Request schema for the logical fallacy analysis endpoint."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The input text to analyze for logical fallacies.",
        json_schema_extra={"example": "If it rains, the ground gets wet. The ground is wet, therefore it rained."},
    )

    history: list[ConversationTurn] | None = Field(
        default=None, description="Previous turns in the conversation for context-aware analysis."
    )

    skip_cache: bool = Field(default=False, description="If True, bypass the Redis cache and force fresh inference.")

    generate_correction: bool = Field(
        default=True, description="If True, generate a human-readable correction strategy."
    )

    include_explanations: bool = Field(
        default=False, description="If True, generate token-level saliency explanations (slower)."
    )

    localize: bool = Field(
        default=False,
        description="If True, force entirely local inference. Skip HuggingFace API fallback for this request, even if device_manager normally uses it.",
    )
    fast_track: bool = Field(
        default=False,
        description="If True, skip all LLM-heavy stages (structural parser LLM, Stage 4 synthesis LLM, rare class reranker, unified LLM breakdown) for faster results.",
    )

    @field_validator("text")
    def text_must_not_be_empty(cls, v: str) -> str:
        """Validate that text contains meaningful content."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Input text cannot be empty or whitespace-only.")
        if len(stripped.split()) < 2:
            raise ValueError("Input text must contain at least 2 words for analysis.")
        return stripped


class Stage1Result(BaseModel):
    """Output from the Stage 1 Gatekeeper (DistilBERT ONNX)."""

    is_logical_claim: bool = Field(description="Whether the text contains a logical claim that can be analyzed.")
    salience_score: float = Field(
        ge=0.0, le=1.0, description="Probability that the text contains an analyzable logical structure."
    )
    latency_ms: float = Field(ge=0.0, description="Stage 1 inference time in milliseconds.")


class Stage2Result(BaseModel):
    """Output from the Stage 2 Coarse Classifier (BERT-Large)."""

    coarse_category: str | None = Field(
        default=None,
        description="Predicted coarse fallacy category (Formal, Informal:Relevance, etc.).",
        json_schema_extra={"example": "Formal"},
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for the coarse category prediction.")
    latency_ms: float = Field(ge=0.0)

    @field_validator("coarse_category")
    def validate_category(cls, v: str | None) -> str | None:
        """Ensure category is from the predefined set."""
        valid_categories = {
            "Formal",
            "Informal (Relevance)",
            "Informal (Ambiguity)",
            "Informal (Presumption)",
            "Informal (Other)",
            "Non-Fallacious",
        }
        if v is not None and v not in valid_categories:
            raise ValueError(f"Invalid coarse category: {v}. Must be one of {valid_categories}")
        return v


class SpanAnnotation(BaseModel):
    """Specific trigger phrase within a sentence."""

    text: str = Field(..., description="The actual text of the trigger phrase.")
    start: int = Field(..., description="Start character index in original text.")
    end: int = Field(..., description="End character index in original text.")
    saliency: float = Field(..., description="Intensity score for highlighting.")


class FallacyAnnotation(BaseModel):
    """Semantically meaningful fallacy annotation for interactive UX."""

    type: str = Field(..., description="Machine name of the fallacy (e.g., ad_hominem).")
    label: str = Field(..., description="Human-readable name (e.g., Ad Hominem).")
    confidence: float = Field(..., description="Model confidence score.")
    definition: str = Field(..., description="Short, concise definition.")
    explanation: str = Field(..., description="Dynamically generated contextual explanation.")
    sentence: str = Field(..., description="The full sentence containing the fallacy.")
    sentence_start: int = Field(..., description="Start index of the sentence.")
    sentence_end: int = Field(..., description="End index of the sentence.")
    spans: list[SpanAnnotation] = Field(default_factory=list, description="Trigger spans within the sentence.")


class FallacyDetail(BaseModel):
    """Unified fallacy detail for the new breakdown format."""

    name: str = Field(..., description="Machine name of the fallacy.")
    quote: str = Field(..., description="Exact text that triggered the fallacy.")
    explanation: str = Field(..., description="One-sentence contextual explanation.")
    confidence: float = Field(..., ge=0.0, le=1.0)


class SalientToken(BaseModel):
    """Detailed attribution information for a single token."""

    token: str = Field(..., description="The decoded token text.")
    score: float = Field(..., description="Normalized attribution score (0.0 to 1.0).")
    start: int = Field(..., description="Start character index in original text.")
    end: int = Field(..., description="End character index in original text.")


class Stage3Result(BaseModel):
    """Output from the Stage 3 Fine-Grained Classifier (RoBERTa-Large)."""

    fine_labels: list[str] = Field(
        default_factory=list,
        description="Top predicted fallacy labels (up to 3).",
        json_schema_extra={"example": ["affirming_consequent", "false_dilemma"]},
    )
    confidence_scores: list[float] = Field(
        default_factory=list,
        description="Confidence scores corresponding to each predicted label.",
        json_schema_extra={"example": [0.85, 0.42]},
    )
    salient_tokens: list[SalientToken] = Field(
        default_factory=list, description="Tokens and their attribution scores for explainability."
    )
    all_labels: list[str] | None = Field(default=None, description="All 25 fallacy labels for debugging/dashboard.")
    all_scores: list[float] | None = Field(default=None, description="Scores for all 25 labels.")
    latency_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_label_score_consistency(self) -> "Stage3Result":
        """Ensure labels and scores have matching lengths."""
        if len(self.fine_labels) != len(self.confidence_scores):
            raise ValueError(
                f"fine_labels length ({len(self.fine_labels)}) must equal "
                f"confidence_scores length ({len(self.confidence_scores)})"
            )
        return self

    @field_validator("confidence_scores")
    def validate_confidence_range(cls, v: list[float]) -> list[float]:
        """Ensure all confidence scores are within [0, 1]."""
        for score in v:
            if score < 0.0 or score > 1.0:
                raise ValueError(f"Confidence score {score} out of range [0.0, 1.0]")
        return v


class Stage4Result(BaseModel):
    """Output from the Stage 4 Neuro-Symbolic Layer."""

    z3_status: str | None = Field(default=None, description="Result from Z3 SMT solver: 'sat', 'unsat', or 'unknown'.")
    z3_parsing_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in the SMT-LIBv2 translation from natural language."
    )
    correction_strategy: str | None = Field(
        default=None, description="Human-readable logical correction generated by the synthesis branch."
    )
    symbolic_latency_ms: float = Field(default=0.0, ge=0.0)
    synthesis_latency_ms: float = Field(default=0.0, ge=0.0)


class ArgumentIntelligenceResult(BaseModel):
    """
    Phase 5: Structured Argument Analysis Output.
    Enables deep reasoning validation beyond simple classification.
    """

    status: str = Field(
        default="success", description="Status of the structural analysis: 'success', 'failed', or 'unavailable'."
    )
    is_argument: bool = Field(
        description="Whether the input text contains a structured argument (premises + conclusion)."
    )
    premises: list[str] = Field(
        default_factory=list, description="Extracted explicit premises supporting the conclusion."
    )
    conclusion: str = Field(default="", description="The primary claim or conclusion being supported.")
    reasoning_type: str = Field(
        default="unknown", description="The intended logical structure (e.g., deductive, inductive, abductive)."
    )
    fallacy: str | None = Field(default=None, description="The primary identified logical fallacy, if any.")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Aggregate confidence in the structural extraction and classification."
    )
    explanation: str = Field(default="", description="Comprehensive explanation of why the argument fails or succeeds.")
    latency_ms: float = Field(default=0.0, ge=0.0)


class InferenceResult(BaseModel):
    """
    Complete inference result contract for LogiScan.
    This is the canonical output schema for all analysis endpoints.
    """

    # Versioning
    version: str = Field(default="v1.2.0-rc1", description="Complete model stack and configuration version hash.")

    # Trace
    analysis_id: str | None = Field(
        default=None, description="Unique identifier for this analysis, usable to fetch its symbolic trace."
    )

    # Input Echo
    input_text: str = Field(description="The sanitized input text that was analyzed.")

    # Stage 1
    is_logical_claim: bool = Field(description="Whether the text contains a logical claim.")
    salience_score: float = Field(ge=0.0, le=1.0, description="Salience score from Stage 1 gatekeeper.")

    # Stage 2
    coarse_category: str | None = Field(default=None, description="Coarse fallacy category from Stage 2.")

    # Stage 3
    fine_labels: list[str] = Field(default_factory=list, description="Top predicted fallacy labels from Stage 3.")
    confidence_scores: list[float] = Field(
        default_factory=list, description="Confidence scores for each predicted label."
    )
    salient_tokens: list[SalientToken] = Field(
        default_factory=list, description="List of detailed salient token objects."
    )

    # New Structured Annotations
    fallacies: list[FallacyDetail] = Field(default_factory=list, description="Unified fallacy breakdown format.")

    argument_structure: ArgumentIntelligenceResult | None = Field(
        default=None, description="Phase 5: Structured argument analysis (premises, conclusion, reasoning type)."
    )

    # Detailed Annotations (Keep for compatibility)
    annotations: list[FallacyAnnotation] = Field(
        default_factory=list, description="Structured annotations for interactive Obsidian-style UX."
    )

    # Stage 4
    z3_status: str | None = Field(default=None, description="Z3 solver result: 'sat', 'unsat', or 'unknown'.")
    correction_strategy: str | None = Field(
        default=None, description="Human-readable correction strategy from the synthesis branch."
    )

    # Metrics
    logic_score: float = Field(
        ge=0.0, le=1.0, description="Composite logic health score. 1.0 = perfectly logical, 0.0 = maximally fallacious."
    )

    # Performance
    total_latency_ms: float = Field(ge=0.0, description="Total end-to-end pipeline latency in milliseconds.")
    stage_latencies: dict = Field(default_factory=dict, description="Breakdown of latency per pipeline stage.")

    # System Metadata
    cached: bool = Field(default=False, description="Whether the result was served from Redis cache.")
    reranked: bool = Field(default=False, description="Whether the prediction was reranked by the LLM.")
    degradation_tier: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Active degradation tier: 0=full (GPU+LLM local+Z3), 1=ONNX-CPU+LLM 4-bit, 2=ONNX-CPU+API fallback, 3=ONNX-CPU+rule-based synthesis.",
    )
    device_info: dict = Field(default_factory=dict, description="Hardware device information for the inference.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(), description="UTC timestamp of the inference."
    )

    # Phase 6: Cross-segment contradiction analysis (None for single-segment inputs)
    cross_segment_contradictions: object | None = Field(
        default=None,
        description=(
            "Cross-segment contradiction analysis for multi-segment inputs. Type: CrossSegmentContradictions | None."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "v1.2.0-rc1",
                "input_text": "If it rains, the ground gets wet. The ground is wet, therefore it rained.",
                "is_logical_claim": True,
                "salience_score": 0.95,
                "coarse_category": "Formal",
                "fine_labels": ["affirming_consequent"],
                "confidence_scores": [0.89],
                "z3_status": "sat",
                "correction_strategy": "This argument commits the fallacy of affirming the consequent.",
                "logic_score": 0.15,
                "total_latency_ms": 450.0,
                "cached": False,
                "timestamp": "2026-05-04T12:00:00Z",
            }
        }
    )

    def dict_for_cache(self) -> dict:
        """Serialize to JSON-compatible dict for Redis caching."""
        return self.model_dump(mode="json")

    @classmethod
    def from_cache(cls, data: dict) -> "InferenceResult":
        """Deserialize from Redis cache data."""
        return cls.model_validate(data)
