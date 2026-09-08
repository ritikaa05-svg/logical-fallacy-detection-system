"""
Debate System Schemas
Pydantic models for the RL-driven debate engine state, actions, and logging.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DebateState(BaseModel):
    """
    POMDP state representation for the debate engine.

    State vector: [fallacy_density, argument_depth, user_sentiment, logic_score]
    """

    fallacy_density: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Ratio of fallacious to non-fallacious statements in recent turns."
    )
    argument_depth: int = Field(
        default=1, ge=0, le=5, description="Measured complexity and nuance of user's arguments."
    )
    user_sentiment: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Estimated sentiment: -1 (hostile) to +1 (receptive)."
    )
    logic_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Moving average of logic scores over the debate."
    )

    def to_tensor(self) -> list[float]:
        """Convert state to a flat tensor for the DQN model."""
        return [
            self.fallacy_density,
            self.argument_depth / 5.0,  # Normalize to [0, 1]
            (self.user_sentiment + 1.0) / 2.0,  # Normalize to [0, 1]
            self.logic_score,
        ]

    @classmethod
    def from_tensor(cls, tensor: list[float]) -> "DebateState":
        """Reconstruct state from a DQN tensor."""
        return cls(
            fallacy_density=tensor[0],
            argument_depth=int(tensor[1] * 5),
            user_sentiment=tensor[2] * 2.0 - 1.0,
            logic_score=tensor[3],
        )


class DebateAction(BaseModel):
    """
    One of four possible debate actions the RL agent can take.
    """

    action_type: Literal[
        "ASK_SOCRATIC",
        "POINT_OUT_FALLACY",
        "COUNTER_ARGUMENT",
        "AGREE_AND_PIVOT",
    ] = Field(description="The strategic debate action to take.")

    action_index: int = Field(ge=0, le=3, description="Integer index: 0=ASK, 1=POINT, 2=COUNTER, 3=AGREE")

    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Q-value confidence for this action.")

    # Action-specific templates
    response_template: str = Field(default="", description="Template for generating the debate response.")


class DebateTurn(BaseModel):
    """Represents a single turn in the debate."""

    session_id: str = Field(description="The session this turn belongs to.")
    turn_number: int = Field(ge=1)
    user_input: str = Field(description="User's argument or response.")
    detected_fallacies: list[str] = Field(default_factory=list)
    logic_score: float = Field(ge=0.0, le=1.0)

    # Agent's response
    agent_action: DebateAction
    agent_response: str

    # State tracking
    state_before: DebateState
    state_after: DebateState

    # Reward
    reward: float = Field(default=0.0)

    # Metrics
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class DebateSession(BaseModel):
    """Full debate session with all turns."""

    session_id: str = Field(description="Unique session identifier.")
    turns: list[DebateTurn] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def total_turns(self) -> int:
        return len(self.turns)

    @property
    def average_logic_score(self) -> float:
        if not self.turns:
            return 1.0
        return sum(t.logic_score for t in self.turns) / len(self.turns)

    @property
    def cumulative_reward(self) -> float:
        return sum(t.reward for t in self.turns)


class DebateRequest(BaseModel):
    """Request to initiate or continue a debate."""

    session_id: str | None = Field(default=None, description="Existing session ID to continue a debate.")
    user_input: str = Field(..., min_length=1, max_length=5000, description="User's argument or response text.")


class DebateResponse(BaseModel):
    """Response from the debate engine."""

    session_id: str
    turn_number: int
    agent_response: str
    agent_action: str

    # Analysis
    detected_fallacies: list[str]
    logic_score: float

    # State
    debate_state: DebateState

    # Metrics
    total_turns: int
    cumulative_reward: float

    # Suggestions
    suggested_next_actions: list[str] = Field(default_factory=list, description="Possible next moves for the user.")
