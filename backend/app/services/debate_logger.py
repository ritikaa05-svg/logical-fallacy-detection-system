"""
Best-effort debate turn logger.

Persists debate turns into the `debate_turns` table (schema in
`deployment/init-db.sql`) so the `rl_training_data` view accumulates real
state-action-reward transitions for future offline RL training.

Logging is strictly best-effort: if Postgres is unavailable or the DSN is a
placeholder, the logger warns once and silently no-ops. Debate never fails
because logging failed.
"""

import json
import logging

from backend.app.config import settings
from backend.app.schemas.debate import DebateTurn

logger = logging.getLogger(__name__)

try:
    import asyncpg
except ImportError:  # pragma: no cover - optional dependency
    asyncpg = None

_PLACEHOLDER_MARKERS = ("REPLACE_ME", "changeme")


class DebateLogger:
    """Async logger that writes debate turns to Postgres via asyncpg."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or getattr(settings, "DATABASE_URL", "") or ""
        self._warned = False

    @property
    def available(self) -> bool:
        """True when a real DSN is configured."""
        if not self.dsn:
            return False
        return not any(marker in self.dsn for marker in _PLACEHOLDER_MARKERS)

    async def log_turn(self, turn: DebateTurn) -> None:
        """Persist a single debate turn (no-op if DB is unavailable)."""
        if not self.available:
            return
        if asyncpg is None:
            self._warn_once("asyncpg not installed; debate turn logging disabled.")
            return

        try:
            conn = await asyncpg.connect(self.dsn)
        except Exception as e:
            self._warn_once(f"Debate turn logging disabled (DB unavailable): {e}")
            return

        try:
            # Upsert the session so the FK constraint is satisfied
            await conn.execute(
                """
                INSERT INTO debate_sessions (session_id, total_turns, average_logic_score, cumulative_reward)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (session_id) DO UPDATE SET
                    total_turns = EXCLUDED.total_turns,
                    average_logic_score = EXCLUDED.average_logic_score,
                    cumulative_reward = EXCLUDED.cumulative_reward,
                    updated_at = NOW()
                """,
                turn.session_id,
                turn.turn_number,
                turn.logic_score,
                turn.reward,
            )

            await conn.execute(
                """
                INSERT INTO debate_turns (
                    session_id, turn_number, user_input, detected_fallacies,
                    logic_score, agent_action, agent_response,
                    state_before, state_after, reward
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                turn.session_id,
                turn.turn_number,
                turn.user_input,
                json.dumps(turn.detected_fallacies),
                turn.logic_score,
                turn.agent_action.action_type,
                turn.agent_response,
                json.dumps(turn.state_before.model_dump()),
                json.dumps(turn.state_after.model_dump()),
                turn.reward,
            )
        except Exception as e:
            logger.warning(f"Debate turn logging failed (non-fatal): {e}")
        finally:
            await conn.close()

    def _warn_once(self, message: str) -> None:
        if not self._warned:
            logger.warning(message)
            self._warned = True


# Global singleton (lazy — no connection is made at import time)
debate_logger = DebateLogger()
