"""
Debate API Router
Endpoints for the RL-powered debate engine.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.core.security import rate_limit_middleware, sanitize_input
from backend.app.schemas.debate import (
    DebateRequest,
    DebateResponse,
)
from backend.app.services.debate_service import debate_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["debate"])


@router.post(
    "/debate",
    response_model=DebateResponse,
    status_code=status.HTTP_200_OK,
    summary="Debate with the AI",
    description="""
    Start or continue a logical debate with the RL-powered debate engine.

    The AI analyzes your argument, selects a strategic response action via DQN,
    and generates a response designed to improve logical discourse.

    **Actions the AI can take:**
    - `ASK_SOCRATIC`: Pose a targeted question to expose contradictions
    - `POINT_OUT_FALLACY`: Name and explain a detected fallacy
    - `COUNTER_ARGUMENT`: Present a substantive counter-argument
    - `AGREE_AND_PIVOT`: Acknowledge valid points and refocus on logic

    **Session Management:**
    - First request: Leave session_id empty to create a new debate
    - Subsequent requests: Include session_id to continue the debate
    """,
    dependencies=[Depends(rate_limit_middleware)],
)
async def debate(
    request: DebateRequest,
    req: Request,
):
    """
    Main debate endpoint — processes a debate turn.
    """
    # Sanitize input
    try:
        sanitized_text = sanitize_input(request.user_input)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input validation failed: {str(e)}",
        )

    logger.info(f"Debate request: session={request.session_id or 'new'}, text_len={len(sanitized_text)} chars")

    try:
        turn = await debate_service.start_or_continue(
            user_input=sanitized_text,
            session_id=request.session_id,
        )
    except Exception as e:
        logger.error(f"Debate processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debate processing failed: {str(e)}",
        )

    # Build response
    session_id = getattr(turn, "session_id", request.session_id or "unknown")
    session = debate_service.get_session(session_id)

    response = DebateResponse(
        session_id=session_id,
        turn_number=turn.turn_number,
        agent_response=turn.agent_response,
        agent_action=turn.agent_action.action_type,
        detected_fallacies=turn.detected_fallacies,
        logic_score=turn.logic_score,
        debate_state=turn.state_after,
        total_turns=session.total_turns if session else turn.turn_number,
        cumulative_reward=session.cumulative_reward if session else turn.reward,
        suggested_next_actions=["Explain your reasoning", "Ask for a counter-example", "Restate your claim"],
    )

    logger.info(f"Debate response: action={turn.agent_action.action_type}, logic_score={turn.logic_score:.2f}")

    return response


@router.get(
    "/debate/session/{session_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get debate session summary",
    description="Retrieve the full summary of a debate session by ID.",
)
async def get_debate_session(session_id: str):
    """Retrieve a debate session summary."""
    summary = debate_service.get_session_summary(session_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate session '{session_id}' not found.",
        )

    return summary


@router.post(
    "/debate/train",
    status_code=status.HTTP_200_OK,
    summary="Trigger offline RL training",
    description="Run offline training on the debate agent using accumulated experience.",
)
async def train_agent(steps: int = 100):
    """Trigger offline training for the DQN agent."""
    if steps < 10 or steps > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Training steps must be between 10 and 1000.",
        )

    losses = debate_service.train_offline(steps)

    if not losses:
        return {
            "status": "insufficient_data",
            "message": "Not enough transitions in replay buffer for training.",
            "buffer_size": len(debate_service.agent.replay_buffer),
        }

    # Save model after training
    debate_service.save_model()

    return {
        "status": "trained",
        "steps_completed": len(losses),
        "average_loss": sum(losses) / len(losses),
        "epsilon": debate_service.agent.epsilon,
        "buffer_size": len(debate_service.agent.replay_buffer),
    }
